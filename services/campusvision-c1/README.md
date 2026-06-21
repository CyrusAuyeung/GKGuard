<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1：校园智能视频检索与轨迹分析接口版

CampusVision C1 是校园智能视频检索的第一阶段服务，负责打通：

```text
上传/接入视频 -> 抽帧 -> 人脸向量入库 -> 上传目标照片 -> 返回出现时间、地点、截图、相似度 -> 生成轨迹时间线
```

当前正式人脸后端固定为 InsightFace/ArcFace，便于保证视频索引、人物聚类和查询图片处在同一个 512 维 embedding 空间。

## 环境准备

推荐在 Ubuntu 22.04 LTS 上使用独立 conda 环境。若已有 `torch126` 环境，可克隆为 `campusvision-c1`：

```bash
cd campusvision-c1
bash scripts/bootstrap_from_torch126.sh
```

脚本默认执行：

```bash
conda create -n campusvision-c1 --clone torch126
conda activate campusvision-c1
pip install -r requirements.txt
```

`requirements.txt` 将 `numpy` 限制为 `<2`，并将 `opencv-python` 限制为 `<4.13`，用于匹配当前 InsightFace / ONNXRuntime 运行环境。若远端环境被 pip 升级到 NumPy 2.x，应重新执行 `pip install -r requirements.txt`，再运行 `python scripts/check_env.py` 并重启实际监听端口的 uvicorn worker。

如果原环境不是 `torch126`：

```bash
bash scripts/bootstrap_from_torch126.sh <source-env> campusvision-c1
```

## 启动服务

```bash
conda activate campusvision-c1
cd campusvision-c1
cp .env.example .env
bash scripts/run_dev.sh
```

默认地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

`.env` 中保持：

```bash
FACE_ENGINE=insightface
INSIGHTFACE_DET_SIZE=1280
```

`INSIGHTFACE_DET_SIZE` 控制 InsightFace 检测输入尺寸，默认 1280；多人全景图或多人乐队/教室场景中，如果查询图只检测到一张人脸，优先确认该值未被旧环境覆盖。修改 `.env` 后需要重启实际监听端口的 uvicorn worker。

### 资源与访问保护

默认开发脚本仍绑定 `127.0.0.1`。如果将 `APP_HOST` 改为 `0.0.0.0` 或 `::` 使 CampusVision C1 暴露到网络，必须设置 `CAMPUSVISION_API_KEY`，上传媒体、查询图片、视频索引和人物索引类接口会要求请求头 `X-CampusVision-API-Key`。也可以在环回地址部署时设置 `CAMPUSVISION_REQUIRE_API_KEY=true` 强制开启同样的校验。

上传与索引默认限制如下，可在 `.env` 中按部署容量调整：

- `CAMPUSVISION_MAX_VIDEO_UPLOAD_BYTES=536870912`：单个视频上传最大 512 MiB。
- `CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES=10485760`：单张查询图片最大 10 MiB。
- `CAMPUSVISION_MAX_QUERY_IMAGES=5`：单次查询最多 5 张图片。
- `CAMPUSVISION_MAX_INDEX_FRAMES=5000`：单个视频索引最多处理 5000 个采样帧。

## 快速接口流程

1. 创建摄像头点位。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "cam_dorm_gate_01",
    "name": "宿舍区东门摄像头01",
    "location": "宿舍区东门",
    "lat": 31.0001,
    "lng": 121.0001
  }'
```

1. 上传视频。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/upload \
  -F "file=@/path/to/demo.mp4" \
  -F "camera_id=cam_dorm_gate_01" \
  -F "recorded_at=2026-07-01T09:00:00" \
  -F "frame_interval_sec=1.0"
```

1. 建立视频索引。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/{video_id}/index
```

1. 构建或更新人物库。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/persons/update-index \
  -F "min_faces=2" \
  -F "min_face_area=2500" \
  -F "min_detection_score=0.85"
```

1. 可选：先检测查询图人脸，用于多人图片目标选择。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/query-faces \
  -F "files=@/path/to/group_photo.jpg"
