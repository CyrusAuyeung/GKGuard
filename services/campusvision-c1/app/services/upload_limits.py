from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status

_CHUNK_SIZE = 1024 * 1024


def copy_upload_with_limit(fileobj: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Copy an uploaded stream to disk while enforcing an application byte limit."""
    total = 0
    try:
        with dest.open("wb") as output:
            while True:
                chunk = fileobj.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Upload exceeds the {max_bytes} byte limit.",
                    )
                output.write(chunk)
    except Exception:
        if dest.exists():
            dest.unlink()
        raise
    return total
