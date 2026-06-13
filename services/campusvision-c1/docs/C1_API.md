# C1 API 说明

Base URL:

```text
http://127.0.0.1:8000
```

交互式文档：

```text
http://127.0.0.1:8000/docs
```

---

## 1. 健康检查

### GET `/health`

返回服务状态、数据目录、识别引擎。

---

## 2. 摄像头点位

### POST `/api/v1/cameras`

创建或更新摄像头点位。

请求体：

```json
{
  "camera_id": "cam_dorm_gate_01",
  "name": "宿舍区东门摄像头01",
  "location": "宿舍区东门",
  "lat": 31.0001,
  "lng": 121.0001
}
```

### GET `/api/v1/cameras`

返回所有摄像头点位。

---

## 3. 视频

### POST `/api/v1/videos/upload`

上传一个历史监控视频。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| file | file | 是 | mp4/avi/mov/mkv 等视频 |
| camera_id | string | 是 | 摄像头 ID |
| recorded_at | string | 否 | 视频起始时间，ISO 格式，例如 `2026-07-01T09:00:00` |
| frame_interval_sec | float | 否 | 抽帧间隔，默认 1 秒 |

返回：

```json
{
  "video_id": "...",
  "camera_id": "...",
  "status": "uploaded"
}
```

### GET `/api/v1/videos`

查看已上传视频。

### POST `/api/v1/videos/{video_id}/index`

对视频抽帧并建立人脸/目标向量索引。

返回：

```json
{
  "video_id": "...",
  "indexed_faces": 12,
  "status": "indexed"
}
```

---

## 4. 以图搜人

### POST `/api/v1/search/by-image`

上传一张或多张目标人物照片，在历史监控索引中检索相似人脸。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| files | file[] | 是 | 目标人物照片，可多张 |
| top_k | int | 否 | 返回前 K 个逐帧结果，默认 20 |
| min_score | float | 否 | 最低相似度。不传时使用 InsightFace 默认值 0.30 |
| max_gap_sec | float | 否 | 合并连续出现事件的最大时间间隔，默认 3.0 秒 |
| camera_id | string | 否 | 限定摄像头 |
| start_time | string | 否 | 限定开始时间，ISO 格式 |
| end_time | string | 否 | 限定结束时间，ISO 格式 |

返回：

```json
{
  "search_id": "...",
  "matches": [
    {
      "face_id": "...",
      "score": 0.82,
      "camera_id": "cam_dorm_gate_01",
      "camera_name": "宿舍区东门摄像头01",
      "location": "宿舍区东门",
      "video_id": "...",
      "video_timestamp_sec": 152.0,
      "captured_at": "2026-07-01T09:02:32",
      "frame_url": "/api/v1/media/frame/..."
    }
  ],
  "trajectory": [
    {
      "time": "2026-07-01T09:02:32",
      "camera_id": "cam_dorm_gate_01",
      "location": "宿舍区东门",
      "lat": 31.0001,
      "lng": 121.0001,
      "video_timestamp_sec": 152.0,
      "captured_at": "2026-07-01T09:02:32",
      "time_display": "00:02:32.000",
      "score": 0.82,
      "frame_url": "/api/v1/media/frame/..."
    }
  ],
  "appearance_events": [
    {
      "appearance_id": "...",
      "video_id": "...",
      "camera_id": "cam_dorm_gate_01",
      "camera_name": "宿舍区东门摄像头01",
      "location": "宿舍区东门",
      "lat": 31.0001,
      "lng": 121.0001,
      "start_sec": 0.0,
      "end_sec": 3.999,
      "duration_sec": 3.999,
      "start_time_display": "00:00:00.000",
      "end_time_display": "00:00:03.999",
      "hit_count": 4,
      "best_score": 0.848343,
      "best_face_id": "...",
      "best_frame_url": "/api/v1/media/frame/...",
      "match_face_ids": ["...", "..."],
      "best_match": { "face_id": "...", "score": 0.848343 }
    }
  ]
}
```

`matches` 按 `score` 从高到低排序；`trajectory` 按时间排序；`appearance_events` 按 `start_sec` 从早到晚排序。同一 `video_id`、同一 `camera_id` 下，相邻命中的 `video_timestamp_sec` 差值小于等于 `max_gap_sec` 时会合并为同一个出现事件。

---

## 5. 人物库

人物库会从已经建好的 `face_records` 中聚类生成，一个 `person` 代表一组视觉上相似的人脸记录。系统会先用严格质量过滤生成高置信人物簇，再从未入库的人脸中恢复持续出现的弱稳定簇，用于召回后方小脸、低头人等检测分偏低但多次出现的人物。常规使用时调用增量更新接口：系统只处理还没有归入人物库的新 `face_records`，能匹配旧人物就追加，匹配不到才创建新人物。全量重建接口保留为调参或校正历史误分时使用。

### POST `/api/v1/persons/update-index`

