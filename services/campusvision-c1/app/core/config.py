from __future__ import annotations

import os
from pathlib import Path
import sys

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


def _uvicorn_host_arg() -> str:
    args = sys.argv
    for index, arg in enumerate(args):
        if arg == "--host" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--host="):
            return arg.partition("=")[2]
    return ""


def _bool_from_env(name: str, default: bool) -> bool:
    return _env_bool(name, default)


def _list_from_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Settings:
    app_name: str = os.getenv("APP_NAME", "CampusVision C1")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = _env_int("APP_PORT", 8000)
    api_key: str = (os.getenv("CAMPUSVISION_API_KEY") or os.getenv("C1_API_KEY") or "").strip()
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
    max_query_image_upload_bytes: int = _env_int("CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES", 16 * 1024 * 1024)
    max_query_images: int = _env_int("CAMPUSVISION_MAX_QUERY_IMAGES", 5)
    max_index_frames: int = _env_int("CAMPUSVISION_MAX_INDEX_FRAMES", 5000)

    @property
    def exposed_requires_api_key(self) -> bool:
        host = (_uvicorn_host_arg() or self.app_host).strip().lower()
        return self.require_api_key or host in {"0.0.0.0", "::", "[::]"}

    event_time_window_sec: float = float(os.getenv("EVENT_TIME_WINDOW_SEC", "10.0"))

    enable_body_detection: bool = _bool_from_env("ENABLE_BODY_DETECTION", True)
    body_detection_backend: str = os.getenv("BODY_DETECTION_BACKEND", "opencv_hog").strip().lower()
    person_detection_confidence_threshold: float = float(
        os.getenv("PERSON_DETECTION_CONFIDENCE_THRESHOLD", "0.35")
    )
    person_detection_nms_threshold: float = float(os.getenv("PERSON_DETECTION_NMS_THRESHOLD", "0.45"))
    ultralytics_model_path: Path = _path_from_env(
        "ULTRALYTICS_MODEL_PATH",
        "data/models/ultralytics/yolo11x.pt",
    )
    ultralytics_device: str = os.getenv("ULTRALYTICS_DEVICE", "cuda:0")
    ultralytics_imgsz: int = int(os.getenv("ULTRALYTICS_IMGSZ", "960"))
    ultralytics_max_detections: int = int(os.getenv("ULTRALYTICS_MAX_DETECTIONS", "50"))
    min_person_box_width: int = int(os.getenv("MIN_PERSON_BOX_WIDTH", "28"))
    min_person_box_height: int = int(os.getenv("MIN_PERSON_BOX_HEIGHT", "56"))
    max_bbox_edge_truncation_ratio: float = float(os.getenv("MAX_BBOX_EDGE_TRUNCATION_RATIO", "0.35"))
    face_body_match_threshold: float = float(os.getenv("FACE_BODY_MATCH_THRESHOLD", "0.35"))
    face_body_max_normalized_distance: float = float(
        os.getenv("FACE_BODY_MAX_NORMALIZED_DISTANCE", "0.65")
    )

    enable_clothing_detection: bool = _bool_from_env("ENABLE_CLOTHING_DETECTION", True)
    enable_upper_clothing_detection: bool = _bool_from_env("ENABLE_UPPER_CLOTHING_DETECTION", True)
    enable_lower_clothing_detection: bool = _bool_from_env("ENABLE_LOWER_CLOTHING_DETECTION", True)
    enable_lower_clothing_core: bool = _bool_from_env("ENABLE_LOWER_CLOTHING_CORE", False)
    upper_roi_start_ratio: float = float(os.getenv("UPPER_ROI_START_RATIO", "0.20"))
    upper_roi_end_ratio: float = float(os.getenv("UPPER_ROI_END_RATIO", "0.50"))
    lower_roi_start_ratio: float = float(os.getenv("LOWER_ROI_START_RATIO", "0.46"))
    lower_roi_end_ratio: float = float(os.getenv("LOWER_ROI_END_RATIO", "0.78"))
    upper_color_confidence_threshold: float = float(
        os.getenv("UPPER_COLOR_CONFIDENCE_THRESHOLD", "0.35")
    )
    lower_color_confidence_threshold: float = float(
        os.getenv("LOWER_COLOR_CONFIDENCE_THRESHOLD", "0.35")
    )
    min_clothing_color_confidence: float = float(os.getenv("MIN_CLOTHING_COLOR_CONFIDENCE", "0.60"))
    clothing_roi_center_width_ratio: float = float(os.getenv("CLOTHING_ROI_CENTER_WIDTH_RATIO", "0.58"))
    lower_body_min_detection_confidence: float = float(
        os.getenv("LOWER_BODY_MIN_DETECTION_CONFIDENCE", "0.45")
    )
    min_valid_pixel_ratio: float = float(os.getenv("MIN_VALID_PIXEL_RATIO", "0.18"))
    min_clothing_roi_area: int = int(os.getenv("MIN_CLOTHING_ROI_AREA", "300"))
    clothing_color_labels: list[str] = _list_from_env(
        "CLOTHING_COLOR_LABELS",
        "black,white,gray,red,orange,yellow,green,blue,purple,brown,pink,striped,other,unknown",
    )
    enable_upper_color_calibrator: bool = _bool_from_env("ENABLE_UPPER_COLOR_CALIBRATOR", False)
    upper_color_calibrator_path: Path = _path_from_env(
        "UPPER_COLOR_CALIBRATOR_PATH",
        "data/models/clothing/upper_color_calibrator_v1.json",
    )
    upper_color_calibrator_k: int = int(os.getenv("UPPER_COLOR_CALIBRATOR_K", "1"))
    upper_color_calibrator_min_confidence: float = float(
        os.getenv("UPPER_COLOR_CALIBRATOR_MIN_CONFIDENCE", "0.0")
    )
    upper_color_backend: str = os.getenv("UPPER_COLOR_BACKEND", "hsv").strip().lower()
    upper_color_clip_backend: str = os.getenv("UPPER_COLOR_CLIP_BACKEND", "hf").strip().lower()
    upper_color_clip_model_dir: Path = _path_from_env(
        "UPPER_COLOR_CLIP_MODEL_DIR",
        "data/models/clip/laion_CLIP-ViT-H-14-laion2B-s32B-b79K",
    )
    upper_color_clip_device: str = os.getenv("UPPER_COLOR_CLIP_DEVICE", "cuda:0")
    upper_color_clip_profile: str = os.getenv(
        "UPPER_COLOR_CLIP_PROFILE",
        "profile_realtime_balanced_prompt_v2",
    )
    upper_color_clip_temperature: float = float(os.getenv("UPPER_COLOR_CLIP_TEMPERATURE", "10.0"))
    upper_color_clip_min_confidence: float = float(os.getenv("UPPER_COLOR_CLIP_MIN_CONFIDENCE", "0.0"))
    upper_color_clip_fail_open: bool = _bool_from_env("UPPER_COLOR_CLIP_FAIL_OPEN", True)
    enable_upper_color_backend_for_face_estimated_body: bool = _bool_from_env(
        "ENABLE_UPPER_COLOR_BACKEND_FOR_FACE_ESTIMATED_BODY",
        False,
    )
    upper_color_schp_root: Path = _path_from_env(
        "UPPER_COLOR_SCHP_ROOT",
        "data/models/schp/Self-Correction-Human-Parsing",
    )
    upper_color_schp_checkpoint: Path = _path_from_env(
        "UPPER_COLOR_SCHP_CHECKPOINT",
        "data/models/schp/checkpoints/schp/exp-schp-201908261155-lip.pth",
    )
    upper_color_schp_min_mask_pixels: int = int(os.getenv("UPPER_COLOR_SCHP_MIN_MASK_PIXELS", "250"))
    enable_upper_color_temporal_cache: bool = _bool_from_env("ENABLE_UPPER_COLOR_TEMPORAL_CACHE", True)
    upper_color_temporal_cache_max_age_sec: float = float(
        os.getenv("UPPER_COLOR_TEMPORAL_CACHE_MAX_AGE_SEC", "4.0")
    )
    upper_color_temporal_cache_iou_threshold: float = float(
        os.getenv("UPPER_COLOR_TEMPORAL_CACHE_IOU_THRESHOLD", "0.45")
    )
    upper_color_temporal_cache_center_threshold: float = float(
        os.getenv("UPPER_COLOR_TEMPORAL_CACHE_CENTER_THRESHOLD", "0.30")
    )
    upper_color_temporal_cache_face_max_age_sec: float = float(
        os.getenv("UPPER_COLOR_TEMPORAL_CACHE_FACE_MAX_AGE_SEC", "30.0")
    )
    upper_color_temporal_cache_face_similarity_threshold: float = float(
        os.getenv("UPPER_COLOR_TEMPORAL_CACHE_FACE_SIMILARITY_THRESHOLD", "0.62")
    )
    enable_event_persistence: bool = _bool_from_env("ENABLE_EVENT_PERSISTENCE", True)
    clothing_model_version: str = os.getenv("CLOTHING_MODEL_VERSION", "hsv_roi_v6_upper_lab_guard_striped")
    body_model_version: str = os.getenv("BODY_MODEL_VERSION", "opencv_hog_v1")
    appearance_session_max_gap_sec: float = float(os.getenv("APPEARANCE_SESSION_MAX_GAP_SEC", "14400"))
    appearance_session_min_support: int = int(os.getenv("APPEARANCE_SESSION_MIN_SUPPORT", "2"))
    appearance_session_profile_confidence: float = float(
        os.getenv("APPEARANCE_SESSION_PROFILE_CONFIDENCE", "0.58")
    )
    appearance_session_low_confidence_threshold: float = float(
        os.getenv("APPEARANCE_SESSION_LOW_CONFIDENCE_THRESHOLD", "0.55")
    )
    appearance_session_change_confidence: float = float(
        os.getenv("APPEARANCE_SESSION_CHANGE_CONFIDENCE", "0.82")
    )
    person_merge_scorer_model_path: Path = _path_from_env(
        "PERSON_MERGE_SCORER_MODEL_PATH",
        "data/models/person_merge/person_merge_scorer_v1.json",
    )
    person_identity_stable_min_faces: int = int(os.getenv("PERSON_IDENTITY_STABLE_MIN_FACES", "10"))
    enable_gender_presentation_detection: bool = _bool_from_env(
        "ENABLE_GENDER_PRESENTATION_DETECTION",
        True,
    )
    gender_presentation_model_dir: Path = _path_from_env(
        "GENDER_PRESENTATION_MODEL_DIR",
        "data/models/clip/laion_CLIP-ViT-H-14-laion2B-s32B-b79K",
    )
    gender_presentation_device: str = os.getenv("GENDER_PRESENTATION_DEVICE", "cuda:0")
    gender_presentation_temperature: float = float(
        os.getenv("GENDER_PRESENTATION_TEMPERATURE", "10.0")
    )
    gender_presentation_sample_count: int = int(os.getenv("GENDER_PRESENTATION_SAMPLE_COUNT", "8"))
    gender_presentation_fail_open: bool = _bool_from_env("GENDER_PRESENTATION_FAIL_OPEN", True)
    enable_glasses_status_detection: bool = _bool_from_env("ENABLE_GLASSES_STATUS_DETECTION", True)
    glasses_status_model_dir: Path = _path_from_env(
        "GLASSES_STATUS_MODEL_DIR",
        "data/models/clip/laion_CLIP-ViT-H-14-laion2B-s32B-b79K",
    )
    glasses_status_device: str = os.getenv("GLASSES_STATUS_DEVICE", "cuda:0")
    glasses_status_temperature: float = float(os.getenv("GLASSES_STATUS_TEMPERATURE", "10.0"))
    glasses_status_sample_count: int = int(os.getenv("GLASSES_STATUS_SAMPLE_COUNT", "8"))
    glasses_status_fail_open: bool = _bool_from_env("GLASSES_STATUS_FAIL_OPEN", True)

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
