<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# C1 设计说明

CampusVision C1 负责校园历史视频中的人脸检索与轨迹分析，为 GKGuard C2 提供可调用的 AI 能力。当前实现以 FastAPI 暴露接口，以 SQLite 保存元数据和向量，以 InsightFace/ArcFace 生成 512 维人脸 embedding。

## 目标

C1 的第一阶段目标是闭环以下能力：

1. 上传或接入历史视频。
2. 按时间间隔抽帧。
3. 检测画面中的人脸。
4. 生成人脸 embedding 并保存。
5. 从已索引的人脸中构建人物库。
6. 上传目标人物照片进行检索。
7. 返回出现时间、摄像头、地点、相似度和截图。
8. 输出按时间排序的人物轨迹。

## 非目标

当前阶段不负责：

- 实时 RTSP 拉流和流媒体运维。
- 低层摄像头 SDK 适配。
- 车辆重识别。
- C2 桌面 UI。
- CampusCar、UE 或底盘控制。
- 用户认证、权限和生产审计。

这些能力应由后续模块或上层 C2 接入。

## 架构

```text
FastAPI routes
  -> service layer
    -> video indexing service
    -> person index service
    -> search service
  -> vision layer
    -> frame sampler
    -> InsightFace face engine
    -> embedding comparison
  -> SQLite repository
  -> runtime media files
```

主要目录：

```text
app/api/        API 路由
app/core/       配置
app/services/   业务服务
app/storage/    SQLite repository
app/vision/     CV 与 embedding 逻辑
data/           运行时数据，不提交真实内容
docs/           API 与设计文档
scripts/        环境、启动和 smoke test 脚本
```

## 数据流

### 视频索引

```text
上传视频
  -> 保存到 data/uploads/videos
  -> 写入 videos 表
  -> 抽帧到 data/frames
  -> 人脸检测
  -> 生成 embedding
  -> 写入 face_records 表
```

### 人物库构建

```text
face_records
  -> 按 detection score 和 face area 过滤
  -> 相似度图聚类
  -> 生成 persons
  -> 写入 person_faces
  -> 选出 representative_face_id
```

### 人物检索

```text
查询图片
  -> 人脸检测与 embedding
  -> 与 persons 代表向量/成员向量比较
  -> 返回候选 person
  -> 展开该 person 的 face_records
  -> 生成 matches、trajectory、appearance_events
```

## 数据模型

核心表：

- `cameras`：摄像头点位、位置和经纬度。
- `videos`：上传视频元数据、来源摄像头和录制时间。
- `frames`：抽帧结果和视频内时间戳。
- `face_records`：人脸检测框、分数、embedding、关联 frame/video/camera。
- `persons`：人物聚类结果和代表人脸。
- `person_faces`：person 与 face_record 的关联。

embedding 当前以 SQLite blob 保存。后续数据量变大时，可迁移到向量数据库或 FAISS 索引。

## 人脸引擎

当前正式引擎：

```text
FACE_ENGINE=insightface
```

选择原因：

- 人脸检测和识别能力稳定。
- ArcFace 512 维向量适合相似度比较。
- 视频索引、人物聚类和查询图片可以共用同一向量空间。
- C2 适配器和阈值解释更稳定。

本地开发如果使用旧环境或错误 worker，可能出现 `/health` 仍显示旧引擎的情况。需要确认实际监听端口的 uvicorn worker 环境变量。

## 相似度与阈值

当前以 cosine similarity 作为主要相似度。

常用阈值：

- `min_detection_score=0.85`
- `min_face_area=2500`
- `person_match_threshold=0.68`
- `max_gap_sec=3.0`

阈值应根据现场摄像头角度、画质、光照和样本数量继续校准。

## 轨迹与出现事件

`trajectory` 是逐帧命中按时间排序后的地图/时间线视图。每个点包含摄像头、位置、时间和相似度。

`appearance_events` 把同一视频、同一摄像头、连续时间窗口内的命中合并为一次出现。它更适合 C2 展示“某人在某地点停留/经过”的摘要。

## 与 C2 的关系

C2 不直接读取 C1 数据库或运行目录，而是通过 HTTP API 调用 C1。

推荐 C2 调用面：

- `GET /health`
- `GET /api/v1/persons`
- `GET /api/v1/videos`
- `POST /api/v1/search/person-by-image`
- `GET /api/v1/media/frame/{face_id}`
- `GET /api/v1/media/face/{face_id}`

C2 当前通过自身 `/c1/...` 代理和适配器转发这些能力，避免前端直接依赖 C1 内部结构。

## 运行数据与安全

以下目录包含真实或潜在敏感数据，不应提交到 Git：

```text
data/uploads/videos/
data/uploads/query_images/
data/frames/
data/campusvision.sqlite3
.env
```

敏感数据包括人脸图像、视频帧、移动轨迹、摄像头位置和人物关联关系。

## 后续演进

建议的后续方向：

