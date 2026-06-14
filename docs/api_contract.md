<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# API 合同

本文中的 GKGuard C2 指桌面工作台和本地 FastAPI 代理层；CampusVision C1 指独立的视频检索服务。GKGuard C2 前端只访问 GKGuard C2 API；所有真实 CampusVision C1 检索都通过 GKGuard C2 的 `/c1/...` 代理完成。

GKGuard C2 本地开发常用地址：

```text
http://127.0.0.1:8002
```

CampusVision C1 适配器默认本机隧道地址：

```text
C1_BASE_URL=http://127.0.0.1:18000
```

安装版 `v0.1.18` 还内置候选地址 `http://127.0.0.1:18000` 和 `http://10.4.167.122:8000`，优先使用本机 SSH 隧道。GKGuard C2 会自动探测候选 CampusVision C1 服务；若未通过隧道连接，桌面端会在软件内提示输入服务器密码、显示连接进度并建立 SSH 隧道。真实检索遇到 CampusVision C1 502/503/504 时，适配器会尝试下一个候选地址。本版保持上传、检查更新、路线、导出和信息提示图标细节修正，保持路线页 `重新上传` 为最左侧操作，并统一桌面 CampusVision C1 密码窗口文案。

GKGuard C2 前端只访问 GKGuard C2 API。真实 CampusVision C1 检索通过 GKGuard C2 的 `/c1/...` 代理完成；旧 mock API 继续保留用于离线演示和非 CampusVision C1 流程。

## 系统

`GET /health`

返回 GKGuard C2 服务状态。

## CampusVision C1 适配器状态

`GET /c1/status`

返回 CampusVision C1 服务可达性与健康状态。

关键字段：

- `baseUrl`：当前用于展示或请求的 CampusVision C1 地址。
- `selectedBaseUrl`：自动探测后选中的健康 CampusVision C1 地址；未选中时为 `null`。
- `candidateUrls`：本次探测的候选 CampusVision C1 地址列表。
- `candidates[]`：每个候选地址的 OpenAPI 与 `/health` 探测结果。
- `reachable`：当前 `baseUrl` 是否能读取 CampusVision C1 OpenAPI。
- `healthOk`：当前 `baseUrl` 的 CampusVision C1 `/health` 是否成功。
- `health`：CampusVision C1 health payload。
- `error` / `healthError`：连接或 HTTP 错误。

## CampusVision C1 人物与视频

`GET /c1/persons`

返回：

```json
{
  "items": []
}
```

GKGuard C2 会把 CampusVision C1 人物代表帧和人脸裁剪图 URL 改写为 `/c1/media/...`。

`GET /c1/videos`

返回：

```json
{
  "items": []
}
```

## CampusVision C1 以图搜人

`POST /c1/search/person-by-image`

Multipart 表单字段：

- `file`：GKGuard C2 前端上传的一张查询图片。

Query 参数：

- `top_k`：默认 `5`，范围 `1..20`。
- `min_score`：可选，相似度阈值，范围 `0..1`。
- `max_gap_sec`：默认 `3.0`。

GKGuard C2 会把 `file` 转发成 CampusVision C1 所需的 `files` 字段，并返回归一化视图模型：

- `source`：`c1`。
- `searchId`：CampusVision C1 search ID。
- `engine`：通常为 `insightface`。
- `warning` / `ambiguous`：CampusVision C1 低置信或歧义提示。
- `person`：当前 UI 选中的候选人物。
- `records[]`：结果页关键帧记录，`frameUrl` 同时用于记录缩略图和详情关键帧。
- `routePoints[]`：路线图轨迹点。
- `appearanceEvents[]`：CampusVision C1 连续出现事件。
- `raw`：原始 CampusVision C1 响应，保留用于调试和后续映射。

如果 CampusVision C1 服务不可用，GKGuard C2 返回结构化错误；当前桌面 UI 会先触发 CampusVision C1 连接窗口并重试一次，仍失败时才回退本地模拟数据。

## CampusVision C1 媒体代理

`GET /c1/media/{kind}/{face_id}`

路径参数：

- `kind`：`frame` 或 `face`。
- `face_id`：CampusVision C1 face record ID。

返回 CampusVision C1 图片字节，通常为 `image/jpeg`。

## 人员搜索（mock）

`GET /search/persons`

Query 参数：

- `keyword`
- `name`
- `student_id`
- `phone`
- `email`
- `identity_type`

返回本地 demo 人员记录。

## 人员画像（mock）

`GET /search/persons/{person_id}/profile`

返回人员基础信息、关联车辆、快照、门禁记录和告警。

## 车辆搜索（mock）

`GET /search/vehicles`

Query 参数：

- `keyword`
- `plate_number`
- `color`
- `brand`
- `vehicle_type`
- `owner_person_id`

