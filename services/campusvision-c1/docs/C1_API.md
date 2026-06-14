<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 API 说明

Base URL：

```text
http://127.0.0.1:8000
```

交互式文档：

```text
http://127.0.0.1:8000/docs
```

## 健康检查

`GET /health`

返回服务状态、数据目录和识别引擎。正式检索期望 `face_engine=insightface`。

## 摄像头点位

`POST /api/v1/cameras`

创建或更新摄像头点位。

```json
{
  "camera_id": "cam_dorm_gate_01",
  "name": "宿舍区东门摄像头01",
  "location": "宿舍区东门",
  "lat": 31.0001,
  "lng": 121.0001
}
```

`GET /api/v1/cameras`

返回所有摄像头点位。

## 视频

`POST /api/v1/videos/upload`

上传历史监控视频。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `file` | file | 是 | mp4/avi/mov/mkv 等视频 |
| `camera_id` | string | 是 | 摄像头 ID |
| `recorded_at` | string | 否 | 视频起始时间，ISO 格式 |
| `frame_interval_sec` | float | 否 | 抽帧间隔，默认 1 秒 |

`GET /api/v1/videos`

查看已上传视频。

`POST /api/v1/videos/{video_id}/index`

对视频抽帧并建立人脸向量索引。

## 逐帧以图搜人

`POST /api/v1/search/by-image`

上传一张或多张目标人物照片，在历史帧级索引中检索相似人脸。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `files` | file[] | 是 | 目标人物照片，可多张 |
| `top_k` | int | 否 | 返回前 K 个逐帧结果，默认 20 |
| `min_score` | float | 否 | 最低相似度；不传时使用默认阈值 |
| `max_gap_sec` | float | 否 | 合并连续出现事件的最大时间间隔，默认 3.0 秒 |
| `camera_id` | string | 否 | 限定摄像头 |
| `start_time` | string | 否 | 限定开始时间 |
| `end_time` | string | 否 | 限定结束时间 |

返回内容：

- `search_id`：查询 ID。
- `matches`：逐帧命中，按 `score` 从高到低排序。
- `trajectory`：按时间排序的轨迹点。
- `appearance_events`：按 `video_id`、`camera_id` 和连续时间窗口合并的出现事件。

## 人物库

人物库从已建索引的 `face_records` 中聚类生成，一个 `person` 代表一组视觉上相似的人脸记录。常规使用时优先调用增量更新接口。

`POST /api/v1/persons/update-index`

增量更新人物库。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `merge_threshold` | float | 否 | 新 face_records 内部连边阈值；不传时自动扫描 |
| `person_match_threshold` | float | 否 | 新簇匹配已有人物阈值，默认 0.68 |
| `min_faces` | int | 否 | 新簇最少人脸数，默认 2 |
| `min_face_area` | float | 否 | 最小人脸框面积，默认 2500 |
| `min_detection_score` | float | 否 | 最低检测分数，默认 0.85 |

`POST /api/v1/persons/rebuild-index`

全量重建人物库，会清空并重新生成 `persons` 和 `person_faces`，适合调参或修复历史误分。

`GET /api/v1/persons`

查看人物库。

`GET /api/v1/persons/gallery`

浏览器可视化查看人物库、代表人脸和样例人脸。

## 基于人物库以图搜人

`POST /api/v1/search/person-by-image`

上传目标人物照片，先匹配人物库中的 `person`，再展开这个人的逐帧命中、轨迹和连续出现事件。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `files` | file[] | 是 | 目标人物照片，可多张，字段名保持为 `files` |
| `top_k` | int | 否 | 返回前 K 个候选人物，默认 5 |
| `min_score` | float | 否 | 人物匹配最低相似度 |
| `max_gap_sec` | float | 否 | 合并连续出现事件的最大时间间隔，默认 3.0 秒 |

返回内容包含：

- `search_id`
- `engine`
- `persons[]`
- `persons[].score`
- `persons[].representative_frame_url`
- `persons[].matches[]`
- `persons[].trajectory[]`
- `persons[].appearance_events[]`

## 媒体访问

`GET /api/v1/media/frame/{face_id}`

返回命中帧截图。

`GET /api/v1/media/face/{face_id}`

返回按人脸框裁剪出的 JPEG 小图。

## 推荐调用顺序

1. `POST /api/v1/cameras`
2. `POST /api/v1/videos/upload`
3. `POST /api/v1/videos/{video_id}/index`
4. `POST /api/v1/persons/update-index` 或 `POST /api/v1/persons/rebuild-index`
5. `GET /api/v1/persons`
6. `POST /api/v1/search/person-by-image`
7. `GET /api/v1/media/frame/{face_id}` 或 `GET /api/v1/media/face/{face_id}`

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 API Reference