```

返回内容包含 `query_faces`、每张人脸的 `bbox`、检测置信度和可选 `diagnostics`。服务端会先对查询图做 EXIF 转正、RGB 标准化、透明通道处理；若首轮没有检测到人脸，会继续尝试贴边/大脸补边和小图放大检测，并把检测框映射回原图坐标。只有一张人脸时可以直接检索；多张人脸时由上层 UI 选择目标人脸并把 `query_face_index` 传给检索接口。多人查询图只返回一张人脸时，应先检查 `INSIGHTFACE_DET_SIZE`、服务重启状态和 `diagnostics` 中的检测尝试。

1. 基于人物库以图搜人。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/person-by-image \
  -F "files=@/path/to/person_1.jpg" \
  -F "query_face_index=0" \
  -F "top_k=5" \
  -F "max_gap_sec=3.0"
```

返回内容包含 `query_faces`、`selected_query_face`、`persons`、候选人物分数、代表截图、逐帧 `matches`、`trajectory` 和 `appearance_events`。`matches[].bbox` 可用于上层界面在关键帧中标出命中人脸。

## 媒体访问

搜索结果中的关键帧 URL：

```text
/api/v1/media/frame/{face_id}
```

人物库中的人脸裁剪图 URL：

```text
/api/v1/media/face/{face_id}
```

## 目录结构

```text
campusvision-c1/
  app/
    api/                 FastAPI 路由
    core/                配置
    services/            视频索引、搜索服务
    storage/             SQLite 存储
    vision/              人脸识别、抽帧、向量逻辑
  data/                  运行后生成，不提交真实数据
  docs/
    C1_API.md
    C1_DESIGN.md
  scripts/
    bootstrap_from_torch126.sh
    run_dev.sh
    check_env.py
    smoke_test.sh
```

## CampusVision C1 边界

当前重点：

- 视频上传。
- 摄像头点位。
- 抽帧。
- 人脸入库。
- 人物库构建。
- 以图搜人。
- 时间线轨迹。
- 媒体帧访问。

后续可扩展：人体 ReID、多摄像头跨镜追踪、车辆检索、RTSP/SDK 接入、厂商智能分析接口和更丰富的轨迹地图。

## 常见问题

### 为什么固定 InsightFace？

人物库检索依赖稳定向量空间。固定 InsightFace 后，视频索引、人物聚类和查询图片都使用同一种 512 维 ArcFace embedding，阈值和分数解释更稳定。

### 视频和图片放哪里？

通过接口上传。服务会自动写入：

```text
data/uploads/videos/
data/uploads/query_images/
data/frames/
```

这些运行数据不要提交。

### 可以直接接监控流吗？

当前 CampusVision C1 先以视频文件建立闭环。RTSP/SDK 接入依赖现场网络、权限、厂商协议和码流稳定性，建议作为后续能力独立设计。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1: Campus Video Retrieval And Trajectory API

CampusVision C1 is the first-stage campus video retrieval service. It connects:

```text
upload/import video -> sample frames -> index face embeddings -> upload target photo -> return time, location, frame, similarity -> generate trajectory timeline
```

The production face backend is fixed to InsightFace/ArcFace so video indexing, person clustering, and query images stay in the same 512-dimensional embedding space.

## Environment Setup

Use a dedicated conda environment on Ubuntu 22.04 LTS. If a `torch126` environment already exists, clone it as `campusvision-c1`:

```bash
cd campusvision-c1
bash scripts/bootstrap_from_torch126.sh
```

The script defaults to:

```bash
conda create -n campusvision-c1 --clone torch126
conda activate campusvision-c1
pip install -r requirements.txt
```

`requirements.txt` pins `numpy<2` and `opencv-python<4.13` to match the current InsightFace / ONNXRuntime runtime. If pip upgrades the remote environment to NumPy 2.x, rerun `pip install -r requirements.txt`, run `python scripts/check_env.py`, and restart the uvicorn worker that owns the listening port.

If the source environment is not `torch126`:

```bash
bash scripts/bootstrap_from_torch126.sh <source-env> campusvision-c1
```

## Start The Service

```bash
conda activate campusvision-c1
cd campusvision-c1
cp .env.example .env
bash scripts/run_dev.sh
```

Default URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Keep this in `.env`:

```bash
FACE_ENGINE=insightface
INSIGHTFACE_DET_SIZE=1280
```
`INSIGHTFACE_DET_SIZE` controls the InsightFace detection input size and defaults to `1280`. If a group, classroom, or band-room image returns only one detected query face, first confirm that an old runtime environment has not overridden this value. After changing `.env`, restart the actual uvicorn worker that owns the listening port.

### Resource And Access Protection