返回本地 demo 车辆记录。

## 快照记录（mock）

`GET /search/records`

Query 参数：

- `person_id`
- `vehicle_id`
- `camera_id`
- `location`
- `start_time`
- `end_time`
- `min_similarity`

返回带摄像头名称、位置和地图坐标的快照记录。

## 图片搜索（legacy mock）

`POST /search/image`

Multipart 表单字段：

- `file`：查询图片。

Query 参数：

- `top_k`：默认 `5`。
- `min_similarity`：默认 `0.72`。

返回本地 Top-K mock 图片检索结果。真实 CampusVision C1 人脸检索请使用 `/c1/search/person-by-image`。

## 时间线（mock）

`GET /persons/{person_id}/timeline`

Query 参数：

- `start_time`
- `end_time`
- `min_similarity`

返回排序后的时间线点和摘要。

## 事件记录

`GET /events/{event_id}/related-records`

返回告警详情、相关快照、可选人员时间线和文本摘要。

`GET /events/{event_id}/report`

返回结构化案件报告。

`POST /events/{event_id}/disposition`

请求体：

```json
{
  "result": "confirmed_safe",
  "handler": "security_desk_demo",
  "notes": "Subject confirmed by timeline and field review."
}
```

返回模拟归档处置记录。

`GET /events/{event_id}/case-package`

返回案件包，包括事件、对象信息、报告、时间线、证据快照、审计日志和处理清单。

## 审计日志

`GET /audit/logs`

Query 参数：

- `limit`：默认 `20`，最大 `100`。

返回敏感 demo 操作产生的审计日志。

## CampusCar / UE 占位

`POST /car-tasks/mock-dispatch`

请求体示例：

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "route_id": "ROUTE-DEMO-01",
  "reason": "field_review",
  "robot_id": "CAR-DEMO-01",
  "robot_type": "campusCar",
  "speed_mps": 0.8,
  "command_topic": "/U2RTopic_Command",
  "position_topic": "/R2UTopic_Pos",
  "status_topic": "/R2UTopic_Text"
}
```

返回模拟任务、`bridge_contract` 和视频 URL 占位字段。

`GET /car-tasks/ue-bridge-status`

返回 CampusCar/UE bridge 的确定性 mock 状态，不探测真实 ROS2 服务。

## 轻量 AI 解析

`POST /ai/parse-query`

请求体：

```json
{
  "query": "find red car near parking at night"
}
```

返回可映射到搜索参数的规则化过滤条件。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# API Contract

Here, GKGuard C2 means the desktop workbench plus local FastAPI proxy layer, and CampusVision C1 means the standalone video-search service. The GKGuard C2 frontend calls GKGuard C2 APIs only; all real CampusVision C1 search goes through GKGuard C2 `/c1/...` proxy endpoints.

Common local GKGuard C2 development URL:

```text
http://127.0.0.1:8002
```

Default local CampusVision C1 tunnel URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

The packaged `v0.1.18` app also has built-in candidates `http://127.0.0.1:18000` and `http://10.4.167.122:8000`, preferring the local SSH tunnel. GKGuard C2 probes candidate CampusVision C1 URLs automatically; if the tunnel is not connected, the desktop app prompts for the server password inside the app, shows connection progress, and creates the SSH tunnel. When real search hits CampusVision C1 502/503/504, the adapter tries the next candidate URL. This version keeps the refined upload, update, route, export, and information icons, keeps the route-screen `重新上传` action as the leftmost control, and standardizes the desktop CampusVision C1 password-window wording.

The GKGuard C2 frontend calls GKGuard C2 APIs only. Real CampusVision C1 search is exposed through GKGuard C2 `/c1/...` proxy endpoints. Legacy mock APIs remain available for offline demos and non-CampusVision C1 workflows.

## System

`GET /health`

Returns GKGuard C2 service status.

## CampusVision C1 Adapter Status

`GET /c1/status`

Returns CampusVision C1 service reachability and health information.

Important fields:

- `baseUrl`: CampusVision C1 URL currently used for display or requests.
- `selectedBaseUrl`: healthy CampusVision C1 URL selected by auto-probing, or `null` if none is selected.
- `candidateUrls`: candidate CampusVision C1 URLs checked during this probe.
- `candidates[]`: OpenAPI and `/health` probe result for each candidate.
- `reachable`: whether the current `baseUrl` can read CampusVision C1 OpenAPI metadata.
- `healthOk`: whether the current `baseUrl` succeeds on CampusVision C1 `/health`.
- `health`: CampusVision C1 health payload.
- `error` / `healthError`: connection or HTTP failures.

## CampusVision C1 People And Videos

`GET /c1/persons`

Returns:

