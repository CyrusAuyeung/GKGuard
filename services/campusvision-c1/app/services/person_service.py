from __future__ import annotations

from datetime import datetime
from hashlib import sha1
import uuid
import numpy as np

from app.core.config import settings
from app.storage import db
from app.vision.face_engine import (
    confident_similarity_threshold,
    default_similarity_threshold,
    get_face_engine,
)
from app.vision.vector_math import cosine_similarity
from app.services import search_service
from app.services import person_merge_scorer


def _normalized_mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []

    arr = np.asarray(vectors, dtype="float32")
    mean = arr.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm < 1e-8:
        return mean.astype(float).tolist()
    return (mean / norm).astype(float).tolist()


def _seen_sort_key(record: dict) -> tuple[str, float]:
    return (record.get("captured_at") or "", float(record.get("video_timestamp_sec") or 0.0))


def _first_seen(records: list[dict]) -> str | None:
    values = [r.get("captured_at") for r in records if r.get("captured_at")]
    return min(values) if values else None


def _last_seen(records: list[dict]) -> str | None:
    values = [r.get("captured_at") for r in records if r.get("captured_at")]
    return max(values) if values else None


def _cluster_embedding(records: list[dict]) -> list[float]:
    return _normalized_mean([record["embedding"] for record in records])


def _frame_key(record: dict) -> tuple[str, float]:
    return (str(record.get("video_id") or ""), round(float(record.get("video_timestamp_sec") or 0.0), 3))


def _bbox_area(record: dict) -> float:
    bbox = record.get("bbox") or {}
    return max(1.0, float(bbox.get("x2", 0) - bbox.get("x1", 0))) * max(
        1.0, float(bbox.get("y2", 0) - bbox.get("y1", 0))
    )


def _detection_score(record: dict) -> float:
    return float((record.get("bbox") or {}).get("score") or 0.0)