增量更新人物库。适合每次上传并索引新视频后调用。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| merge_threshold | float | 否 | 手动指定新 face_records 内部连边相似度阈值。不传时自动扫描阈值 |
| person_match_threshold | float | 否 | 新簇匹配已有人物的相似度阈值，默认 0.68 |
| min_faces | int | 否 | 新簇至少包含多少张人脸才保留，默认 2 |
| min_face_area | float | 否 | 参与人物库聚类的最小人脸框面积，默认 2500 |
| min_detection_score | float | 否 | 参与人物库聚类的最低检测分数，默认 0.85 |

返回字段与全量重建一致。`cluster_quality.created_persons` 表示本次新增人物数量，`cluster_quality.updated_persons` 表示本次追加过新脸的旧人物数量。增量更新不会清空已有人物库，因此已有 `person_id` 会被保留。
`cluster_quality.weak_recovered_clusters` 表示本次从弱稳定簇中额外恢复的人物簇数量，`cluster_quality.weak_recovered_faces` 表示这些簇关联的人脸数量。

### POST `/api/v1/persons/rebuild-index`

从当前全部人脸索引全量重建人物库。它会清空 `persons` 和 `person_faces` 后重新聚类，因此会重新生成 `person_id`。适合调参、修复历史误分或数据量不大时做整体校正。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| merge_threshold | float | 否 | 手动指定人脸连边相似度阈值。不传时自动扫描阈值 |
| min_faces | int | 否 | 至少包含多少张人脸才保留为人物，默认 2 |
| min_face_area | float | 否 | 参与人物库聚类的最小人脸框面积，默认 2500 |
| min_detection_score | float | 否 | 参与人物库聚类的最低检测分数，默认 0.85 |

返回：

```json
{
  "persons": 3,
  "linked_faces": 34,
  "source_faces": 42,
  "merge_threshold": 0.72,
  "min_faces": 2,
  "min_face_area": 2500.0,
  "min_detection_score": 0.85,
  "low_quality_faces": 5,
  "noise_faces": 8,
  "cluster_quality": {
    "score": 0.812345,
    "mean_intra_similarity": 0.83,
    "max_inter_similarity": 0.48,
    "coverage": 0.91,
    "same_frame_conflicts": 0,
    "singleton_ratio": 0.15,
    "selected_clusters": 3
  },
  "algorithm": "graph_auto_threshold"
}
```

默认模式不会要求提前知道视频里有几个人。系统会过滤低质量人脸，扫描多个相似度阈值，并选择簇内相似度、簇间分离度、覆盖率和同帧冲突综合表现更好的聚类结果。`noise_faces` 包含低质量人脸、小簇和未能可靠归入人物库的人脸。

### GET `/api/v1/persons`

查看人物库。

返回：

```json
[
  {
    "person_id": "person_...",
    "display_name": null,
    "representative_face_id": "...",
    "representative_frame_url": "/api/v1/media/frame/...",
    "representative_face_crop_url": "/api/v1/media/face/...",
    "face_count": 12,
    "first_seen_at": null,
    "last_seen_at": null
  }
]
```

### GET `/api/v1/persons/gallery`

在浏览器中可视化查看人物库。每个 `person` 会显示一张按 bbox 裁剪出的代表人脸、关联人脸数量、代表 `face_id`、时间范围和若干样例脸。

### POST `/api/v1/search/person-by-image`

上传目标人物照片，先匹配人物库中的 `person`，再展开这个人的逐帧命中、轨迹和连续出现事件。

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| files | file[] | 是 | 目标人物照片，可多张，字段名保持为 `files` |
| top_k | int | 否 | 返回前 K 个候选人物，默认 5 |
| min_score | float | 否 | 人物匹配最低相似度。不传时使用 InsightFace 默认值 0.30 |
| max_gap_sec | float | 否 | 合并连续出现事件的最大时间间隔，默认 3.0 秒 |

返回：

```json
{
  "search_id": "...",
  "engine": "insightface",
  "persons": [
    {
      "person_id": "person_...",
      "score": 0.86,
      "representative_face_id": "...",
      "representative_frame_url": "/api/v1/media/frame/...",
      "face_count": 12,
      "matches": [],
      "trajectory": [],
      "appearance_events": []
    }
  ]
}
```

---

## 6. 媒体访问

### GET `/api/v1/media/frame/{face_id}`

返回命中帧截图。

### GET `/api/v1/media/face/{face_id}`

返回从命中帧中按人脸框裁剪出的 JPEG 小图，主要用于人物库可视化和人工核查。

---

## 7. 推荐调用顺序

1. `POST /api/v1/cameras`
2. `POST /api/v1/videos/upload`
3. `POST /api/v1/videos/{video_id}/index`
4. `POST /api/v1/persons/rebuild-index`
5. `GET /api/v1/persons`
6. `POST /api/v1/search/person-by-image`
7. `POST /api/v1/search/by-image`，可继续用于逐帧检索对比
8. `GET /api/v1/media/frame/{face_id}`
