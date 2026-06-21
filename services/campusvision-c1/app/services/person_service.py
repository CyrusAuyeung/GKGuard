from __future__ import annotations

from datetime import datetime
from hashlib import sha1
import uuid
import numpy as np

from app.storage import db
from app.vision.face_engine import (
    confident_similarity_threshold,
    default_similarity_threshold,
    get_face_engine,
)
from app.vision.vector_math import cosine_similarity
from app.services import search_service


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


def _create_person_from_cluster(cluster: dict) -> tuple[dict, int]:
    representative = _cluster_representative(cluster)
    person = db.add_person(
        {
            "person_id": "person_" + uuid.uuid4().hex,
            "display_name": None,
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


def _best_existing_person_match(cluster: dict, persons: list[dict], threshold: float) -> dict | None:
    best: tuple[float, dict] | None = None
    for person in persons:
        centroid_similarity = cosine_similarity(cluster["embedding"], person["embedding"])
        person_records = db.list_face_records_for_person(person["person_id"])
        person_cluster = _make_cluster(person_records) if person_records else None
        has_conflict = person_cluster is not None and _has_same_frame_conflict(cluster, person_cluster)
        if has_conflict:
            continue

        if centroid_similarity >= threshold and (best is None or centroid_similarity > best[0]):
            best = (centroid_similarity, person)
    return best[1] if best else None


def rebuild_person_index(
    merge_threshold: float | None = None,
    min_faces: int = 2,
    min_face_area: float = 2500.0,
    min_detection_score: float = 0.85,
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
        clusters, pose_fragment_merges = _merge_pose_fragments(clusters)
        quality = _cluster_quality(clusters, len(quality_records), min_faces)
        quality["pose_fragment_merges"] = pose_fragment_merges
        algorithm = "graph_auto_threshold"
    else:
        threshold = float(merge_threshold)
        clusters = _graph_clusters(quality_records, threshold)
        quality = _cluster_quality(clusters, len(quality_records), min_faces=min_faces)
        quality["pose_fragment_merges"] = 0
        algorithm = "graph_threshold"

    selected = [cluster for cluster in clusters if len(cluster["records"]) >= min_faces]
    recovered, recovery_quality = _recover_weak_stable_clusters(
        records,
        selected,
        min_face_area=min_face_area,
    )
    selected = selected + recovered
    quality |= recovery_quality
    linked_face_ids = {
        record["face_id"] for cluster in selected for record in cluster["records"]
    }
    noise_faces = len(records) - len(linked_face_ids)

    db.clear_person_index()
    linked_faces = 0

    for cluster in selected:
        _, added_faces = _create_person_from_cluster(cluster)
        linked_faces += added_faces

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
    merge_threshold: float | None = None,
    person_match_threshold: float = 0.68,
    min_faces: int = 2,
    min_face_area: float = 2500.0,
    min_detection_score: float = 0.85,
) -> dict:
    records = db.list_unassigned_face_records()
    min_faces = int(min_faces)
    quality_records = [
        record
        for record in records
        if _is_quality_face(record, min_face_area=min_face_area, min_detection_score=min_detection_score)
    ]
    low_quality_faces = len(records) - len(quality_records)

    if merge_threshold is None:
        clusters, threshold, quality = _auto_graph_clusters(quality_records, min_faces=min_faces)
        clusters, pose_fragment_merges = _merge_pose_fragments(clusters)
        quality = _cluster_quality(clusters, len(quality_records), min_faces)
        quality["pose_fragment_merges"] = pose_fragment_merges
        algorithm = "incremental_graph_auto_threshold"
    else:
        threshold = float(merge_threshold)
        clusters = _graph_clusters(quality_records, threshold)
        quality = _cluster_quality(clusters, len(quality_records), min_faces=min_faces)
        quality["pose_fragment_merges"] = 0
        algorithm = "incremental_graph_threshold"

    selected = [cluster for cluster in clusters if len(cluster["records"]) >= min_faces]
    recovered, recovery_quality = _recover_weak_stable_clusters(
        records,
        selected,
        min_face_area=min_face_area,
    )
    selected = selected + recovered
    existing_persons = db.list_persons()
    created_persons = 0
    updated_persons: set[str] = set()
    linked_faces = 0

    for cluster in selected:
        match = _best_existing_person_match(cluster, existing_persons, threshold=person_match_threshold)
        if match is None:
            person, added_faces = _create_person_from_cluster(cluster)
            existing_persons.append(person)
            created_persons += 1
            linked_faces += added_faces
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

    linked_face_ids = {record["face_id"] for cluster in selected for record in cluster["records"]}
    noise_faces = len(records) - len(linked_face_ids)

    return {
        "persons": len(db.list_persons()),
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
            "person_match_threshold": person_match_threshold,
        },
        "algorithm": algorithm + "+weak_stable_recovery" if recovered else algorithm,
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


def list_persons() -> list[dict]:
    persons = db.list_persons()
    for person in persons:
        events = person_events(person["person_id"])
        person.pop("embedding", None)
        if person.get("representative_face_id"):
            person["representative_face_crop_url"] = (
                f"/api/v1/media/face/{person['representative_face_id']}"
            )
        person["events"] = events
        person["event_count"] = len(events)
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