Base URL:

```text
http://127.0.0.1:8000
```

Interactive docs:

```text
http://127.0.0.1:8000/docs
```

## Health Check

`GET /health`

Returns service status, data directory, and recognition engine. Real search expects `face_engine=insightface`.

## Cameras

`POST /api/v1/cameras`

Creates or updates a camera point.

```json
{
  "camera_id": "cam_dorm_gate_01",
  "name": "宿舍区东门摄像头01",
  "location": "宿舍区东门",
  "lat": 31.0001,
  "lng": 121.0001
}
```

`GET /api/v1/cameras`

Returns all cameras.

## Videos

`POST /api/v1/videos/upload`

Uploads a historical surveillance video.

| Field | Type | Required | Description |
|---|---|---:|---|
| `file` | file | Yes | mp4/avi/mov/mkv video |
| `camera_id` | string | Yes | camera ID |
| `recorded_at` | string | No | video start time in ISO format |
| `frame_interval_sec` | float | No | sampling interval, default 1 second |

`GET /api/v1/videos`

Lists uploaded videos.

`POST /api/v1/videos/{video_id}/index`

Samples frames and creates face embeddings for the video.

## Frame-Level Image Search

`POST /api/v1/search/by-image`

Uploads one or more target-person photos and searches similar faces in the frame-level index.

| Field | Type | Required | Description |
|---|---|---:|---|
| `files` | file[] | Yes | one or more target-person images |
| `top_k` | int | No | top frame-level results, default 20 |
| `min_score` | float | No | minimum similarity; default threshold is used when omitted |
| `max_gap_sec` | float | No | max gap for merging continuous appearances, default 3.0 seconds |
| `camera_id` | string | No | camera filter |
| `start_time` | string | No | start-time filter |
| `end_time` | string | No | end-time filter |

Response includes:

- `search_id`: query ID.
- `matches`: frame-level hits sorted by `score` descending.
- `trajectory`: time-sorted route points.
- `appearance_events`: continuous appearances merged by `video_id`, `camera_id`, and time gap.

## Person Index

The person index is clustered from indexed `face_records`; one `person` represents a visually similar group of face records. Prefer incremental update for normal use.

`POST /api/v1/persons/update-index`

Incrementally updates the person index.

| Field | Type | Required | Description |
|---|---|---:|---|
| `merge_threshold` | float | No | edge threshold inside new face records; auto-scanned when omitted |
| `person_match_threshold` | float | No | threshold for matching new clusters to existing people, default 0.68 |
| `min_faces` | int | No | minimum faces per new cluster, default 2 |
| `min_face_area` | float | No | minimum face-box area, default 2500 |
| `min_detection_score` | float | No | minimum detection score, default 0.85 |

`POST /api/v1/persons/rebuild-index`

Fully rebuilds the person index. It clears and regenerates `persons` and `person_faces`, so use it for tuning or correcting previous clustering.

`GET /api/v1/persons`

Lists indexed people.

`GET /api/v1/persons/gallery`

Provides a browser gallery for representative and sample faces.

## Person Search By Image

`POST /api/v1/search/person-by-image`

Uploads target-person images, matches the person index first, then expands the selected people into frame-level hits, trajectory, and appearance events.

| Field | Type | Required | Description |
|---|---|---:|---|
| `files` | file[] | Yes | one or more target-person images; keep field name `files` |
| `top_k` | int | No | top candidate people, default 5 |
| `min_score` | float | No | minimum person-match similarity |
| `max_gap_sec` | float | No | max gap for merging continuous appearances, default 3.0 seconds |

Response includes:

- `search_id`
- `engine`
- `persons[]`
- `persons[].score`
- `persons[].representative_frame_url`
- `persons[].matches[]`
- `persons[].trajectory[]`
- `persons[].appearance_events[]`

## Media Access

`GET /api/v1/media/frame/{face_id}`

Returns the matched frame image.

`GET /api/v1/media/face/{face_id}`

Returns a JPEG face crop from the matched frame.

## Recommended Call Order

1. `POST /api/v1/cameras`
2. `POST /api/v1/videos/upload`
3. `POST /api/v1/videos/{video_id}/index`
4. `POST /api/v1/persons/update-index` or `POST /api/v1/persons/rebuild-index`
5. `GET /api/v1/persons`
6. `POST /api/v1/search/person-by-image`
7. `GET /api/v1/media/frame/{face_id}` or `GET /api/v1/media/face/{face_id}`

<p align="right"><a href="#english">Back to English top</a></p>
