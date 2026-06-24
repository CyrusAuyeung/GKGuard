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
当前 `v0.2.2` 集成状态下，CampusVision C1 还提供人物事件、事件观测、人体图、上装颜色、眼镜状态、外观倾向和人物特征检索接口，供 GKGuard C2 展示“以图搜人”和“按人物特征查事件”两个入口。`v0.2.1` 在 `v0.2.0` 集成基础上修复查询图不可解码与超限清理、同一视频重复索引幂等性、受影响人物索引与 appearance session 重建、人物特征路线点时间顺序和路线点到结果记录的稳定映射；`v0.2.2` 进一步统一查询图候选接口的 Query 参数、4xx 校验错误返回和路线点高亮边界。

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

## 安全与资源限制

默认本地开发绑定 `127.0.0.1`，不要求 API key。若服务绑定到 `0.0.0.0`、`::` 或显式设置 `CAMPUSVISION_REQUIRE_API_KEY=true`，必须配置 `CAMPUSVISION_API_KEY` 或 `C1_API_KEY`；受保护的相机元数据、视频列表、上传、索引、人物库、检索结果、媒体帧、人脸裁剪图和记录接口会在读取 multipart 请求体前校验 `X-CampusVision-API-Key`。人物库 HTML 预览会在服务端内联人脸图，不依赖浏览器直接请求受保护媒体 URL。查询图不可解码时返回 400，上传体积、解码像素数或单边尺寸超限时返回 413，并清理临时上传；重复索引同一 `video_id` 会先替换旧索引产物，如果替换索引失败，需要重新运行索引，不应依赖旧事件或人物结果自动保留。不要把 API key 写入仓库或日志。

`.env` 可配置以下资源上限：

```bash
CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES=16777216
CAMPUSVISION_MAX_QUERY_IMAGES=5
CAMPUSVISION_MAX_VIDEO_UPLOAD_BYTES=536870912
CAMPUSVISION_MAX_INDEX_FRAMES=5000
```

查询图会限制上传体积、解码像素数和单边尺寸；视频上传和索引会限制体积与最大抽帧数量。不可解码查询图和超限请求都会返回结构化错误，并清理已经保存的临时文件或部分索引结果。

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

1. 面向 GKGuard C2 的人脸查询大接口。

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/query/face-image?top_k=5&include_candidates=true&event_limit_per_person=10" \
  -F "files=@/path/to/person_1.jpg"
```

该接口复用查询图人脸检测和人物库检索，返回 `candidates[]`、候选人物属性、事件列表、逐帧匹配和轨迹。默认优先稳定人物，`include_candidates=true` 时包含候选碎片人物。多图查询可通过 Query 参数 `query_face_indices` 指定每张图使用的人脸序号。接口沿用查询图上传数量、单文件大小和解码尺寸限制；不可解码查询图返回 400，超限时返回 413。

1. 按人物特征查事件。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/person-attributes \
  -H "Content-Type: application/json" \
  -d '{"upper_colors":["black"],"glasses_status":["no_glasses"],"include_candidates":true,"limit":20}'
```

该接口按时间、摄像头、上装颜色、眼镜状态、外观倾向和人物范围查询事件。结果分为 `exact` 和 `partial`：`exact` 表示已填写条件全部满足，`partial` 会通过 `failed_conditions` 和 `condition_scores` 说明不满足项；`unknown` 表示模型无法判断，不等同于否定结果。当查询条件显式选择 `unknown` 时，真实 `unknown` 事件会作为满足条件处理。候选扫描优先覆盖最新事件窗口，避免大规模索引只检索到最早事件。

手动实时源采集 `/api/v1/live-sources/{source_id}/capture` 若未传 `recorded_at`，会使用采集开始时间写入视频记录；因此 `index=true` 生成的事件可正常参与时间范围筛选。

1. 查询事件与观测。

```bash
curl http://127.0.0.1:8000/api/v1/events
curl 'http://127.0.0.1:8000/api/v1/persons/{person_id}/events?limit=20'
curl http://127.0.0.1:8000/api/v1/events/{event_id}/observations
```

这些只读接口用于查看人物连续出现事件和事件内观测明细，供上层 UI 定位事件关键帧、人体图、人脸图和轨迹摘要。

## 媒体访问

搜索结果中的关键帧 URL：

```text
/api/v1/media/frame/{face_id}
```

人物库中的人脸裁剪图 URL：

```text
/api/v1/media/face/{face_id}
```

事件代表现场图和人体图 URL：

```text
/api/v1/media/event/frame/{event_id}
/api/v1/media/event/body/{event_id}
```

观测级现场图和人体图 URL：

