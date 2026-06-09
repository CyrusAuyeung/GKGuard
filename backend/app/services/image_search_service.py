from __future__ import annotations

import hashlib
from typing import Any

from app.services.search_service import search_snapshots


PERSON_HINTS = {
    "p001": "P001",
    "student_a": "P001",
    "missing": "P001",
    "target": "P001",
    "p002": "P002",
    "p003": "P003",
    "p004": "P004",
}


def _infer_person_id(filename: str, content: bytes) -> str | None:
    haystack = f"{filename.lower()} {content[:128].decode('utf-8', errors='ignore').lower()}"
    for token, person_id in PERSON_HINTS.items():
        if token in haystack:
            return person_id
    return None


def _stable_similarity(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:4], 16) % 38
    return round(0.58 + bucket / 100, 3)


def search_by_image(filename: str, content: bytes, top_k: int = 5, min_similarity: float = 0.72) -> dict[str, Any]:
    inferred_person_id = _infer_person_id(filename, content)
    candidate_snapshots = search_snapshots(person_id=inferred_person_id) if inferred_person_id else search_snapshots()
    ranked = []
    for index, snapshot in enumerate(candidate_snapshots):
        if inferred_person_id:
            similarity = round(max(float(snapshot.get("mock_similarity", 0.82)), 0.96 - index * 0.025), 3)
            match_reason = "mock face embedding matched inferred demo identity"
        else:
            similarity = _stable_similarity(f"{filename}:{snapshot['snapshot_id']}")
            match_reason = "mock visual embedding similarity"
        if similarity < min_similarity:
            continue
        ranked.append(snapshot | {"similarity": similarity, "match_reason": match_reason})
    ranked.sort(key=lambda item: (-item["similarity"], item["time"]))
    return {
        "query_filename": filename,
        "query_hint_person_id": inferred_person_id,
        "top_k": top_k,
        "min_similarity": min_similarity,
        "matches": ranked[:top_k],
    }