1. 增加真实摄像头/RTSP 导入层。
2. 引入后台任务队列，避免视频索引阻塞 HTTP 请求。
3. 增加批量索引进度查询。
4. 将大规模 embedding 检索迁移到 FAISS 或向量数据库。
5. 增加身份、权限、审计和数据保留策略。
6. 提供 C2 所需的更稳定 response schema 版本号。
7. 增加人体 ReID 和车辆检索能力。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# C1 Design Notes

CampusVision C1 provides face retrieval and trajectory analysis over campus historical video, exposing AI capabilities for GKGuard C2. The current implementation uses FastAPI for APIs, SQLite for metadata and vectors, and InsightFace/ArcFace for 512-dimensional face embeddings.

## Goals

The first C1 milestone closes this loop:

1. Upload or import historical video.
2. Sample frames at a time interval.
3. Detect faces in frames.
4. Generate and store face embeddings.
5. Build a person index from indexed faces.
6. Upload a target-person photo for search.
7. Return appearance time, camera, location, similarity, and frame image.
8. Output a time-sorted trajectory.

## Non-Goals

The current phase does not own:

- Real-time RTSP ingestion and streaming operations.
- Low-level camera SDK adapters.
- Vehicle re-identification.
- C2 desktop UI.
- CampusCar, UE, or chassis control.
- User authentication, authorization, and production audit.

Those capabilities should be added by later modules or upper-level C2 integration.

## Architecture

```text
FastAPI routes
  -> service layer
    -> video indexing service
    -> person index service
    -> search service
  -> vision layer
    -> frame sampler
    -> InsightFace face engine
    -> embedding comparison
  -> SQLite repository
  -> runtime media files
```

Main directories:

```text
app/api/        API routes
app/core/       configuration
app/services/   business services
app/storage/    SQLite repository
app/vision/     computer vision and embedding logic
data/           runtime data; do not commit real contents
docs/           API and design docs
scripts/        environment, startup, and smoke-test scripts
```

## Data Flow

### Video Indexing

```text
upload video
  -> save to data/uploads/videos
  -> insert videos row
  -> sample frames to data/frames
  -> detect faces
  -> generate embeddings
  -> insert face_records rows
```

### Person Indexing

```text
face_records
  -> filter by detection score and face area
  -> cluster by similarity graph
  -> create persons
  -> write person_faces
  -> choose representative_face_id
```

### Person Search

```text
query image
  -> face detection and embedding
  -> compare with person representative/member vectors
  -> return candidate people
  -> expand selected person's face_records
  -> generate matches, trajectory, appearance_events
```

## Data Model

Core tables:

- `cameras`: camera points, location, and coordinates.
- `videos`: uploaded video metadata, source camera, and recording time.
- `frames`: sampled frames and timestamps within video.
- `face_records`: face boxes, detection scores, embeddings, and frame/video/camera links.
- `persons`: person clusters and representative faces.
- `person_faces`: relation between a person and face records.

Embeddings are currently stored as SQLite blobs. For larger datasets, this can move to a vector database or FAISS index.

## Face Engine

Production engine:

```text
FACE_ENGINE=insightface
```

Reasons:

- Stable face detection and recognition.
- ArcFace 512-dimensional vectors are suitable for similarity search.
- Video indexing, person clustering, and query images share one vector space.
- C2 adapter behavior and threshold interpretation are more stable.

In local development, an old environment or stale worker can make `/health` still show an old engine. Confirm the environment variables of the actual uvicorn worker that owns the listening port.

## Similarity And Thresholds

Cosine similarity is currently the main score.

Common thresholds:

- `min_detection_score=0.85`
- `min_face_area=2500`
- `person_match_threshold=0.68`
- `max_gap_sec=3.0`

Thresholds should be calibrated against real camera angles, image quality, lighting, and sample count.

## Trajectory And Appearance Events

`trajectory` is the map/timeline view created from frame-level matches sorted by time. Each point includes camera, location, time, and similarity.

`appearance_events` merges hits from the same video, camera, and continuous time window into one appearance. It is better suited for C2 summaries such as “this person stayed at or passed through this place.”

## Relationship With C2

C2 should not read the C1 database or runtime directories directly. It should call C1 over HTTP APIs.

Recommended C2 call surface:

- `GET /health`
- `GET /api/v1/persons`
- `GET /api/v1/videos`
- `POST /api/v1/search/person-by-image`
- `GET /api/v1/media/frame/{face_id}`
- `GET /api/v1/media/face/{face_id}`

C2 currently forwards these capabilities through its own `/c1/...` proxy and adapter so the frontend does not depend on C1 internals.

## Runtime Data And Safety

These paths contain real or potentially sensitive data and must not be committed:

```text
data/uploads/videos/
data/uploads/query_images/
data/frames/
data/campusvision.sqlite3
.env
```

Sensitive data includes face images, video frames, movement trajectories, camera locations, and person links.

## Future Evolution

Suggested next steps:

1. Add real camera or RTSP ingestion.
2. Introduce a background task queue so video indexing does not block HTTP requests.
3. Add batch indexing progress APIs.
4. Move large-scale embedding search to FAISS or a vector database.
5. Add identity, permission, audit, and retention policies.
6. Provide a more stable response schema version for C2.
7. Add body ReID and vehicle retrieval.

<p align="right"><a href="#english">Back to English top</a></p>