```json
{
  "items": []
}
```

GKGuard C2 rewrites CampusVision C1 representative frame and face-crop URLs to `/c1/media/...`.

`GET /c1/videos`

Returns:

```json
{
  "items": []
}
```

## CampusVision C1 Person Search By Image

`POST /c1/search/person-by-image`

Multipart form field:

- `file`: one query image uploaded by the GKGuard C2 frontend.

Query parameters:

- `top_k`: default `5`, range `1..20`.
- `min_score`: optional similarity threshold, range `0..1`.
- `max_gap_sec`: default `3.0`.

GKGuard C2 forwards `file` as CampusVision C1's required `files` field and returns a normalized view model:

- `source`: `c1`.
- `searchId`: CampusVision C1 search ID.
- `engine`: usually `insightface`.
- `warning` / `ambiguous`: CampusVision C1 low-confidence or ambiguity information.
- `person`: selected candidate person for the current UI.
- `records[]`: keyframe records for the result screen; `frameUrl` powers both record thumbnails and the detail keyframe.
- `routePoints[]`: route points for the route screen.
- `appearanceEvents[]`: CampusVision C1 appearance events.
- `raw`: original CampusVision C1 response for debugging and future mapping.

If the CampusVision C1 service is unavailable, GKGuard C2 returns a structured error. The current desktop UI first opens the CampusVision C1 connection prompt and retries once; it falls back to local mock data only if CampusVision C1 is still unavailable.

## CampusVision C1 Media Proxy

`GET /c1/media/{kind}/{face_id}`

Path parameters:

- `kind`: `frame` or `face`.
- `face_id`: CampusVision C1 face record ID.

Returns CampusVision C1 image bytes, usually as `image/jpeg`.

## Person Search (Mock)

`GET /search/persons`

Query parameters:

- `keyword`
- `name`
- `student_id`
- `phone`
- `email`
- `identity_type`

Returns local demo person records.

## Person Profile (Mock)

`GET /search/persons/{person_id}/profile`

Returns base person data, linked vehicles, snapshots, access records, and alerts.

## Vehicle Search (Mock)

`GET /search/vehicles`

Query parameters:

- `keyword`
- `plate_number`
- `color`
- `brand`
- `vehicle_type`
- `owner_person_id`

Returns local demo vehicle records.

## Snapshot Records (Mock)

`GET /search/records`

Query parameters:

- `person_id`
- `vehicle_id`
- `camera_id`
- `location`
- `start_time`
- `end_time`
- `min_similarity`

Returns snapshot records enriched with camera name, location, and map coordinates.

## Image Search (Legacy Mock)

`POST /search/image`

Multipart form field:

- `file`: query image.

Query parameters:

- `top_k`: default `5`.
- `min_similarity`: default `0.72`.

Returns local Top-K mock image-search matches. Use `/c1/search/person-by-image` for real CampusVision C1 face search.

## Timeline (Mock)

`GET /persons/{person_id}/timeline`

Query parameters:

- `start_time`
- `end_time`
- `min_similarity`

Returns sorted timeline points and a summary.

## Event Records

`GET /events/{event_id}/related-records`

Returns alert detail, related snapshots, an optional person timeline, and a text summary.

`GET /events/{event_id}/report`

Returns a structured case report.

`POST /events/{event_id}/disposition`

Body:

```json
{
  "result": "confirmed_safe",
  "handler": "security_desk_demo",
  "notes": "Subject confirmed by timeline and field review."
}
```

Returns a mock archived disposition record.

`GET /events/{event_id}/case-package`

Returns a case package containing event detail, subject data, report, timeline, evidence snapshots, audit logs, and an action checklist.

## Audit Logs

`GET /audit/logs`

Query parameters:

- `limit`: default `20`, max `100`.

Returns audit logs generated by sensitive demo actions.

## CampusCar / UE Placeholder

`POST /car-tasks/mock-dispatch`

Example body:

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "route_id": "ROUTE-DEMO-01",
  "reason": "field_review",
  "robot_id": "CAR-DEMO-01",
  "robot_type": "campusCar",
  "speed_mps": 0.8,
  "command_topic": "/U2RTopic_Command",
  "position_topic": "/R2UTopic_Pos",
  "status_topic": "/R2UTopic_Text"
}
```

Returns a mock task, `bridge_contract`, and video URL placeholders.

`GET /car-tasks/ue-bridge-status`

Returns deterministic mock CampusCar/UE bridge status. It does not probe a live ROS2 service.

## Lightweight AI Parser

`POST /ai/parse-query`

Body:

```json
{
  "query": "find red car near parking at night"
}
```

Returns rule-based filters that can be mapped into search parameters.

<p align="right"><a href="#english">Back to English top</a></p>
