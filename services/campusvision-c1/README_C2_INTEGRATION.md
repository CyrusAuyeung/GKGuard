# CampusVision C1 to C2 Integration Notes

版本：`speng/c1-person-events@2ba9064`

本文档给 C2 对接使用，描述 C1 v1 当前稳定建议调用的接口、字段语义和展示约定。C2 不需要读取 C1 本地文件路径，只消费 HTTP JSON 和 media URL。

## Base URL

本地开发默认：

```text
http://127.0.0.1:8000
```

健康检查：

```http
GET /health
```

## 核心接口

### 1. 人脸以图搜人

用于上传证件照、自拍照或多张参考图，返回相似人物候选，并在每个候选人物下带出事件。

```http
POST /api/v1/query/face-image
Content-Type: multipart/form-data
```

请求参数：

| 字段 | 类型 | 默认值 | 说明 |
|---|---:|---:|---|
| `files` | file[] | 必填 | 一张或多张查询图片 |
| `query_face_indices` | string | null | JSON 数组或逗号列表，例如 `[0,0]`，表示每张图选第几张脸 |
| `query_face_index` | int | null | 单图兼容参数；未传时默认取每张图第 0 张脸 |
| `top_k` | int | 5 | 返回候选人物数，服务端限制 1-50 |
| `min_score` | float | null | 最低相似分；不传使用服务默认策略 |
| `include_candidates` | bool | false | 是否包含候选碎片人物；默认只返回稳定人物 |
| `event_limit_per_person` | int | 20 | 每个候选人物最多返回多少事件，服务端限制 0-200 |
| `match_limit_per_person` | int | 10 | 每个候选人物最多返回多少人脸匹配，服务端限制 0-200 |
| `include_events` | bool | true | 是否返回候选人物事件 |
| `include_matches` | bool | true | 是否返回人脸匹配明细 |
| `camera_id` | string | null | 限定摄像头 |
| `start_time` | string | null | 限定起始时间，ISO 字符串 |
| `end_time` | string | null | 限定结束时间，ISO 字符串 |

示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/face-image \
  -F "files=@/path/to/id_photo.jpg" \
  -F "top_k=5" \
  -F "include_candidates=true" \
  -F "event_limit_per_person=10"