```text
/api/v1/media/observation/frame/{observation_id}
/api/v1/media/observation/body/{observation_id}
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
- 人物事件与事件观测。
- 上装颜色、眼镜状态和外观倾向查询。
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
In the current `v0.2.2` integration state, CampusVision C1 also exposes person events, event observations, body crops, upper color, glasses status, appearance presentation, and person-attribute search endpoints for GKGuard C2's image-based person search and attribute-based event search entries. `v0.2.1` fixed undecodable and over-limit query-image cleanup, same-video re-index idempotency, affected person-index and appearance-session rebuilds, chronological person-attribute route ordering, and stable route-to-record mapping on top of the `v0.2.0` integration; `v0.2.2` further aligns the query-image candidate endpoint's Query parameters, 4xx validation-error responses, and route-point highlighting boundaries.

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

## Security And Resource Limits

Local development binds to `127.0.0.1` by default and does not require an API key. If the service binds to `0.0.0.0`, `::`, or explicitly sets `CAMPUSVISION_REQUIRE_API_KEY=true`, set `CAMPUSVISION_API_KEY` or `C1_API_KEY`; protected camera-metadata, video-list, upload, indexing, person-index, search-result, media-frame, face-crop, and record endpoints validate `X-CampusVision-API-Key` before reading multipart request bodies. The person-gallery HTML preview inlines face images server-side instead of relying on browser requests to protected media URLs. Undecodable query images return 400, query-image upload-size, decoded-pixel, or maximum-side violations return 413, and these paths clean up temporary uploads; re-indexing the same `video_id` replaces the old index artifacts first, so a failed replacement index must be run again instead of relying on old event or person results being preserved automatically. Do not write API keys to the repository or logs.

These resource limits can be configured in `.env`:

```bash
CAMPUSVISION_MAX_QUERY_IMAGE_UPLOAD_BYTES=16777216
CAMPUSVISION_MAX_QUERY_IMAGES=5
CAMPUSVISION_MAX_VIDEO_UPLOAD_BYTES=536870912
CAMPUSVISION_MAX_INDEX_FRAMES=5000
```

Query images are limited by upload size, decoded pixel count, and maximum side length; video upload and indexing are limited by upload size and maximum indexed frames. Undecodable query images and over-limit requests return structured errors and clean up saved temporary files or partial indexing results.

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

1. Use the GKGuard C2-oriented face query endpoint.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/query/face-image?top_k=5&include_candidates=true&event_limit_per_person=10" \
  -F "files=@/path/to/person_1.jpg"
```

This endpoint reuses query-face detection and person-index search, returning `candidates[]`, candidate attributes, events, frame-level matches, and trajectory. It prefers stable people by default; `include_candidates=true` includes candidate fragments. Multi-image queries can use the Query parameter `query_face_indices` to select the face index for each image. It reuses query-image upload-count, per-file-size, and decoded-dimension limits; undecodable query images return 400, and over-limit requests return 413.

1. Search events by person attributes.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/person-attributes \
  -H "Content-Type: application/json" \
  -d '{"upper_colors":["black"],"glasses_status":["no_glasses"],"include_candidates":true,"limit":20}'
```

This endpoint searches events by time, camera, upper color, glasses status, appearance presentation, and person scope. Results are marked as `exact` or `partial`: `exact` means all filled conditions match, while `partial` explains failed conditions through `failed_conditions` and `condition_scores`; `unknown` means the model cannot determine the attribute, not that the attribute is false. When a query explicitly selects `unknown`, events whose actual value is `unknown` satisfy that condition. Candidate scanning prioritizes the newest event window so large indexes do not only search the oldest events.

Manual live-source capture at `/api/v1/live-sources/{source_id}/capture` stamps the video row with the capture start time when `recorded_at` is omitted, so events produced by `index=true` can participate in time-range filtering.

1. Query events and observations.

```bash
curl http://127.0.0.1:8000/api/v1/events
curl 'http://127.0.0.1:8000/api/v1/persons/{person_id}/events?limit=20'
curl http://127.0.0.1:8000/api/v1/events/{event_id}/observations
```

These read-only endpoints expose continuous person events and event observation details so upper-layer UIs can locate event keyframes, body crops, face crops, and route summaries.

## Media Access

Keyframe URL in search results:

```text
/api/v1/media/frame/{face_id}
```

Face crop URL in the person index:

```text
/api/v1/media/face/{face_id}
```

Event representative frame and body crop URLs:

```text
/api/v1/media/event/frame/{event_id}
/api/v1/media/event/body/{event_id}
```

Observation-level frame and body crop URLs:

```text
/api/v1/media/observation/frame/{observation_id}
/api/v1/media/observation/body/{observation_id}
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
- Person events and event observations.
- Upper color, glasses status, and gender-presentation queries.
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
