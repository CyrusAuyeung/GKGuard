from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if load_dotenv:
    load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


class Settings:
    app_name: str = os.getenv("APP_NAME", "CampusVision C1")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    data_dir: Path = _path_from_env("CAMPUSVISION_DATA_DIR", "data")
    uploads_dir: Path = data_dir / "uploads"
    video_uploads_dir: Path = uploads_dir / "videos"
    query_uploads_dir: Path = uploads_dir / "query_images"
    frames_dir: Path = data_dir / "frames"
    db_path: Path = data_dir / "campusvision.sqlite3"

    face_engine: str = os.getenv("FACE_ENGINE", "insightface").strip().lower()
    insightface_det_size: int = int(os.getenv("INSIGHTFACE_DET_SIZE", "1280"))
    default_frame_interval_sec: float = float(os.getenv("DEFAULT_FRAME_INTERVAL_SEC", "1.0"))

    def ensure_dirs(self) -> None:
        for p in [
            self.data_dir,
            self.uploads_dir,
            self.video_uploads_dir,
            self.query_uploads_dir,
            self.frames_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