def _time_display(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None

    total_ms = int(round(float(seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _parse_iso_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _record_event_sort_key(record: dict) -> tuple[str, float, str, float]:
    captured_sec = _parse_iso_seconds(record.get("captured_at"))
    return (
        str(record.get("camera_id") or ""),
        captured_sec if captured_sec is not None else float("inf"),
        str(record.get("video_id") or ""),
        float(record.get("video_timestamp_sec") or 0.0),
    )


def _is_quality_face(record: dict, min_face_area: float, min_detection_score: float) -> bool:
    return _bbox_area(record) >= min_face_area and _detection_score(record) >= min_detection_score


def _make_cluster(records: list[dict]) -> dict:
    embedding = _cluster_embedding(records)
    return {
        "records": sorted(records, key=_seen_sort_key),
        "embedding": embedding,
        "scores": {
            record["face_id"]: round(cosine_similarity(record["embedding"], embedding), 6)
            for record in records
        },
    }


def _cluster_time_bounds(cluster: dict) -> tuple[float, float]:
    times = [float(record.get("video_timestamp_sec") or 0.0) for record in cluster["records"]]
    return (min(times), max(times)) if times else (0.0, 0.0)


def _cluster_video_ids(cluster: dict) -> set[str]:
    return {str(record.get("video_id") or "") for record in cluster["records"]}


def _cluster_time_gap(left: dict, right: dict) -> float | None:
    if not (_cluster_video_ids(left) & _cluster_video_ids(right)):
        return None

    left_start, left_end = _cluster_time_bounds(left)
    right_start, right_end = _cluster_time_bounds(right)
    if left_end < right_start:
        return right_start - left_end
    if right_end < left_start:
        return left_start - right_end
    return 0.0


def _has_same_frame_conflict(left: dict, right: dict) -> bool:
    left_keys = {_frame_key(record) for record in left["records"]}
    return any(_frame_key(record) in left_keys for record in right["records"])


def _max_pair_similarity(left: dict, right: dict) -> float:
    best = -1.0
    for left_record in left["records"]:
        for right_record in right["records"]:
            best = max(best, cosine_similarity(left_record["embedding"], right_record["embedding"]))
    return best


def _merge_pose_fragments(clusters: list[dict]) -> tuple[list[dict], int]:
    merged = [_make_cluster(cluster["records"]) for cluster in clusters]
    merge_count = 0

    while True:
        best_pair: tuple[float, int, int] | None = None
        for left_index, left in enumerate(merged):
            for right_index, right in enumerate(merged[left_index + 1 :], start=left_index + 1):
                if _has_same_frame_conflict(left, right):
                    continue

                left_size = len(left["records"])
                right_size = len(right["records"])
                smaller_size = min(left_size, right_size)
                centroid_similarity = cosine_similarity(left["embedding"], right["embedding"])
                pair_similarity = _max_pair_similarity(left, right)
                time_gap = _cluster_time_gap(left, right)

                is_pose_fragment = smaller_size <= 8
                has_strong_embedding_bridge = centroid_similarity >= 0.74 and pair_similarity >= 0.76
                has_nearby_pose_bridge = (
                    time_gap is not None
                    and time_gap <= 12.0
                    and pair_similarity >= 0.62
                    and centroid_similarity >= 0.40
                )

                if is_pose_fragment and (has_strong_embedding_bridge or has_nearby_pose_bridge):
                    score = max(centroid_similarity, pair_similarity)
                    if best_pair is None or score > best_pair[0]:
                        best_pair = (score, left_index, right_index)

        if best_pair is None:
            break

        _, left_index, right_index = best_pair
        records = merged[left_index]["records"] + merged[right_index]["records"]
        merged[left_index] = _make_cluster(records)
        del merged[right_index]
        merge_count += 1

    return merged, merge_count


def _graph_clusters(records: list[dict], threshold: float) -> list[dict]:
    if not records:
        return []

    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(records):
        for right_index, right in enumerate(records[left_index + 1 :], start=left_index + 1):
            if _frame_key(left) == _frame_key(right):
                continue
            if cosine_similarity(left["embedding"], right["embedding"]) >= threshold:
                union(left_index, right_index)

    components: dict[int, list[dict]] = {}
    for index, record in enumerate(records):
        components.setdefault(find(index), []).append(record)
    return [_make_cluster(component) for component in components.values()]


def _same_frame_conflicts(clusters: list[dict]) -> int:
    conflicts = 0
    for cluster in clusters:
        seen = set()
        for record in cluster["records"]:
            key = _frame_key(record)
            if key in seen:
                conflicts += 1
            seen.add(key)
    return conflicts


def _mean_intra_similarity(cluster: dict) -> float:
    records = cluster["records"]
    if len(records) <= 1:
        return 1.0
    scores = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            scores.append(cosine_similarity(left["embedding"], right["embedding"]))
    return float(sum(scores) / len(scores)) if scores else 0.0


def _max_inter_similarity(clusters: list[dict]) -> float:
    if len(clusters) <= 1:
        return 0.0
    scores = []
    for left_index, left in enumerate(clusters):
        for right in clusters[left_index + 1 :]:
            scores.append(cosine_similarity(left["embedding"], right["embedding"]))
    return float(max(scores)) if scores else 0.0


def _cluster_quality(clusters: list[dict], eligible_faces: int, min_faces: int) -> dict:
    selected = [cluster for cluster in clusters if len(cluster["records"]) >= min_faces]
    linked_faces = sum(len(cluster["records"]) for cluster in selected)
    coverage = linked_faces / eligible_faces if eligible_faces else 0.0
    mean_intra = (
        sum(_mean_intra_similarity(cluster) for cluster in selected) / len(selected)
        if selected
        else 0.0
    )
    max_inter = _max_inter_similarity(selected)
    conflicts = _same_frame_conflicts(selected)
    singleton_ratio = (
        sum(1 for cluster in clusters if len(cluster["records"]) == 1) / len(clusters)
        if clusters
        else 1.0
    )
    score = (
        0.45 * mean_intra
        + 0.25 * max(0.0, 1.0 - max_inter)
        + 0.20 * coverage
        + 0.10 * max(0.0, 1.0 - singleton_ratio)
        - 0.25 * conflicts
    )
    return {
        "score": round(score, 6),
        "mean_intra_similarity": round(mean_intra, 6),
        "max_inter_similarity": round(max_inter, 6),
        "coverage": round(coverage, 6),
        "same_frame_conflicts": conflicts,
        "singleton_ratio": round(singleton_ratio, 6),
        "selected_clusters": len(selected),
    }


def _cluster_stats(cluster: dict) -> dict:
    records = cluster["records"]
    areas = [_bbox_area(record) for record in records]
    scores = [_detection_score(record) for record in records]
    start_sec, end_sec = _cluster_time_bounds(cluster)
    return {
        "faces": len(records),
        "mean_area": float(sum(areas) / len(areas)) if areas else 0.0,
        "mean_detection_score": float(sum(scores) / len(scores)) if scores else 0.0,
        "time_span_sec": max(0.0, end_sec - start_sec),
        "mean_intra_similarity": _mean_intra_similarity(cluster),
    }


def _recover_weak_stable_clusters(
    records: list[dict],
    selected: list[dict],
    *,
    min_face_area: float,
    weak_min_detection_score: float = 0.55,
    weak_threshold: float = 0.52,
    weak_min_faces: int = 4,
) -> tuple[list[dict], dict]:
    selected_face_ids = {
        record["face_id"] for cluster in selected for record in cluster["records"]
    }
    candidates = [
        record
        for record in records
        if record["face_id"] not in selected_face_ids
        and _is_quality_face(
            record,
            min_face_area=min_face_area,
            min_detection_score=weak_min_detection_score,
        )
    ]
    if not candidates:
        return [], {
            "weak_candidates": 0,
            "weak_candidate_clusters": 0,
            "weak_recovered_clusters": 0,
            "weak_recovered_faces": 0,
            "weak_threshold": weak_threshold,
            "weak_min_detection_score": weak_min_detection_score,
        }

    weak_clusters = _graph_clusters(candidates, weak_threshold)
    weak_clusters, weak_pose_fragment_merges = _merge_pose_fragments(weak_clusters)
    recovered = []
    skipped = {
        "too_small": 0,
        "too_short": 0,
        "too_similar_to_existing": 0,
        "low_quality": 0,
    }

    for cluster in weak_clusters:
        stats = _cluster_stats(cluster)
        if stats["faces"] < weak_min_faces:
            skipped["too_small"] += 1
            continue
        if stats["time_span_sec"] < 2.0:
            skipped["too_short"] += 1
            continue

        if selected:
            max_centroid_similarity = max(
                cosine_similarity(cluster["embedding"], existing["embedding"])
                for existing in selected
            )
            max_pair_similarity = max(
                _max_pair_similarity(cluster, existing) for existing in selected
            )
        else:
            max_centroid_similarity = 0.0
            max_pair_similarity = 0.0

        if max_centroid_similarity >= 0.78 or max_pair_similarity >= 0.78:
            skipped["too_similar_to_existing"] += 1
            continue

        is_regular_stable = (
            stats["mean_detection_score"] >= 0.65
            and stats["mean_intra_similarity"] >= 0.68
        )
        is_small_face_stable = (
            stats["mean_detection_score"] >= 0.65
            and stats["mean_area"] <= 4500.0
            and stats["mean_intra_similarity"] >= 0.48
        )
        if not (is_regular_stable or is_small_face_stable):
            skipped["low_quality"] += 1
            continue

        recovered.append(cluster)

    return recovered, {
        "weak_candidates": len(candidates),
        "weak_candidate_clusters": len(weak_clusters),
        "weak_recovered_clusters": len(recovered),
        "weak_recovered_faces": sum(len(cluster["records"]) for cluster in recovered),
        "weak_threshold": weak_threshold,
        "weak_min_detection_score": weak_min_detection_score,
        "weak_pose_fragment_merges": weak_pose_fragment_merges,
        "weak_skipped": skipped,
    }


def _auto_graph_clusters(records: list[dict], min_faces: int) -> tuple[list[dict], float, dict]:
    candidates = [float(round(value, 2)) for value in np.arange(0.9, 0.59, -0.02)]
    best_clusters: list[dict] = []
    best_threshold = candidates[0]
    best_quality: dict | None = None

    for threshold in candidates:
        clusters = _graph_clusters(records, threshold)
        quality = _cluster_quality(clusters, len(records), min_faces)
        if best_quality is None or quality["score"] > best_quality["score"]:
            best_clusters = clusters
            best_threshold = threshold
            best_quality = quality

    assert best_quality is not None
    return best_clusters, best_threshold, best_quality


def _cluster_representative(cluster: dict) -> dict:
    return max(
        cluster["records"],
        key=lambda record: cosine_similarity(record["embedding"], cluster["embedding"]),
    )


def _upsert_person_from_records(person_id: str, records: list[dict], display_name: str | None = None) -> dict:
    cluster = _make_cluster(records)
    representative = _cluster_representative(cluster)
    return db.update_person(
        person_id,
        {
            "display_name": display_name,
            "representative_face_id": representative["face_id"],
            "representative_frame_path": representative["frame_path"],
            "embedding": cluster["embedding"],
            "face_count": len(cluster["records"]),
            "first_seen_at": _first_seen(cluster["records"]),
            "last_seen_at": _last_seen(cluster["records"]),
        },
    )


def _create_person_from_cluster(cluster: dict, display_name: str | None = None) -> tuple[dict, int]:
    representative = _cluster_representative(cluster)
    person = db.add_person(
        {
            "person_id": "person_" + uuid.uuid4().hex,
            "display_name": display_name,
            "representative_face_id": representative["face_id"],
            "representative_frame_path": representative["frame_path"],
            "embedding": cluster["embedding"],
            "face_count": len(cluster["records"]),
            "first_seen_at": _first_seen(cluster["records"]),
            "last_seen_at": _last_seen(cluster["records"]),
        }
    )
    linked_faces = 0
    for record in cluster["records"]:
        score_to_person = cluster["scores"].get(record["face_id"])
        if score_to_person is None:
            score_to_person = round(cosine_similarity(record["embedding"], cluster["embedding"]), 6)
        db.add_person_face(person["person_id"], record["face_id"], score_to_person)
        linked_faces += 1
    return person, linked_faces


def _best_existing_person_candidate(cluster: dict, persons: list[dict]) -> dict | None:
    best: tuple[float, dict] | None = None
    for person in persons:
        centroid_similarity = cosine_similarity(cluster["embedding"], person["embedding"])
        person_records = db.list_face_records_for_person(person["person_id"])
        person_cluster = _make_cluster(person_records) if person_records else None
        has_conflict = person_cluster is not None and _has_same_frame_conflict(cluster, person_cluster)
        if has_conflict:
            continue

        if best is None or centroid_similarity > best[0]:
            best = (centroid_similarity, person)
    if best is None:
        return None
    return {"score": best[0], "person": best[1]}


def _best_existing_person_match(cluster: dict, persons: list[dict], threshold: float) -> dict | None:
    candidate = _best_existing_person_candidate(cluster, persons)
    if candidate is None or float(candidate["score"]) < threshold:
        return None
    return candidate["person"]


def _cluster_has_same_frame_conflict(cluster: dict) -> bool:
    return _same_frame_conflicts([cluster]) > 0


def _candidate_person_display_name(prefix: str | None, cluster: dict) -> str | None:
    if not prefix:
        return None
    face_ids = ",".join(sorted(str(record["face_id"]) for record in cluster["records"]))
    digest = sha1(face_ids.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def _select_clusters_with_guards(
    clusters: list[dict],
    *,
    min_faces: int,
    min_cluster_mean_similarity: float = 0.0,
) -> tuple[list[dict], dict]:
    selected = []
    skipped = {
        "too_small_clusters": 0,
        "too_small_faces": 0,
        "same_frame_conflict_clusters": 0,
        "same_frame_conflict_faces": 0,
        "low_intra_similarity_clusters": 0,
        "low_intra_similarity_faces": 0,
    }
    for cluster in clusters:
        face_count = len(cluster["records"])
        if face_count < min_faces:
            skipped["too_small_clusters"] += 1
            skipped["too_small_faces"] += face_count
            continue
        if _cluster_has_same_frame_conflict(cluster):
            skipped["same_frame_conflict_clusters"] += 1
            skipped["same_frame_conflict_faces"] += face_count
            continue
        if min_cluster_mean_similarity > 0.0:
            mean_intra = _mean_intra_similarity(cluster)
            if mean_intra < min_cluster_mean_similarity:
                skipped["low_intra_similarity_clusters"] += 1
                skipped["low_intra_similarity_faces"] += face_count
                continue
        selected.append(cluster)
    return selected, skipped


def rebuild_person_index(
    merge_threshold: float | None = None,
    min_faces: int = 2,
    min_face_area: float = 2500.0,
    min_detection_score: float = 0.85,
    use_pose_fragment_merge: bool = True,
    recover_weak_stable: bool = True,
    min_cluster_mean_similarity: float = 0.0,
) -> dict:
    records = db.list_face_records()
    min_faces = int(min_faces)
    quality_records = [
        record
        for record in records
        if _is_quality_face(record, min_face_area=min_face_area, min_detection_score=min_detection_score)
    ]
    low_quality_faces = len(records) - len(quality_records)

    if merge_threshold is None:
        clusters, threshold, quality = _auto_graph_clusters(quality_records, min_faces=min_faces)
        if use_pose_fragment_merge:
            clusters, pose_fragment_merges = _merge_pose_fragments(clusters)
        else:
            pose_fragment_merges = 0
        quality = _cluster_quality(clusters, len(quality_records), min_faces)
        quality["pose_fragment_merges"] = pose_fragment_merges
        algorithm = "graph_auto_threshold"
    else:
        threshold = float(merge_threshold)
        clusters = _graph_clusters(quality_records, threshold)
        quality = _cluster_quality(clusters, len(quality_records), min_faces=min_faces)
        quality["pose_fragment_merges"] = 0
        algorithm = "graph_threshold"

    selected, selection_skips = _select_clusters_with_guards(
        clusters,
        min_faces=min_faces,
        min_cluster_mean_similarity=min_cluster_mean_similarity,
    )
    if recover_weak_stable:
        recovered, recovery_quality = _recover_weak_stable_clusters(
            records,
            selected,
            min_face_area=min_face_area,
        )
    else:
        recovered = []
        recovery_quality = {
            "weak_recovery_enabled": False,
            "weak_recovered_clusters": 0,
            "weak_recovered_faces": 0,
        }
    selected = selected + recovered
    quality |= recovery_quality
    quality |= {
        "selection_skips": selection_skips,
        "use_pose_fragment_merge": use_pose_fragment_merge,
        "recover_weak_stable": recover_weak_stable,
        "min_cluster_mean_similarity": min_cluster_mean_similarity,
    }
    linked_face_ids = {
        record["face_id"] for cluster in selected for record in cluster["records"]
    }
    noise_faces = len(records) - len(linked_face_ids)

    db.clear_person_index()
    linked_faces = 0

    for cluster in selected:
        _, added_faces = _create_person_from_cluster(cluster)
        linked_faces += added_faces

    video_ids = {str(record.get("video_id") or "") for cluster in selected for record in cluster["records"]}
    if video_ids:
        from app.services import event_service

        event_service.rebuild_events_for_videos(video_ids)

    return {
        "persons": len(selected),
        "linked_faces": linked_faces,
        "source_faces": len(records),
        "merge_threshold": threshold,
        "min_faces": min_faces,
        "min_face_area": min_face_area,
        "min_detection_score": min_detection_score,
        "low_quality_faces": low_quality_faces,
        "noise_faces": noise_faces,
        "cluster_quality": quality,
        "algorithm": algorithm + "+weak_stable_recovery" if recovered else algorithm,
    }


def update_person_index(
    merge_threshold: float | None = 0.80,
    person_match_threshold: float = 0.82,
    ambiguous_person_match_threshold: float | None = 0.78,
    min_faces: int = 4,
    min_face_area: float = 2500.0,
    min_detection_score: float = 0.85,
    camera_id_prefix: str | None = None,
    create_unmatched_persons: bool = True,
    candidate_display_name_prefix: str | None = None,
    use_pose_fragment_merge: bool = False,
    recover_weak_stable: bool = False,
    min_cluster_mean_similarity: float = 0.0,
    dry_run: bool = False,
) -> dict:
    records = db.list_unassigned_face_records()
    if camera_id_prefix:
        records = [
            record
            for record in records
            if str(record.get("camera_id") or "").startswith(camera_id_prefix)
        ]
    min_faces = int(min_faces)
    quality_records = [
        record
        for record in records
        if _is_quality_face(record, min_face_area=min_face_area, min_detection_score=min_detection_score)
    ]
    low_quality_faces = len(records) - len(quality_records)

    if merge_threshold is None:
        clusters, threshold, quality = _auto_graph_clusters(quality_records, min_faces=min_faces)
        if use_pose_fragment_merge:
            clusters, pose_fragment_merges = _merge_pose_fragments(clusters)
        else:
            pose_fragment_merges = 0
        quality = _cluster_quality(clusters, len(quality_records), min_faces)
        quality["pose_fragment_merges"] = pose_fragment_merges
        algorithm = "incremental_graph_auto_threshold"
    else:
        threshold = float(merge_threshold)
        clusters = _graph_clusters(quality_records, threshold)
        quality = _cluster_quality(clusters, len(quality_records), min_faces=min_faces)
        quality["pose_fragment_merges"] = 0
        algorithm = "incremental_graph_threshold"

    selected, selection_skips = _select_clusters_with_guards(
        clusters,
        min_faces=min_faces,
        min_cluster_mean_similarity=min_cluster_mean_similarity,
    )
    if recover_weak_stable:
        recovered, recovery_quality = _recover_weak_stable_clusters(
            records,
            selected,
            min_face_area=min_face_area,
        )
    else:
        recovered = []
        recovery_quality = {
            "weak_recovery_enabled": False,
            "weak_recovered_clusters": 0,
            "weak_recovered_faces": 0,
        }
    selected = selected + recovered
    existing_persons = db.list_persons()
    created_persons = 0
    updated_persons: set[str] = set()
    linked_faces = 0
    skipped_ambiguous_clusters = 0
    skipped_ambiguous_faces = 0
    skipped_unmatched_clusters = 0
    skipped_unmatched_faces = 0
    cluster_decisions = []
    if ambiguous_person_match_threshold is not None:
        ambiguous_person_match_threshold = min(
            float(ambiguous_person_match_threshold),
            float(person_match_threshold),
        )

    for cluster in selected:
        best_candidate = _best_existing_person_candidate(cluster, existing_persons)
        best_score = float(best_candidate["score"]) if best_candidate is not None else None
        match = best_candidate["person"] if best_candidate is not None else None
        face_count = len(cluster["records"])
        decision = {
            "faces": face_count,
            "mean_intra_similarity": round(_mean_intra_similarity(cluster), 6),
            "best_existing_person_id": match.get("person_id") if match else None,
            "best_existing_score": round(best_score, 6) if best_score is not None else None,
        }

        if match is not None and best_score is not None and best_score >= person_match_threshold:
            decision["action"] = "merge_existing"
        elif (
            match is not None
            and best_score is not None
            and ambiguous_person_match_threshold is not None
            and best_score >= ambiguous_person_match_threshold
        ):
            skipped_ambiguous_clusters += 1
            skipped_ambiguous_faces += face_count
            decision["action"] = "skip_ambiguous_existing"
            cluster_decisions.append(decision)
            continue
        elif not create_unmatched_persons:
            skipped_unmatched_clusters += 1
            skipped_unmatched_faces += face_count
            decision["action"] = "skip_unmatched_new_person_disabled"
            cluster_decisions.append(decision)
            continue
        else:
            display_name = _candidate_person_display_name(candidate_display_name_prefix, cluster)
            decision["action"] = "create_candidate_person"
            decision["display_name"] = display_name
            if dry_run:
                existing_persons.append(
                    {
                        "person_id": f"dry_run_candidate_{created_persons + 1}",
                        "display_name": display_name,
                        "embedding": cluster["embedding"],
                    }
                )
                created_persons += 1
                linked_faces += face_count
                cluster_decisions.append(decision)
                continue

            person, added_faces = _create_person_from_cluster(cluster, display_name=display_name)
            existing_persons.append(person)
            created_persons += 1
            linked_faces += added_faces
            cluster_decisions.append(decision)
            continue

        assert match is not None
        if dry_run:
            updated_persons.add(match["person_id"])
            linked_faces += face_count
            cluster_decisions.append(decision)
            continue

        for record in cluster["records"]:
            score_to_person = round(cosine_similarity(record["embedding"], match["embedding"]), 6)
            db.add_person_face(match["person_id"], record["face_id"], score_to_person)
            linked_faces += 1

        all_records = db.list_face_records_for_person(match["person_id"])
        updated = _upsert_person_from_records(
            match["person_id"],
            all_records,
            display_name=match.get("display_name"),
        )
        updated_persons.add(match["person_id"])
        existing_persons = [updated if person["person_id"] == updated["person_id"] else person for person in existing_persons]
        cluster_decisions.append(decision)

    skipped_face_ids = set()
    for decision, cluster in zip(cluster_decisions, selected):
        if str(decision.get("action") or "").startswith("skip_"):
            skipped_face_ids.update(record["face_id"] for record in cluster["records"])
    linked_face_ids = {
        record["face_id"]
        for cluster in selected
        for record in cluster["records"]
        if record["face_id"] not in skipped_face_ids
    }
    noise_faces = len(records) - len(linked_face_ids)
    video_ids = {str(record.get("video_id") or "") for cluster in selected for record in cluster["records"]}
    event_update_result = None
    if video_ids and not dry_run:
        from app.services import event_service

        event_update_result = event_service.rebuild_events_for_videos(video_ids)

    return {
        "persons": len(db.list_persons()) + (created_persons if dry_run else 0),
        "linked_faces": linked_faces,
        "source_faces": len(records),
        "merge_threshold": threshold,
        "min_faces": min_faces,
        "min_face_area": min_face_area,
        "min_detection_score": min_detection_score,
        "low_quality_faces": low_quality_faces,
        "noise_faces": noise_faces,
        "cluster_quality": quality | recovery_quality | {
            "created_persons": created_persons,
            "updated_persons": len(updated_persons),
            "skipped_ambiguous_clusters": skipped_ambiguous_clusters,
            "skipped_ambiguous_faces": skipped_ambiguous_faces,
            "skipped_unmatched_clusters": skipped_unmatched_clusters,
            "skipped_unmatched_faces": skipped_unmatched_faces,
            "selection_skips": selection_skips,
            "person_match_threshold": person_match_threshold,
            "ambiguous_person_match_threshold": ambiguous_person_match_threshold,
            "camera_id_prefix": camera_id_prefix,
            "create_unmatched_persons": create_unmatched_persons,
            "candidate_display_name_prefix": candidate_display_name_prefix,
            "use_pose_fragment_merge": use_pose_fragment_merge,
            "recover_weak_stable": recover_weak_stable,
            "min_cluster_mean_similarity": min_cluster_mean_similarity,
            "dry_run": dry_run,
            "cluster_decisions": cluster_decisions,
            "event_update_result": event_update_result,
        },
        "algorithm": algorithm + "+weak_stable_recovery" if recovered else algorithm,
    }


def _person_records_cluster(person_id: str) -> dict | None:
    records = db.list_face_records_for_person(person_id)
    return _make_cluster(records) if records else None


def _strong_person_colors(person_id: str, prefix: str) -> dict[str, int]:
    from app.services import event_service

    colors: dict[str, int] = {}
    for event in event_service.list_events(person_id=person_id, limit=5000):
        color = event.get(f"{prefix}_color")
        confidence = event.get(f"{prefix}_color_confidence")
        visible = event.get(f"{prefix}_visible")
        if not visible or not color or color == "unknown" or confidence is None:
            continue
        if float(confidence) < 0.75:
            continue
        colors[color] = colors.get(color, 0) + 1
    return colors


def _has_strong_clothing_conflict(source_person_id: str, target_person_id: str) -> bool:
    prefixes = ("upper", "lower") if getattr(settings, "enable_lower_clothing_core", False) else ("upper",)
    for prefix in prefixes:
        source_colors = _strong_person_colors(source_person_id, prefix)
        target_colors = _strong_person_colors(target_person_id, prefix)
        if not source_colors or not target_colors:
            continue
        source_color, source_support = max(source_colors.items(), key=lambda item: item[1])
        target_color, target_support = max(target_colors.items(), key=lambda item: item[1])
        if source_support >= 1 and target_support >= 2 and source_color != target_color:
            return True
    return False


def _merge_fragment_metrics(
    source_person: dict,
    target_person: dict,
    target_persons: list[dict],
    *,
    merge_scorer_model: dict | None = None,
) -> dict:
    source_cluster = _person_records_cluster(source_person["person_id"])
    target_cluster = _person_records_cluster(target_person["person_id"])
    if source_cluster is None or target_cluster is None:
        return {
            "source_person_id": source_person["person_id"],
            "target_person_id": target_person["person_id"],
            "centroid_similarity": 0.0,
            "max_pair_similarity": 0.0,
            "top5_pair_similarity": 0.0,
            "nearest_margin": 0.0,
            "same_frame_conflict": True,
            "strong_clothing_conflict": False,
        }

    other_person_embeddings = [
        person["embedding"]
        for person in target_persons
        if person["person_id"] not in {source_person["person_id"], target_person["person_id"]}
    ]
    similarities = []
    for person in target_persons:
        if person["person_id"] in {source_person["person_id"], target_person["person_id"]}:
            continue
        similarities.append(cosine_similarity(source_cluster["embedding"], person["embedding"]))
    second_best = max(similarities) if similarities else -1.0

    pair_scores = [
        cosine_similarity(source_record["embedding"], target_record["embedding"])
        for source_record in source_cluster["records"]
        for target_record in target_cluster["records"]
    ]
    pair_scores.sort(reverse=True)
    centroid_similarity = cosine_similarity(source_cluster["embedding"], target_cluster["embedding"])
    top5_count = min(5, len(pair_scores))
    metrics = {
        "source_person_id": source_person["person_id"],
        "source_display_name": source_person.get("display_name"),
        "source_faces": len(source_cluster["records"]),
        "target_person_id": target_person["person_id"],
        "target_display_name": target_person.get("display_name"),
        "target_faces": len(target_cluster["records"]),
        "centroid_similarity": round(float(centroid_similarity), 6),
        "max_pair_similarity": round(float(pair_scores[0] if pair_scores else 0.0), 6),
        "top5_pair_similarity": round(float(sum(pair_scores[:top5_count]) / top5_count), 6)
        if top5_count
        else 0.0,
        "nearest_margin": round(float(centroid_similarity - second_best), 6),
        "second_best_similarity": round(float(second_best), 6),
        "same_frame_conflict": _has_same_frame_conflict(source_cluster, target_cluster),
        "strong_clothing_conflict": _has_strong_clothing_conflict(
            source_person["person_id"],
            target_person["person_id"],
        ),
    }
    if merge_scorer_model is not None:
        features = person_merge_scorer.build_pair_features(
            source_cluster["records"],
            target_cluster["records"],
            other_person_embeddings=other_person_embeddings,
        )
        probability = person_merge_scorer.predict_probability(merge_scorer_model, features)
        metrics["merge_probability"] = round(float(probability), 6)
        metrics["merge_model_version"] = merge_scorer_model.get("model_version")
        metrics["merge_model_threshold"] = merge_scorer_model.get("threshold")
        metrics["merge_features"] = {
            key: round(float(value), 6)
            for key, value in features.items()
        }
    return metrics


def _best_fragment_target(
    source_person: dict,
    target_persons: list[dict],
    *,
    comparison_persons: list[dict] | None = None,
    merge_scorer_model: dict | None = None,
) -> tuple[dict | None, dict | None]:
    source_cluster = _person_records_cluster(source_person["person_id"])
    if source_cluster is None:
        return None, None

    comparison_persons = comparison_persons or target_persons
    best_person = None
    best_score: tuple[float, float] = (-1.0, -1.0)
    best_metrics = None
    for person in target_persons:
        if person["person_id"] == source_person["person_id"]:
            continue
        metrics = _merge_fragment_metrics(
            source_person,
            person,
            comparison_persons,
            merge_scorer_model=merge_scorer_model,
        )
        score = (
            float(metrics.get("merge_probability") or 0.0),
            float(metrics.get("centroid_similarity") or 0.0),
        ) if merge_scorer_model is not None else (
            float(metrics.get("centroid_similarity") or 0.0),
            float(metrics.get("max_pair_similarity") or 0.0),
        )
        if score > best_score:
            best_score = score
            best_person = person
            best_metrics = metrics

    if best_person is None:
        return None, None
    return best_person, best_metrics


def _passes_auto_fragment_merge_guards(
    metrics: dict,
    *,
    min_centroid_similarity: float,
    min_max_pair_similarity: float,
    min_nearest_margin: float,
    use_clothing_conflict_guard: bool = False,
    min_merge_probability: float | None = None,
) -> tuple[bool, str]:
    if metrics["same_frame_conflict"]:
        return False, "same_frame_conflict"
    if use_clothing_conflict_guard and metrics["strong_clothing_conflict"]:
        return False, "strong_clothing_conflict"
    if float(metrics["centroid_similarity"]) < min_centroid_similarity:
        return False, "low_centroid_similarity"
    if float(metrics["max_pair_similarity"]) < min_max_pair_similarity:
        return False, "low_max_pair_similarity"
    if float(metrics["nearest_margin"]) < min_nearest_margin:
        return False, "low_nearest_margin"
    if min_merge_probability is not None:
        probability = metrics.get("merge_probability")
        if probability is None:
            return False, "missing_merge_probability"
        if float(probability) < min_merge_probability:
            return False, "low_merge_probability"
    return True, "passed"


def merge_person_into(
    *,
    source_person_id: str,
    target_person_id: str,
    dry_run: bool = False,
) -> dict:
    source = db.get_person(source_person_id)
    target = db.get_person(target_person_id)
    if source is None:
        raise KeyError(f"source person not found: {source_person_id}")
    if target is None:
        raise KeyError(f"target person not found: {target_person_id}")

    source_records = db.list_face_records_for_person(source_person_id)
    target_records = db.list_face_records_for_person(target_person_id)
    touched_video_ids = {
        str(record.get("video_id") or "")
        for record in source_records + target_records
        if record.get("video_id")
    }
    metrics = _merge_fragment_metrics(source, target, [person for person in db.list_persons() if person["person_id"] != source_person_id])

    if dry_run:
        return {
            "dry_run": True,
            "source_person_id": source_person_id,
            "target_person_id": target_person_id,
            "moved_faces": len(source_records),
            "video_ids": sorted(touched_video_ids),
            "metrics": metrics,
            "event_update_result": None,
        }

    merge_result = db.merge_person_into(source_person_id, target_person_id)
    all_records = db.list_face_records_for_person(target_person_id)
    updated = _upsert_person_from_records(
        target_person_id,
        all_records,
        display_name=target.get("display_name"),
    )
    for record in all_records:
        db.update_person_face_score(
            target_person_id,
            record["face_id"],
            round(cosine_similarity(record["embedding"], updated["embedding"]), 6),
        )

    event_update_result = None
    if touched_video_ids:
        from app.services import event_service

        event_update_result = event_service.rebuild_events_for_videos(touched_video_ids)

    return {
        "dry_run": False,
        "source_person_id": source_person_id,
        "target_person_id": target_person_id,
        "moved_faces": merge_result["moved_faces"],
        "moved_observations": merge_result["moved_observations"],
        "moved_events": merge_result["moved_events"],
        "deleted_sessions": merge_result["deleted_sessions"],
        "video_ids": sorted(touched_video_ids),
        "metrics": metrics,
        "target_person": updated,
        "event_update_result": event_update_result,
    }


def auto_consolidate_person_fragments(
    *,
    source_display_prefix: str = "candidate_",
    include_all_small_sources: bool = False,
    max_source_faces: int = 3,
    min_target_faces: int = 5,
    min_centroid_similarity: float = 0.64,
    min_max_pair_similarity: float = 0.55,
    min_nearest_margin: float = 0.35,
    use_clothing_conflict_guard: bool = False,
    use_merge_scorer: bool = False,
    merge_scorer_model_path: str | None = None,
    min_merge_probability: float | None = None,
    dry_run: bool = True,
) -> dict:
    persons = db.list_persons()
    merge_scorer_model = (
        person_merge_scorer.load_model(merge_scorer_model_path)
        if use_merge_scorer
        else None
    )
    if use_merge_scorer and min_merge_probability is None and merge_scorer_model is not None:
        min_merge_probability = float(merge_scorer_model.get("threshold") or 0.85)
    if include_all_small_sources:
        sources = [
            person
            for person in persons
            if int(person.get("face_count") or 0) <= max_source_faces
        ]
    else:
        sources = [
            person
            for person in persons
            if str(person.get("display_name") or "").startswith(source_display_prefix)
            and int(person.get("face_count") or 0) <= max_source_faces
        ]
    source_ids = {person["person_id"] for person in sources}
    targets = [
        person
        for person in persons
        if person["person_id"] not in source_ids
        and int(person.get("face_count") or 0) >= min_target_faces
    ]

    decisions = []
    merged = []
    skipped = []
    consumed_sources: set[str] = set()
    for source in sources:
        if source["person_id"] in consumed_sources:
            continue
        target, metrics = _best_fragment_target(
            source,
            targets,
            comparison_persons=persons,
            merge_scorer_model=merge_scorer_model,
        )
        if target is None or metrics is None:
            skipped.append({"source_person_id": source["person_id"], "reason": "no_target"})
            continue
        passed, reason = _passes_auto_fragment_merge_guards(
            metrics,
            min_centroid_similarity=min_centroid_similarity,
            min_max_pair_similarity=min_max_pair_similarity,
            min_nearest_margin=min_nearest_margin,
            use_clothing_conflict_guard=use_clothing_conflict_guard,
            min_merge_probability=min_merge_probability,
        )
        decision = metrics | {"action": "merge" if passed else "skip", "reason": reason}
        decisions.append(decision)
        if not passed:
            skipped.append(decision)
            continue

        merge_result = merge_person_into(
            source_person_id=source["person_id"],
            target_person_id=target["person_id"],
            dry_run=dry_run,
        )
        merge_result["metrics"] = metrics
        merged.append(merge_result)
        consumed_sources.add(source["person_id"])

    return {
        "dry_run": dry_run,
        "source_display_prefix": source_display_prefix,
        "include_all_small_sources": include_all_small_sources,
        "max_source_faces": max_source_faces,
        "min_target_faces": min_target_faces,
        "min_centroid_similarity": min_centroid_similarity,
        "min_max_pair_similarity": min_max_pair_similarity,
        "min_nearest_margin": min_nearest_margin,
        "use_clothing_conflict_guard": use_clothing_conflict_guard,
        "use_merge_scorer": use_merge_scorer,
        "merge_scorer_model_path": str(merge_scorer_model_path) if merge_scorer_model_path else None,
        "min_merge_probability": min_merge_probability,
        "source_candidates": len(sources),
        "target_candidates": len(targets),
        "merge_count": len(merged),
        "skip_count": len(skipped),
        "decisions": decisions,
        "merged": merged,
        "skipped": skipped,
        "persons": len(db.list_persons()),
    }


def _event_representative(records: list[dict]) -> dict:
    return max(
        records,
        key=lambda record: (
            _detection_score(record),
            _bbox_area(record),
            -float(record.get("video_timestamp_sec") or 0.0),
        ),
    )


def _record_time_delta_sec(previous: dict, current: dict) -> float | None:
    previous_captured = _parse_iso_seconds(previous.get("captured_at"))
    current_captured = _parse_iso_seconds(current.get("captured_at"))
    if previous_captured is not None and current_captured is not None:
        return current_captured - previous_captured

    if previous.get("video_id") == current.get("video_id"):
        return float(current.get("video_timestamp_sec") or 0.0) - float(
            previous.get("video_timestamp_sec") or 0.0
        )
    return None


def _event_id(person_id: str, event: dict) -> str:
    raw = "|".join(
        [
            person_id,
            str(event.get("camera_id") or ""),
            str(event.get("video_id") or ""),
            str(event.get("start_time") or ""),
            str(event.get("end_time") or ""),
            f"{float(event.get('start_timestamp_sec') or 0.0):.3f}",
            f"{float(event.get('end_timestamp_sec') or 0.0):.3f}",
            str(event.get("representative_face_id") or ""),
        ]
    )
    return "event_" + sha1(raw.encode("utf-8")).hexdigest()[:16]


def _person_event_from_records(person_id: str, records: list[dict], cameras: dict[str, dict]) -> dict:
    representative = _event_representative(records)
    camera_id = str(representative.get("camera_id") or "")
    camera = cameras.get(camera_id, {})

    captured_values = [record.get("captured_at") for record in records if record.get("captured_at")]
    timestamp_values = [float(record.get("video_timestamp_sec") or 0.0) for record in records]
    start_timestamp = min(timestamp_values) if timestamp_values else None
    end_timestamp = max(timestamp_values) if timestamp_values else None
    duration = (
        round(max(0.0, float(end_timestamp) - float(start_timestamp)), 3)
        if start_timestamp is not None and end_timestamp is not None
        else None
    )

    event = {
        "event_id": "",
        "person_id": person_id,
        "camera_id": camera_id,
        "camera_name": camera.get("name"),
        "location": camera.get("location"),
        "video_id": representative.get("video_id"),
        "start_time": min(captured_values) if captured_values else None,
        "end_time": max(captured_values) if captured_values else None,
        "start_timestamp_sec": start_timestamp,
        "end_timestamp_sec": end_timestamp,
        "start_time_display": _time_display(start_timestamp),
        "end_time_display": _time_display(end_timestamp),
        "duration_sec": duration,
        "face_count": len(records),
        "representative_face_id": representative["face_id"],
        "representative_face_crop_url": f"/api/v1/media/face/{representative['face_id']}",
        "representative_frame_url": f"/api/v1/media/frame/{representative['face_id']}",
    }
    event["event_id"] = _event_id(person_id, event)
    return event


def person_events(person_id: str, max_gap_sec: float = 10.0) -> list[dict]:
    records = sorted(db.list_face_records_for_person(person_id), key=_record_event_sort_key)
    if not records:
        return []

    cameras = search_service.camera_lookup()
    gap = max(0.0, float(max_gap_sec))
    groups: list[list[dict]] = []
    current_group: list[dict] = []

    for record in records:
        if not current_group:
            current_group = [record]
            continue

        previous = current_group[-1]
        delta_sec = _record_time_delta_sec(previous, record)
        same_camera = record.get("camera_id") == previous.get("camera_id")
        if same_camera and delta_sec is not None and 0.0 <= delta_sec <= gap:
            current_group.append(record)
            continue

        groups.append(current_group)
        current_group = [record]

    if current_group:
        groups.append(current_group)

    events = [_person_event_from_records(person_id, group, cameras) for group in groups]
    return sorted(
        events,
        key=lambda event: (
            event.get("start_time") or "",
            event.get("camera_id") or "",
            float(event.get("start_timestamp_sec") or 0.0),
        ),
    )


def _persisted_event_for_person(event: dict, person_id: str) -> dict:
    output = {
        "event_id": event["event_id"],
        "person_id": person_id,
        "camera_id": event["camera_id"],
        "camera_name": None,
        "location": None,
        "video_id": event.get("video_id"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "start_timestamp_sec": event.get("start_timestamp_sec"),
        "end_timestamp_sec": event.get("end_timestamp_sec"),
        "start_time_display": _time_display(event.get("start_timestamp_sec")),
        "end_time_display": _time_display(event.get("end_timestamp_sec")),
        "duration_sec": (
            round(float(event["end_timestamp_sec"]) - float(event["start_timestamp_sec"]), 3)
            if event.get("start_timestamp_sec") is not None and event.get("end_timestamp_sec") is not None
            else None
        ),
        "observation_count": int(event.get("observation_count") or 0),
        "face_count": int(event.get("face_count") or 0),
        "representative_observation_id": event.get("representative_observation_id"),
        "representative_face_id": event.get("representative_face_id") or "",
        "representative_frame_path": event.get("representative_frame_path"),
        "representative_face_crop_url": event.get("representative_face_crop_url") or "",
        "representative_frame_url": event.get("representative_frame_url") or "",
        "representative_body_crop_url": event.get("representative_body_crop_url"),
        "body_visibility": event.get("body_visibility"),
        "upper_color": event.get("upper_color"),
        "upper_color_confidence": event.get("upper_color_confidence"),
        "upper_visible": event.get("upper_visible"),
        "identity_confidence": event.get("identity_confidence"),
        "event_status": event.get("event_status"),
        "aggregation_version": event.get("aggregation_version"),
        "created_at": event.get("created_at"),
        "updated_at": event.get("updated_at"),
    }
    for key in (
        "raw_upper_color",
        "raw_upper_color_confidence",
        "raw_upper_visible",
        "normalized_upper_color",
        "normalized_upper_color_confidence",
        "normalized_upper_visible",
        "appearance_session_id",
        "clothing_normalization_version",
        "clothing_normalization_reason",
    ):
        output[key] = event.get(key)
    return output


def _latest_clothing(event: dict | None) -> dict | None:
    if not event:
        return None
    return {
        "event_id": event["event_id"],
        "timestamp": event.get("end_time") or event.get("start_time"),
        "upper_color": event.get("upper_color"),
        "upper_color_confidence": event.get("upper_color_confidence"),
        "upper_visible": event.get("upper_visible"),
        "raw_upper_color": event.get("raw_upper_color"),
        "raw_upper_color_confidence": event.get("raw_upper_color_confidence"),
        "raw_upper_visible": event.get("raw_upper_visible"),
        "normalized_upper_color": event.get("normalized_upper_color"),
        "normalized_upper_color_confidence": event.get("normalized_upper_color_confidence"),
        "normalized_upper_visible": event.get("normalized_upper_visible"),
        "appearance_session_id": event.get("appearance_session_id"),
        "clothing_normalization_version": event.get("clothing_normalization_version"),
    }


def list_persons() -> list[dict]:
    persons = db.list_persons()
    for person in persons:
        persisted_events = db.list_events(person_id=person["person_id"], limit=200)
        if persisted_events:
            events = [_persisted_event_for_person(event, person["person_id"]) for event in persisted_events]
        else:
            events = person_events(person["person_id"])
        person.pop("embedding", None)
        if person.get("representative_face_id"):
            person["representative_face_crop_url"] = (
                f"/api/v1/media/face/{person['representative_face_id']}"
            )
        person["events"] = events
        person["event_count"] = len(events)
        latest_event = persisted_events[-1] if persisted_events else None
        person["latest_event"] = (
            _persisted_event_for_person(latest_event, person["person_id"]) if latest_event else None
        )
        person["latest_clothing"] = _latest_clothing(latest_event)
    return persons


def person_gallery_items() -> list[dict]:
    persons = list_persons()
    for person in persons:
        person["events"] = person.get("events", [])[:12]
    return persons


def _person_matches(
    person_id: str,
    query_embeddings: list[list[float]],
    max_gap_sec: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    cameras = search_service.camera_lookup()
    records = db.list_face_records_for_person(person_id)
    matches = []
    for record in records:
        score = max(cosine_similarity(q, record["embedding"]) for q in query_embeddings)
        matches.append(search_service.build_match(record, score, cameras))
    matches.sort(key=lambda m: m["score"], reverse=True)
    trajectory = search_service.trajectory_from_matches(matches)
    appearance_events = search_service.appearance_events_from_matches(
        matches, max_gap_sec=max_gap_sec
    )
    return matches, trajectory, appearance_events


def search_persons_by_images(
    query_paths: list[str],
    top_k: int = 5,
    min_score: float | None = None,
    max_gap_sec: float = 3.0,
    query_face_index: int | None = None,
) -> dict:
    search_id = uuid.uuid4().hex
    min_score = default_similarity_threshold() if min_score is None else float(min_score)
    query_faces = search_service.detect_query_faces(query_paths)["query_faces"]
    selected_query_face = None
    if query_face_index is not None:
        selected_query_face = next(
            (face for face in query_faces if int(face["index"]) == int(query_face_index)),
            None,
        )
    query_embeddings = search_service.load_embeddings_from_images(query_paths, query_face_index=query_face_index)

    if not query_embeddings:
        if query_face_index is not None and selected_query_face is None:
            warning = "Selected query face was not found in the uploaded image."
        else:
            warning = "No face/target embedding extracted from query images."
        result = {
            "search_id": search_id,
            "engine": get_face_engine().name,
            "query_faces": query_faces,
            "selected_query_face": selected_query_face,
            "persons": [],
            "ambiguous": False,
            "warning": warning,
        }
        db.add_search(
            {
                "search_id": search_id,
                "query_paths": query_paths,
                "params": {
                    "mode": "persons",
                    "top_k": top_k,
                    "min_score": min_score,
                    "max_gap_sec": max_gap_sec,
                    "query_face_index": query_face_index,
                },
                "result": result,
            }
        )
        return result

    scored = []
    for person in db.list_persons():
        records = db.list_face_records_for_person(person["person_id"])
        face_scores = sorted(
            (
                max(cosine_similarity(q, record["embedding"]) for q in query_embeddings)
                for record in records
            ),
            reverse=True,
        )
        centroid_score = max(cosine_similarity(q, person["embedding"]) for q in query_embeddings)
        best_face_score = face_scores[0] if face_scores else centroid_score
        top3_face_score = (
            sum(face_scores[:3]) / min(3, len(face_scores))
            if face_scores
            else centroid_score
        )
        score = max(
            centroid_score,
            0.50 * best_face_score + 0.35 * top3_face_score + 0.15 * centroid_score,
        )
        if score >= min_score:
            person["similarity_score"] = round(float(score), 6)
            person["centroid_score"] = round(float(centroid_score), 6)
            person["best_face_score"] = round(float(best_face_score), 6)
            person["top3_face_score"] = round(float(top3_face_score), 6)
            scored.append((person, round(float(score), 6)))

    scored.sort(key=lambda item: item[1], reverse=True)
    persons = []
    for person, score in scored[: max(1, int(top_k))]:
        matches, trajectory, appearance_events = _person_matches(
            person["person_id"], query_embeddings, max_gap_sec
        )
        person.pop("embedding", None)
        person["score"] = score
        person["matches"] = matches
        person["trajectory"] = trajectory
        person["appearance_events"] = appearance_events
        persons.append(person)

    if persons:
        best_score = persons[0]["score"]
        second_score = persons[1]["score"] if len(persons) > 1 else None
        margin = best_score - second_score if second_score is not None else None
        confidence = "high" if best_score >= confident_similarity_threshold() and (margin is None or margin >= 0.08) else "low"
        ambiguous = second_score is not None and margin is not None and margin < 0.08
        for person in persons:
            person["confidence"] = confidence if person is persons[0] else "candidate"
        warning = None
        if confidence == "low":
            warning = "Low-confidence person match. Candidates are close or below the recommended threshold."
    else:
        warning = "No person matched the requested minimum score."

    result = {
        "search_id": search_id,
        "engine": get_face_engine().name,
        "query_faces": query_faces,
        "selected_query_face": selected_query_face,
        "persons": persons,
        "ambiguous": ambiguous if persons else False,
        "warning": warning,
    }
    db.add_search(
        {
            "search_id": search_id,
            "query_paths": query_paths,
            "params": {
                "mode": "persons",
                "top_k": top_k,
                "min_score": min_score,
                "max_gap_sec": max_gap_sec,
                "query_face_index": query_face_index,
            },
            "result": result,
        }
    )
    return result
