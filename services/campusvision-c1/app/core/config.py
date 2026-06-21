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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _path_from_env(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


class Settings:
    app_name: str = os.getenv("APP_NAME", "CampusVision C1")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = _env_int("APP_PORT", 8000)
    api_key: str = os.getenv("CAMPUSVISION_API_KEY", "").strip()
    require_api_key: bool = _env_bool("CAMPUSVISION_REQUIRE_API_KEY", False)

    data_dir: Path = _path_from_env("CAMPUSVISION_DATA_DIR", "data")
    uploads_dir: Path = data_dir / "uploads"
    video_uploads_dir: Path = uploads_dir / "videos"
    query_uploads_dir: Path = uploads_dir / "query_images"
    frames_dir: Path = data_dir / "frames"
    db_path: Path = data_dir / "campusvision.sqlite3"

    face_engine: str = os.getenv("FACE_ENGINE", "insightface").strip().lower()
    insightface_det_size: int = _env_int("INSIGHTFACE_DET_SIZE", 1280)
    default_frame_interval_sec: float = _env_float("DEFAULT_FRAME_INTERVAL_SEC", 1.0)

    max_video_upload_bytes: int = _env_int("CAMPUSVISION_MAX_VIDEO_UPLOAD_BYTES", 512 * 1024 * 1024)
    max_query_image_upload_bytes: int = _env_int("CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES", 10 * 1024 * 1024)
    max_query_images: int = _env_int("CAMPUSVISION_MAX_QUERY_IMAGES", 5)
    max_index_frames: int = _env_int("CAMPUSVISION_MAX_INDEX_FRAMES", 5000)

    @property
    def exposed_requires_api_key(self) -> bool:
        host = self.app_host.strip().lower()
        exposed_hosts = {"0.0.0.0", "::", "[::]"}
        return self.require_api_key or host in exposed_hosts

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
