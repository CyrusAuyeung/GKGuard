from __future__ import annotations

from pathlib import Path
from typing import BinaryIO


class UploadTooLarge(ValueError):
    pass


CHUNK_SIZE = 1024 * 1024


def copy_upload_with_limit(fileobj: BinaryIO, dest: Path, max_bytes: int, label: str = "Upload") -> int:
    total = 0
    too_large = False
    with dest.open("wb") as output:
        while True:
            chunk = fileobj.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                too_large = True
                break
            output.write(chunk)
    if too_large:
        dest.unlink(missing_ok=True)
        raise UploadTooLarge(f"{label} exceeds the {max_bytes} byte limit.")
    return total