```

返回结构摘要：

```json
{
  "search_id": "uuid",
  "engine": "insightface",
  "query_faces": [],
  "selected_query_faces": [],
  "reference_consistency": {
    "status": "single_reference"
  },
  "candidates": [
    {
      "person_id": "person_xxx",
      "identity_status": "stable",
      "is_stable_identity": true,
      "score": 0.912936,
      "confidence": "high",
      "representative_face_crop_url": "/api/v1/media/face/face_xxx",
      "attributes": {
        "latest_upper_color": "black",
        "gender_presentation": "masculine",
        "glasses_status": "no_glasses"
      },
      "events": [],
      "matches": []
    }
  ],
  "ambiguous": false,
  "warnings": []
}
```

C2 展示建议：

- 候选人物头像：`candidate.representative_face_crop_url`
- 候选人物事件列表：`candidate.events`
- 不要只展示 top1；当 `ambiguous=true` 或多个候选分数接近时，应展示多个候选供用户查看。

### 2. 人物特征搜索

用于按时间、摄像头、外观倾向、眼镜状态、上装颜色搜索事件。所有条件都可以为空。返回完全符合条件的事件，也可以返回相似事件并标出不满足项。

```http
POST /api/v1/query/person-attributes
Content-Type: application/json
```

请求字段：

| 字段 | 类型 | 默认值 | 说明 |
|---|---:|---:|---|
| `time_range.start_time` | string | null | 起始时间，ISO 字符串 |
| `time_range.end_time` | string | null | 结束时间，ISO 字符串 |
| `camera_ids` | string[] | [] | 摄像头 ID 列表；空表示不限 |
| `gender_presentation` | string[] | [] | 外观倾向；空表示不限 |
| `glasses_status` | string[] | [] | 眼镜状态；空表示不限 |
| `upper_colors` | string[] | [] | 上装颜色；空表示不限 |
| `person_scope` | string | `stable` | `stable`、`identified`、`all`、`unidentified` |
| `include_candidates` | bool | false | true 时包含候选碎片人物，相当于扩大到 identified |
| `include_near_misses` | bool | true | 是否返回 partial 相似事件 |
| `min_score` | float | null | partial 最低分 |
| `limit` | int | 50 | 返回数量，服务端限制 1-200 |
| `offset` | int | 0 | 分页偏移 |
| `candidate_pool_size` | int | 5000 | 后端候选池上限 |

枚举值：

```text
gender_presentation: masculine, feminine, neutral, unknown
glasses_status: glasses, no_glasses, unknown
upper_colors: black, white, gray, red, orange, yellow, green, blue, purple, brown, pink, striped, other, unknown
person_scope: stable, identified, all, unidentified
```

示例：

```json
{
  "time_range": {
    "start_time": "2026-06-23T08:00:00",
    "end_time": "2026-06-23T09:00:00"
  },
  "camera_ids": ["p1e_s1_c1", "p1e_s1_c2"],
  "gender_presentation": ["masculine"],
  "glasses_status": ["no_glasses"],
  "upper_colors": ["black", "gray"],
  "include_candidates": true,
  "include_near_misses": true,
  "limit": 20,
  "offset": 0
}
```

返回结构摘要：

```json
{
  "query_id": "attr_query_xxx",
  "created_at": "2026-06-24T05:32:39Z",
  "query": {},
  "summary": {
    "scanned_events": 382,
    "total_matches": 382,
    "exact_matches": 69,
    "partial_matches": 313,
    "returned": 20
  },
  "results": [
    {
      "event_id": "event_xxx",
      "person_id": "person_xxx",
      "identity_status": "stable",
      "score": 1.0,
      "match_type": "exact",
      "failed_conditions": [],
      "condition_scores": {
        "glasses_status": 1.0,
        "upper_color": 1.0
      },
      "camera_id": "p1e_s1_c1",
      "start_time": "2026-06-23T08:00:55",
      "representative_frame_url": "/api/v1/media/event/frame/event_xxx",
      "representative_body_crop_url": "/api/v1/media/event/body/event_xxx",
      "representative_face_crop_url": "/api/v1/media/face/face_xxx",
      "upper_color": "black",
      "gender_presentation": "masculine",
      "glasses_status": "no_glasses"
    }
  ]
}
```

`match_type` 语义：

- `exact`: 所有已填写条件都满足。
- `partial`: 部分条件不满足，但与查询仍相似。

`failed_conditions` 示例：

```json
[
  {
    "field": "upper_color",
    "expected": ["black"],
    "actual": "striped",
    "actual_confidence": 0.3984,
    "reason": "upper_color_mismatch"
  }
]
```

C2 展示建议：

- 搜索结果列表优先展示 `exact`，再展示 `partial`。
- `partial` 必须把 `failed_conditions` 展示出来，例如“上装颜色不完全匹配：期望 black，实际 striped”。
- `unknown` 表示 C1 模型无法判断，不等同于否定结果；展示时建议写“无法判断”。

## Media URL

C1 返回的图片字段都是相对 URL。C2 应拼接 base URL 使用。

### 事件代表现场图

```http
GET /api/v1/media/event/frame/{event_id}
```

对应字段：

```text
representative_frame_url
```

用途：查看原始监控帧上下文。

### 事件代表人体图

```http
GET /api/v1/media/event/body/{event_id}
```

对应字段：

```text
representative_body_crop_url
```

用途：事件卡片主图，优先展示这个字段。

### 事件代表人脸图

```http
GET /api/v1/media/face/{face_id}
```

对应字段：

```text
representative_face_crop_url
```

用途：头像、小脸图、候选人物对比。

### 原始人脸记录所在帧

```http
GET /api/v1/media/frame/{face_id}
```

用途：按 face record 查看该人脸所在原始帧。事件列表优先使用 `/media/event/frame/{event_id}`。

## 推荐 UI 行为

1. 人脸查询页
   - 支持上传多张图。
   - 展示 `query_faces` 供用户确认选中的脸。
   - 候选人物按 `score` 排序展示。
   - 每个候选人物下展示 `events`，事件主图用 `representative_body_crop_url`，小头像用 `representative_face_crop_url`。

2. 人物特征搜索页
   - 条件筛选器支持空条件。
   - 结果分区展示：完全匹配、相似结果。
   - 对 `partial` 结果展示不满足原因。
   - 图片加载失败时 fallback 顺序建议：`representative_body_crop_url` -> `representative_frame_url` -> `representative_face_crop_url`。

3. 时间和摄像头
   - 时间字段使用 `start_time/end_time` 做绝对时间展示。
   - 视频内时间可使用 `start_time_display/end_time_display`。
   - 摄像头展示优先 `camera_name`，为空时展示 `camera_id`。

## Error Handling

常见错误：

| 状态码 | 场景 | C2 处理建议 |
|---:|---|---|
| 400 | 参数枚举不支持，例如 `glasses_status=["maybe"]` | 展示参数错误并提示用户修改 |
| 400 | 人脸查询没有上传图片 | 提示上传图片 |
| 404 | media URL 对应图片不存在 | 使用 fallback 图片或隐藏该图 |
| 500 | C1 内部错误 | 展示服务异常，并保留请求条件方便排查 |

## Known Limitations

- 当前 C1 v1 只保证本地服务和当前数据闭环；真实学校海康流接入还需要等真实数据到位后再适配。
- 上装颜色、外观倾向、眼镜状态来自模型/profile，C2 应展示置信度或“无法判断”，不要把模型结果当作绝对事实。
- 事件装束分组当前还未达到最终目标：最近评估 pairwise F1 `0.888287`，purity `0.916667`。这不影响两个查询接口使用，但影响“装束分组”类 UI 的精细程度。
- `include_candidates=true` 会包含候选碎片人物，召回更高，但可能出现同一人的碎片候选；默认建议 C2 首屏使用 `false`。

## Quick Smoke Tests

```bash
curl -sS http://127.0.0.1:8000/health
```

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/query/person-attributes \
  -H "Content-Type: application/json" \
  -d '{"upper_colors":["black"],"glasses_status":["no_glasses"],"include_candidates":true,"limit":3}'
```

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/query/face-image \
  -F "files=@/path/to/query.jpg" \
  -F "top_k=5" \
  -F "include_candidates=true"
```
