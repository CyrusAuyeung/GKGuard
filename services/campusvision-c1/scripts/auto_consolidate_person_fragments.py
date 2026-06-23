from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import person_service  # noqa: E402
from app.storage import db  # noqa: E402


def _compact(result: dict[str, Any]) -> dict[str, Any]:
    merged = []
    for item in result.get("merged") or []:
        metrics = item.get("metrics") or {}
        merged.append(
            {
                "source_person_id": item.get("source_person_id"),
                "source_display_name": metrics.get("source_display_name"),
                "target_person_id": item.get("target_person_id"),
                "centroid_similarity": metrics.get("centroid_similarity"),
                "max_pair_similarity": metrics.get("max_pair_similarity"),
                "nearest_margin": metrics.get("nearest_margin"),
                "moved_faces": item.get("moved_faces"),
                "video_ids": item.get("video_ids"),
            }
        )
    skipped = [
        {
            "source_person_id": item.get("source_person_id"),
            "source_display_name": item.get("source_display_name"),
            "target_person_id": item.get("target_person_id"),
            "centroid_similarity": item.get("centroid_similarity"),
            "max_pair_similarity": item.get("max_pair_similarity"),
            "nearest_margin": item.get("nearest_margin"),
            "reason": item.get("reason"),
        }
        for item in result.get("skipped") or []
    ]
    return {
        **{key: result.get(key) for key in (
            "dry_run",
            "source_display_prefix",
            "include_all_small_sources",
            "max_source_faces",
            "min_target_faces",
            "min_centroid_similarity",
            "min_max_pair_similarity",
            "min_nearest_margin",
            "use_clothing_conflict_guard",
            "source_candidates",
            "target_candidates",
            "merge_count",
            "skip_count",
            "persons",
        )},
        "merged": merged,
        "skipped": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automatically absorb small candidate person fragments into stable identities.",
    )
    parser.add_argument("--source-display-prefix", default="candidate_")
    parser.add_argument(
        "--all-small-sources",
        action="store_true",
        help="Treat any small indexed person as a possible fragment source instead of only prefixed candidates.",
    )
    parser.add_argument("--max-source-faces", type=int, default=3)
    parser.add_argument("--min-target-faces", type=int, default=5)
    parser.add_argument("--min-centroid-similarity", type=float, default=0.64)
    parser.add_argument("--min-max-pair-similarity", type=float, default=0.55)
    parser.add_argument("--min-nearest-margin", type=float, default=0.35)
    parser.add_argument(
        "--use-clothing-conflict-guard",
        action="store_true",
        help="Block merges when strong clothing colors disagree. Disabled by default because clothing can change.",
    )
    parser.add_argument("--apply", action="store_true", help="Write merges to the C1 database.")
    args = parser.parse_args()

    db.init_db()
    result = person_service.auto_consolidate_person_fragments(
        source_display_prefix=args.source_display_prefix,
        include_all_small_sources=args.all_small_sources,
        max_source_faces=args.max_source_faces,
        min_target_faces=args.min_target_faces,
        min_centroid_similarity=args.min_centroid_similarity,
        min_max_pair_similarity=args.min_max_pair_similarity,
        min_nearest_margin=args.min_nearest_margin,
        use_clothing_conflict_guard=args.use_clothing_conflict_guard,
        dry_run=not args.apply,
    )
    print(json.dumps(_compact(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