The default development script still binds to `127.0.0.1`. If `APP_HOST` is changed to `0.0.0.0` or `::` so CampusVision C1 is exposed on a network, set `CAMPUSVISION_API_KEY`; media uploads, query-image uploads, video indexing, and person-index endpoints then require the `X-CampusVision-API-Key` request header. You can also set `CAMPUSVISION_REQUIRE_API_KEY=true` on loopback deployments to force the same check.

Uploads and indexing use these default limits, which can be adjusted in `.env` for deployment capacity:

- `CAMPUSVISION_MAX_VIDEO_UPLOAD_BYTES=536870912`: maximum 512 MiB per video upload.
- `CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES=10485760`: maximum 10 MiB per query image.
- `CAMPUSVISION_MAX_QUERY_IMAGES=5`: maximum 5 images per query request.
- `CAMPUSVISION_MAX_INDEX_FRAMES=5000`: maximum 5000 sampled frames per video indexing run.

## Quick API Flow

1. Create a camera.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "cam_dorm_gate_01",
    "name": "宿舍区东门摄像头01",
    "location": "宿舍区东门",
    "lat": 31.0001,
    "lng": 121.0001
  }'
```

1. Upload a video.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/upload \
  -F "file=@/path/to/demo.mp4" \
  -F "camera_id=cam_dorm_gate_01" \
  -F "recorded_at=2026-07-01T09:00:00" \
  -F "frame_interval_sec=1.0"
```

1. Index the video.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/{video_id}/index
```

1. Build or update the person index.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/persons/update-index \
  -F "min_faces=2" \
  -F "min_face_area=2500" \
  -F "min_detection_score=0.85"
```

1. Optional: detect faces in the query image for multi-face target selection.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/query-faces \
  -F "files=@/path/to/group_photo.jpg"
```

The response includes `query_faces`, each face `bbox`, detection confidence, and optional `diagnostics`. The service normalizes EXIF orientation, RGB channels, and alpha before detection. If the first pass finds no faces, it retries with padding for tight or large faces and with small-image upscaling, then maps detected boxes back to original-image coordinates. If there is one face, the caller can search directly; if there are multiple faces, the upper-layer UI selects the target and passes `query_face_index` to the search endpoint. If a multi-face query image returns only one face, check `INSIGHTFACE_DET_SIZE`, confirm the service was restarted, and inspect `diagnostics`.

1. Search person by image.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/person-by-image \
  -F "files=@/path/to/person_1.jpg" \
  -F "query_face_index=0" \
  -F "top_k=5" \
  -F "max_gap_sec=3.0"
```

The response includes `query_faces`, `selected_query_face`, `persons`, candidate scores, representative frames, frame-level `matches`, `trajectory`, and `appearance_events`. `matches[].bbox` can be used by upper-layer UIs to mark the matched face in the keyframe.

## Media Access

Keyframe URL in search results:

```text
/api/v1/media/frame/{face_id}
```

Face crop URL in the person index:

```text
/api/v1/media/face/{face_id}
```

## Directory Structure

```text
campusvision-c1/
  app/
    api/                 FastAPI routes
    core/                configuration
    services/            video indexing and search services
    storage/             SQLite storage
    vision/              face recognition, frame sampling, embeddings
  data/                  generated at runtime; do not commit real data
  docs/
    C1_API.md
    C1_DESIGN.md
  scripts/
    bootstrap_from_torch126.sh
    run_dev.sh
    check_env.py
    smoke_test.sh
```

## CampusVision C1 Boundary

Current focus:

- Video upload.
- Camera points.
- Frame sampling.
- Face indexing.
- Person index creation.
- Search person by image.
- Timeline trajectory.
- Media frame access.

Future extensions may include body ReID, multi-camera tracking, vehicle retrieval, RTSP/SDK integration, vendor analysis APIs, and richer route maps.

## FAQ

### Why Fix InsightFace?

Person indexing depends on a stable vector space. With InsightFace fixed, video indexing, person clustering, and query images all use the same 512-dimensional ArcFace embedding, making thresholds and scores easier to interpret.

### Where Are Videos And Images Stored?

Upload them through the API. The service writes runtime data to:

```text
data/uploads/videos/
data/uploads/query_images/
data/frames/
```

Do not commit these runtime files.

### Can It Connect Directly To Camera Streams?

The current CampusVision C1 milestone closes the loop with uploaded video files first. RTSP/SDK integration depends on site network access, permissions, vendor protocols, and stream stability, so it should be designed as a later capability.

<p align="right"><a href="#english">Back to English top</a></p>
