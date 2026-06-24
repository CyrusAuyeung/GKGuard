from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import person_service  # noqa: E402
from app.storage import db  # noqa: E402


def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
    quality = dict(result.get("cluster_quality") or {})
    decisions = list(quality.pop("cluster_decisions", []))
    actions = Counter(str(decision.get("action") or "unknown") for decision in decisions)
    return {
        "dry_run": bool(quality.get("dry_run")),
        "persons": result.get("persons"),
        "linked_faces": result.get("linked_faces"),
        "source_faces": result.get("source_faces"),
        "low_quality_faces": result.get("low_quality_faces"),
        "noise_faces": result.get("noise_faces"),
        "merge_threshold": result.get("merge_threshold"),
        "min_faces": result.get("min_faces"),
        "min_face_area": result.get("min_face_area"),
        "min_detection_score": result.get("min_detection_score"),
        "algorithm": result.get("algorithm"),
        "actions": dict(actions),
        "cluster_quality": quality,
        "decisions": decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover stable unassigned face clusters as strict existing-person matches or candidate newcomers.",
    )
    parser.add_argument("--camera-prefix", default="p1e_s1_")
    parser.add_argument("--merge-threshold", type=float, default=0.76)
    parser.add_argument("--person-match-threshold", type=float, default=0.82)
    parser.add_argument("--ambiguous-person-match-threshold", type=float, default=0.78)
    parser.add_argument("--min-faces", type=int, default=2)
    parser.add_argument("--min-face-area", type=float, default=2500.0)
    parser.add_argument("--min-detection-score", type=float, default=0.70)
    parser.add_argument("--min-cluster-mean-similarity", type=float, default=0.76)
    parser.add_argument("--candidate-prefix", default="candidate_p1e_s1")
    parser.add_argument("--no-create", action="store_true")
    parser.add_argument("--use-pose-fragment-merge", action="store_true")
    parser.add_argument("--recover-weak-stable", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write changes to the C1 database.")
    args = parser.parse_args()

    db.init_db()
    result = person_service.update_person_index(
        merge_threshold=args.merge_threshold,
        person_match_threshold=args.person_match_threshold,
        ambiguous_person_match_threshold=args.ambiguous_person_match_threshold,
        min_faces=args.min_faces,
        min_face_area=args.min_face_area,
        min_detection_score=args.min_detection_score,
        camera_id_prefix=args.camera_prefix,
        create_unmatched_persons=not args.no_create,
        candidate_display_name_prefix=args.candidate_prefix,
        use_pose_fragment_merge=args.use_pose_fragment_merge,
        recover_weak_stable=args.recover_weak_stable,
        min_cluster_mean_similarity=args.min_cluster_mean_similarity,
        dry_run=not args.apply,
    )
    print(json.dumps(_compact_result(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
