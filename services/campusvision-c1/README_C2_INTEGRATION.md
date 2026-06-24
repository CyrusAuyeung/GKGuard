<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 与 GKGuard C2 对接说明

本文档面向 GKGuard C2 对接 CampusVision C1 的代理层和前端展示。GKGuard C2 不读取 CampusVision C1 本地文件路径，只消费 HTTP JSON 与 media URL；真实部署时应通过 GKGuard C2 后端 `/c1/...` 代理访问 CampusVision C1。

## 服务入口

本地开发默认服务地址：

```text
http://127.0.0.1:8000
```

健康检查：

```http
GET /health
```

## 人脸以图搜人

用于上传证件照、自拍照或多张参考图，返回查询图人脸、选中人脸、相似人物候选、候选人物事件和匹配明细。

```http
POST /api/v1/query/face-image
Content-Type: multipart/form-data
```

常用请求字段：

| 字段 | 类型 | 默认值 | 说明 |
|---|---:|---:|---|
| `files` | file[] | 必填 | 一张或多张查询图片 |
| `query_face_indices` | string | null | JSON 数组或逗号列表，例如 `[0,0]` |
| `query_face_index` | int | null | 单图兼容参数；未传时默认取每张图第 0 张脸 |
| `top_k` | int | 5 | 返回候选人物数，服务端限制 1-50 |
| `min_score` | float | null | 最低相似分；不传使用服务默认策略 |
| `include_candidates` | bool | false | 是否包含候选碎片人物 |
| `event_limit_per_person` | int | 20 | 每个候选人物最多返回多少事件 |
| `match_limit_per_person` | int | 10 | 每个候选人物最多返回多少人脸匹配 |
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

GKGuard C2 展示建议：

- 多个人脸查询图应先展示 `query_faces` 并让用户确认目标人脸。
- 候选人物头像优先使用 `representative_face_crop_url`。
- 候选人物事件列表优先使用 `events`。
- 不要只展示 top1；当 `ambiguous=true` 或多个候选分数接近时，应展示多个候选供用户查看。

## 人物特征检索

用于按时间、摄像头、外观倾向、眼镜状态、上装颜色搜索事件。所有条件都可以为空；接口返回完全匹配事件，也可以返回相似事件并标出不满足项。

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
| `include_candidates` | bool | false | true 时包含候选碎片人物 |
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

`match_type` 语义：

- `exact`：所有已填写条件都满足。
- `partial`：部分条件不满足，但与查询仍相似。

`unknown` 表示 CampusVision C1 模型无法判断，不等同于否定结果。GKGuard C2 展示时应写成“无法判断”，不要把它当作明确不匹配。

## Media URL

CampusVision C1 返回的图片字段是相对 URL。GKGuard C2 后端应通过 `/c1/media/{path}` 代理读取，不应让前端直接访问 CampusVision C1。

常用媒体接口：

| 用途 | CampusVision C1 URL | 常用字段 |
|---|---|---|
| 事件代表现场图 | `/api/v1/media/event/frame/{event_id}` | `representative_frame_url` |
| 事件代表人体图 | `/api/v1/media/event/body/{event_id}` | `representative_body_crop_url` |
| 观测现场图 | `/api/v1/media/observation/frame/{observation_id}` | `frame_url` |
| 观测人体图 | `/api/v1/media/observation/body/{observation_id}` | `body_crop_url` |
| 人脸裁剪图 | `/api/v1/media/face/{face_id}` | `representative_face_crop_url` |
| 人脸所在原始帧 | `/api/v1/media/frame/{face_id}` | `frame_url` |

推荐展示优先级：

1. 事件卡片主图优先使用 `representative_body_crop_url`。
2. 结果详情关键帧优先使用 `representative_frame_url`。
3. 候选头像和记录缩略图优先使用 `representative_face_crop_url`。
4. 图片加载失败时按 `representative_body_crop_url` -> `representative_frame_url` -> `representative_face_crop_url` 回退。

## 错误处理

| 状态码 | 场景 | GKGuard C2 处理建议 |
|---:|---|---|
| 400 | 参数枚举不支持 | 展示参数错误并提示修改 |
| 400 | 人脸查询没有上传图片 | 提示上传图片 |
| 404 | media URL 对应图片不存在 | 使用 fallback 图片或隐藏该图 |
| 500 | CampusVision C1 内部错误 | 展示服务异常，并保留请求条件方便排查 |

## 已知限制

- 当前 CampusVision C1 v1 只保证本地服务和当前数据闭环；真实学校海康流接入需要等真实数据到位后再适配。
- 上装颜色、外观倾向、眼镜状态来自模型和 profile，GKGuard C2 应展示置信度或“无法判断”，不要把模型结果当作绝对事实。
- 事件装束分组仍未达到最终稳定目标；这不阻断人脸查询和人物特征查询接口使用，但影响装束分组类 UI 的精细程度。
- `include_candidates=true` 会提高召回，但可能出现同一人的碎片候选；GKGuard C2 首屏默认建议使用 `false`，需要人工排查时再开放。

## Smoke Test

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

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 And GKGuard C2 Integration Notes

This document is for the GKGuard C2 proxy layer and frontend that integrate with CampusVision C1. GKGuard C2 must not read local CampusVision C1 file paths. It consumes only HTTP JSON and media URLs, and real deployments should access CampusVision C1 through the GKGuard C2 backend `/c1/...` proxy.

## Service Entry

Default local development service URL:

```text
http://127.0.0.1:8000
```

Health check:

```http
GET /health
```

## Image-Based Person Search

Use this endpoint to upload ID photos, selfies, or multiple reference images. It returns detected query faces, selected query faces, similar person candidates, candidate events, and match details.

```http
POST /api/v1/query/face-image
Content-Type: multipart/form-data
```

Common request fields:

| Field | Type | Default | Description |
|---|---:|---:|---|
| `files` | file[] | required | One or more query images |
| `query_face_indices` | string | null | JSON array or comma list, for example `[0,0]` |
| `query_face_index` | int | null | Single-image compatibility field; defaults to face index 0 |
| `top_k` | int | 5 | Number of person candidates, service limit 1-50 |
| `min_score` | float | null | Minimum similarity score; service default applies when omitted |
| `include_candidates` | bool | false | Whether to include candidate fragmented identities |
| `event_limit_per_person` | int | 20 | Maximum events per candidate person |
| `match_limit_per_person` | int | 10 | Maximum face matches per candidate person |
| `camera_id` | string | null | Camera filter |
| `start_time` | string | null | Start time filter, ISO string |
| `end_time` | string | null | End time filter, ISO string |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query/face-image \
  -F "files=@/path/to/id_photo.jpg" \
  -F "top_k=5" \
  -F "include_candidates=true" \
  -F "event_limit_per_person=10"
```

Response summary:

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

GKGuard C2 display guidance:

- Multi-face query images should show `query_faces` first and let the user confirm the target face.
- Candidate portraits should prefer `representative_face_crop_url`.
- Candidate event lists should prefer `events`.
- Do not display only top1. When `ambiguous=true` or candidate scores are close, show multiple candidates for user inspection.

## Person-Attribute Search

Use this endpoint to search events by time, camera, appearance presentation, glasses status, and upper-body color. Every condition may be empty. The endpoint returns exact matches and can also return similar events with failed conditions.

```http
POST /api/v1/query/person-attributes
Content-Type: application/json
```

Request fields:

| Field | Type | Default | Description |
|---|---:|---:|---|
| `time_range.start_time` | string | null | Start time, ISO string |
| `time_range.end_time` | string | null | End time, ISO string |
| `camera_ids` | string[] | [] | Camera IDs; empty means no camera filter |
| `gender_presentation` | string[] | [] | Appearance presentation; empty means no filter |
| `glasses_status` | string[] | [] | Glasses status; empty means no filter |
| `upper_colors` | string[] | [] | Upper-body colors; empty means no filter |
| `person_scope` | string | `stable` | `stable`, `identified`, `all`, or `unidentified` |
| `include_candidates` | bool | false | Include fragmented candidate identities when true |
| `include_near_misses` | bool | true | Whether to return partial similar events |
| `min_score` | float | null | Minimum partial score |
| `limit` | int | 50 | Result count, service limit 1-200 |
| `offset` | int | 0 | Pagination offset |
| `candidate_pool_size` | int | 5000 | Backend candidate-pool limit |

Enum values:

```text
gender_presentation: masculine, feminine, neutral, unknown
glasses_status: glasses, no_glasses, unknown
upper_colors: black, white, gray, red, orange, yellow, green, blue, purple, brown, pink, striped, other, unknown
person_scope: stable, identified, all, unidentified
```

`match_type` semantics:

- `exact`: all provided conditions match.
- `partial`: some conditions do not match, but the event is still similar.

`unknown` means the CampusVision C1 model could not determine the attribute. It is not a negative result. GKGuard C2 should display it as "unable to determine" rather than a definite mismatch.

## Media URLs

CampusVision C1 returns relative image URLs. The GKGuard C2 backend should read them through `/c1/media/{path}` and should not let the frontend call CampusVision C1 directly.

Common media endpoints:

| Purpose | CampusVision C1 URL | Common Field |
|---|---|---|
| Event representative scene frame | `/api/v1/media/event/frame/{event_id}` | `representative_frame_url` |
| Event representative body crop | `/api/v1/media/event/body/{event_id}` | `representative_body_crop_url` |
| Observation scene frame | `/api/v1/media/observation/frame/{observation_id}` | `frame_url` |
| Observation body crop | `/api/v1/media/observation/body/{observation_id}` | `body_crop_url` |
| Face crop | `/api/v1/media/face/{face_id}` | `representative_face_crop_url` |
| Original frame for a face record | `/api/v1/media/frame/{face_id}` | `frame_url` |

Recommended display priority:

1. Event cards prefer `representative_body_crop_url`.
2. Result detail keyframes prefer `representative_frame_url`.
3. Candidate portraits and record thumbnails prefer `representative_face_crop_url`.
4. If an image fails to load, fall back in this order: `representative_body_crop_url` -> `representative_frame_url` -> `representative_face_crop_url`.

## Error Handling

| Status | Scenario | GKGuard C2 Handling |
|---:|---|---|
| 400 | Unsupported enum parameter | Show a parameter error and ask the user to adjust it |
| 400 | Face query has no uploaded image | Ask the user to upload an image |
| 404 | Media URL image does not exist | Use a fallback image or hide the image |
| 500 | CampusVision C1 internal error | Show a service error and preserve the request conditions for debugging |

## Known Limitations

- Current CampusVision C1 v1 guarantees only the local service and current data loop. Real school Hikvision stream integration still needs adaptation after real data is available.
- Upper-body color, appearance presentation, and glasses status come from models and profiles. GKGuard C2 should display confidence or "unable to determine" and should not treat model output as absolute fact.
- Event outfit grouping has not reached the final stability target. This does not block the face-query or person-attribute query endpoints, but affects the precision of outfit-grouping UI.
- `include_candidates=true` improves recall but may return fragmented candidates for the same person. GKGuard C2 should default to `false` on the first screen and expose it only for manual investigation.

## Smoke Test

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

<p align="right"><a href="#english">Back to English top</a></p>
