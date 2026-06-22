<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# API 规范

本文中的 GKGuard C2 指桌面工作台和本地 FastAPI 代理层；CampusVision C1 指独立的视频检索服务。GKGuard C2 前端只访问 GKGuard C2 API；所有真实 CampusVision C1 检索都通过 GKGuard C2 的 `/c1/...` 代理完成。

GKGuard C2 本地开发常用地址：

```text
http://127.0.0.1:8002
```

CampusVision C1 适配器默认本机隧道地址：

```text
C1_BASE_URL=http://127.0.0.1:18000
```

安装版 `v0.1.37` 默认只内置本机隧道候选地址 `http://127.0.0.1:18000`；校园网直连地址必须通过 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或 `%APPDATA%\GKGuard\c1-connection.json` 显式配置。GKGuard C2 会自动探测候选 CampusVision C1 服务；若未通过隧道连接，桌面端会在软件内连接窗口展示服务器账号、隧道目标、四步连接进度、失败重试和密码安全说明。主进程会在发送服务器密码前自动比对受信 SSH 主机密钥；服务器地址或主机密钥变化时必须通过 `sshTunnel.hostFingerprint` 或 `C1_SSH_HOST_FINGERPRINT` 显式更新受信主机信息。受信主机信息缺失或不匹配时，GKGuard C2 会阻断连接而不会弹出人工确认继续连接入口。真实检索遇到 CampusVision C1 502/503/504 时，适配器会尝试下一个显式候选地址。本版继续保留查询图人脸检测与选中人脸检索能力：CampusVision C1 会对查询图做 EXIF 转正、RGB 标准化、透明通道处理、贴边/大脸补边和小图放大重试，同时限制查询图上传不超过 16 MiB、解码后不超过 16MP 且单边不超过 8192 像素；超出解码限制时返回 413 并清理临时上传。上传图只有一张有效候选人脸时自动检索，多张有效候选人脸时必须选择目标人脸，上传区提供显式放大选择按钮，点击上传区本身仍可重新选择文件，低置信候选会标注但不直接隐藏，检测失败、无匹配、超时或真实检索失败时停留在上传页而不展示模拟命中；多人选择弹窗默认按可见容器内最大无滚动尺寸完整适配原图，`适应` 会回到该尺寸；结果页人物照片优先使用用户点击的目标框生成查询人脸裁切图，并按 CampusVision C1 返回的 `imageWidth` / `imageHeight` 将像素 bbox 映射到浏览器实际图片尺寸，裁切时会横向和纵向扩边，空间允许时调整为方形裁切，靠近图像边缘时向内平移以保留完整人脸，最终图片固定在人物照片方框的 8px 安全边距内并用 `object-fit: contain` 充分利用可见空间，缺失时才回退 CampusVision C1 返回的人脸缩略图；桌面端记录列表保持在左侧并继续优先使用 CampusVision C1 人脸缩略图，结果关键帧和预览弹窗会按实际图片内容区域框出目标人脸，并把相似度显示在框外，避免遮挡人脸、落在左上角或受黑边偏移。结果页切换左侧记录时会保留当前关键帧，预加载并解码目标记录关键帧，加载期间显示轻量提示；失败预加载可重试，快速切回当前记录时旧加载任务不会覆盖当前详情。Electron 桌面端会在加载页面前清理 renderer cache，并通过 `asset=v0.1.37-ui` 页面参数避免安装更新后继续显示旧页面。其余响应式布局、关键帧预览、路线联动、统一状态提示、应用内更新和旧后台资源复用保护继续保留。

安全边界：GKGuard C2 只会选择通过 `C1_ALLOWED_HOSTS` 允许列表、OpenAPI 身份检查和 `/health` 检查的 CampusVision C1 候选地址；如果 CampusVision C1 绑定到 `0.0.0.0`、`::` 或显式设置 `CAMPUSVISION_REQUIRE_API_KEY=true`，CampusVision C1 要求 `CAMPUSVISION_API_KEY` 或 `C1_API_KEY`，GKGuard C2 按相同优先级读取密钥并通过 `X-CampusVision-API-Key` 转发。CampusVision C1 会保护相机元数据、视频列表与索引、人物库、检索结果、媒体帧、人脸裁剪图和记录接口；人物库 HTML 预览会在服务端内联人脸图，不依赖浏览器直接请求受保护媒体 URL。视频索引失败时只回滚本次尝试新增的人脸记录和帧文件，保留该视频已有成功索引。旧版模拟图片搜索限制单个文件不超过 2 MiB，并在缺失或超出 `Content-Length` 时提前拒绝请求。案件包导出和审计日志读取属于本地敏感接口，分别需要 `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN` / `X-GKGuard-Export-Token` 和 `GKGUARD_AUDIT_TOKEN` / `X-GKGuard-Audit-Token`。

GKGuard C2 前端只访问 GKGuard C2 API。真实 CampusVision C1 检索通过 GKGuard C2 的 `/c1/...` 代理完成；旧版模拟 API 继续保留用于离线演示和非 CampusVision C1 流程。

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
- `candidates[].identityOk`：候选地址是否通过 CampusVision C1 OpenAPI 身份检查；未通过的候选不会被选中，也不会接收检索请求。
- `reachable`：当前 `baseUrl` 是否能读取 CampusVision C1 OpenAPI。
- `healthOk`：当前 `baseUrl` 的 CampusVision C1 `/health` 是否成功。
- `health`：CampusVision C1 health 响应内容。
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

## CampusVision C1 查询图人脸检测

`POST /c1/query-faces`

Multipart 表单字段：

- `file`：GKGuard C2 前端上传的一张查询图片。

GKGuard C2 会转发到 CampusVision C1 的 `POST /api/v1/search/query-faces`，返回查询图内的人脸检测结果。该接口只用于检索前的目标选择，不创建检索记录。

关键字段：

- `source`：`c1`。
- `engine`：CampusVision C1 使用的人脸引擎，通常为 `insightface`。
- `faceCount`：查询图内检测到的人脸数量。
- `queryFaces[]`：查询图人脸列表。
- `queryFaces[].index`：前端后续传给 `/c1/search/person-by-image` 的目标人脸序号。
- `queryFaces[].score`：人脸检测置信度，不等同于人物匹配相似度。
- `queryFaces[].bbox`：查询图人脸框，包含像素坐标 `x1`、`y1`、`x2`、`y2`、`width`、`height`，以及前端可用的 `leftPct`、`topPct`、`widthPct`、`heightPct`。
- `diagnostics`：CampusVision C1 查询图预处理和检测重试诊断信息，包括原图尺寸、使用过的检测变体和每次尝试检测到的人脸数；仅用于排障，不应展示给普通用户。

前端行为：

- `faceCount=0`：提示重新上传清晰正脸照片，不进入结果页。
- `faceCount=1`：自动选择唯一人脸并直接检索；如果该候选低于 `0.65` 但不低于 `0.45`，前端会提示低置信但仍允许检索。
- `faceCount>1`：在上传原图上显示可选人脸框和检测置信度，并自动打开放大选择弹窗。检测置信度不等同于人物相似度；低于 `0.65` 但不低于 `0.45` 的候选以低置信样式显示并仍可选择，低于 `0.45` 的候选不作为可选目标。

## CampusVision C1 以图搜人

`POST /c1/search/person-by-image`

Multipart 表单字段：

- `file`：GKGuard C2 前端上传的一张查询图片。

Query 参数：

- `top_k`：默认 `5`，范围 `1..20`。
- `min_score`：可选，相似度阈值，范围 `0..1`。
- `max_gap_sec`：默认 `3.0`。
- `query_face_index`：可选，指定查询图中被用户选择的人脸序号；多人查询图必须使用该参数才能保证只检索目标人脸。

GKGuard C2 会把 `file` 转发成 CampusVision C1 所需的 `files` 字段，并返回归一化视图模型：

- `source`：`c1`。
- `searchId`：CampusVision C1 search ID。
- `engine`：通常为 `insightface`。
- `warning` / `ambiguous`：CampusVision C1 低置信或歧义提示。
- `queryFaces[]`：本次查询图检测到的人脸列表。
- `selectedQueryFace`：本次实际用于检索的查询图目标人脸；只有单人自动选择或用户手动选择后才有值。
- `person`：当前 UI 选中的候选人物。
- `records[]`：结果页记录；`faceUrl` 用于记录缩略图，`frameUrl` 用于详情关键帧。
- `records[].faceBox`：命中关键帧中的目标人脸框，GKGuard C2 前端用它在详情关键帧和预览弹窗上标注目标人脸，并显示 `records[].similarity`。适配器兼容像素坐标、归一化坐标、百分比字段和常见 bbox 字段别名。
- `routePoints[]`：路线图轨迹点。
- `appearanceEvents[]`：CampusVision C1 连续出现事件。
- `raw`：原始 CampusVision C1 响应，保留用于调试和后续映射。

如果 CampusVision C1 服务不可用，GKGuard C2 返回结构化错误；当前桌面 UI 会先触发 CampusVision C1 连接窗口并重试一次。未上传图片时仍可进入本地模拟流程；已上传图片时，查询图人脸检测失败、真实检索失败、`records[]` 为空或请求超时都会停留在上传页并提示重试，不展示模拟命中结果，也不保持“检索中”状态。前端对 `/c1/query-faces` 使用约 15 秒超时，对 `/c1/search/person-by-image` 使用约 25 秒超时，并用约 30 秒整体 watchdog 防止旧请求卡住界面。

## CampusVision C1 媒体代理

`GET /c1/media/{kind}/{face_id}`

路径参数：

- `kind`：`frame` 或 `face`。
- `face_id`：CampusVision C1 face record ID。

返回 CampusVision C1 图片字节，通常为 `image/jpeg`。

GKGuard C2 会对成功读取的 CampusVision C1 媒体字节使用进程内短期缓存，缓存键包含实际响应的 CampusVision C1 base URL、API key、候选地址配置和连接代次，默认缓存 300 秒、最多 64 项，总上限 16 MiB、单项上限 2 MiB，可通过 `C1_MEDIA_CACHE_TTL_SEC`、`C1_MEDIA_CACHE_MAX_ITEMS`、`C1_MEDIA_CACHE_MAX_BYTES` 和 `C1_MEDIA_CACHE_MAX_ITEM_BYTES` 调整。未过期媒体缓存会先于实时 CampusVision C1 状态探测返回，用于降低服务短暂不可达时的记录切换失败率；但 `GET /c1/status` 或桌面端 SSH 隧道重新确认会推进连接代次并清理旧媒体缓存，避免同一本地隧道重连后复用上一实例媒体。常规代理请求还会复用短期 CampusVision C1 健康状态探测结果，默认 15 秒，可通过 `C1_STATUS_CACHE_TTL_SEC` 调整；`GET /c1/status` 仍执行实时探测，探测失败或身份校验失败会清理对应地址的旧健康缓存。

## 人员搜索（模拟）

`GET /search/persons`

Query 参数：

- `keyword`
- `name`
- `student_id`
- `phone`
- `email`
- `identity_type`

返回本地演示人员记录。

## 人员画像（模拟）

`GET /search/persons/{person_id}/profile`

返回人员基础信息、关联车辆、快照、门禁记录和告警。

## 车辆搜索（模拟）

`GET /search/vehicles`

Query 参数：

- `keyword`
- `plate_number`
- `color`
- `brand`
- `vehicle_type`
- `owner_person_id`

返回本地演示车辆记录。

## 快照记录（模拟）

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

## 图片搜索（旧版模拟）

`POST /search/image`

Multipart 表单字段：

- `file`：查询图片。

Query 参数：

- `top_k`：默认 `5`。
- `min_similarity`：默认 `0.72`。

返回本地 Top-K 模拟图片检索结果。真实 CampusVision C1 人脸检索请使用 `/c1/search/person-by-image`。

限制：

- `Content-Length` 必须存在且不超过文件上限加固定 multipart 开销。
- 单个图片文件最多 `2 MiB`。
- 超限返回 HTTP 413。

## 时间线（模拟）

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

安全要求：

- 服务端必须配置 `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN`。
- 请求必须携带 `X-GKGuard-Export-Token`。
- 未配置 token 返回 HTTP 503；token 缺失或错误返回 HTTP 401。

## 审计日志

`GET /audit/logs`

Query 参数：

- `limit`：默认 `20`，最大 `100`。

返回敏感演示操作产生的审计日志。

安全要求：

- 服务端必须配置 `GKGUARD_AUDIT_TOKEN`。
- 请求必须携带 `X-GKGuard-Audit-Token`。
- token 缺失或错误返回 HTTP 403。
- 审计日志按单条字段长度、总行数和总字节数做压缩保留，避免日志文件无限增长。

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

返回 CampusCar/UE 桥接的确定性模拟状态，不探测真实 ROS2 服务。

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

# API Specification

Here, GKGuard C2 means the desktop workbench plus local FastAPI proxy layer, and CampusVision C1 means the standalone video-search service. The GKGuard C2 frontend calls GKGuard C2 APIs only; all real CampusVision C1 search goes through GKGuard C2 `/c1/...` proxy endpoints.

Common local GKGuard C2 development URL:

```text
http://127.0.0.1:8002
```

Default local CampusVision C1 tunnel URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

The packaged `v0.1.37` app includes only the local tunnel candidate `http://127.0.0.1:18000` by default; campus-network direct URLs must be configured explicitly through `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or `%APPDATA%\GKGuard\c1-connection.json`. GKGuard C2 probes candidate CampusVision C1 URLs automatically; if the tunnel is not connected, the desktop app prompts for the server password inside the app and shows connection progress. Before sending the password, the main process automatically compares the trusted SSH host key. If the server address or host key changes, update trusted host information through `sshTunnel.hostFingerprint` or `C1_SSH_HOST_FINGERPRINT` explicitly. Connections with missing or mismatched trusted host information are blocked instead of allowing manual approval. When real search hits CampusVision C1 502/503/504, the adapter tries the next explicitly configured candidate URL. This version keeps the query-face detection and selected-face search behavior: CampusVision C1 applies EXIF orientation normalization, RGB conversion, alpha compositing, padding retries for tight or large faces, and small-image upscale retries, while limiting query-image uploads to 16 MiB, decoded images to 16MP, and each side to 8192 pixels; decoded over-limit images return 413 and clean up temporary uploads. Uploads with one effective candidate face auto-search; uploads with multiple effective candidates require selecting the target face, the upload area provides an explicit enlarged-selection button, and clicking the upload area itself still opens the file picker; low-confidence candidates are labeled instead of being hidden outright; detection failures, no-match results, timeouts, or real-search failures stay on the upload screen instead of showing mock hits. The multi-face selection modal defaults to the largest no-scroll full-image fit inside the visible frame, and `适应` returns to that fit. The result portrait prefers a query-face crop generated from the clicked target box and maps CampusVision C1 pixel bboxes through `imageWidth` / `imageHeight` to the browser image dimensions before cropping; the crop is padded horizontally and vertically, made square when the source image has enough room, shifted inward near image edges to preserve the full face, fixed inside the portrait frame with an 8px safe margin, and rendered with `object-fit: contain` so the available frame space is used consistently. It falls back to the CampusVision C1 face thumbnail only when needed. The desktop record list stays on the left side and keeps preferring CampusVision C1 face thumbnails, and result keyframes plus the preview dialog position the target overlay against the rendered image content with the similarity label outside the box so it does not cover the face or drift into the top-left corner or letterbox area. When switching records from the left list, the result page keeps the current keyframe visible, preloads and decodes the target record keyframe, and shows a lightweight loading hint during the transition; failed preloads can be retried, and stale load tasks cannot overwrite the current detail after users switch back. Electron clears the renderer cache before loading the page and appends `asset=v0.1.37-ui` so installed updates do not reuse stale HTML/CSS/JS. The responsive layout, keyframe preview, route selection sync, unified status feedback, in-app updates, and stale-backend asset protection remain in place.

Security boundary: GKGuard C2 selects only CampusVision C1 candidates that pass the `C1_ALLOWED_HOSTS` allowlist, OpenAPI identity check, and `/health` check. If CampusVision C1 binds to `0.0.0.0`, `::`, or explicitly sets `CAMPUSVISION_REQUIRE_API_KEY=true`, CampusVision C1 requires `CAMPUSVISION_API_KEY` or `C1_API_KEY`; GKGuard C2 reads the key with the same precedence and forwards it through `X-CampusVision-API-Key`. CampusVision C1 protects camera metadata, video listing and indexing, the person index, search results, media frames, face crops, and record endpoints. The person-gallery HTML preview inlines face images server-side instead of relying on browser requests to protected media URLs. Failed video indexing rolls back only records and frame files created by the current attempt while preserving existing successful indexes for the same video. Legacy mock image search limits one uploaded file to 2 MiB and rejects missing or over-limit `Content-Length` before endpoint handling. Case-package export and audit-log readback are sensitive local endpoints: they require `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN` / `X-GKGuard-Export-Token` and `GKGUARD_AUDIT_TOKEN` / `X-GKGuard-Audit-Token`, respectively.

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
- `candidates[].identityOk`: whether the candidate passed the CampusVision C1 OpenAPI identity check; candidates that fail it are not selected and do not receive search requests.
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

## CampusVision C1 Query-Face Detection

`POST /c1/query-faces`

Multipart form field:

- `file`: one query image uploaded by the GKGuard C2 frontend.

GKGuard C2 forwards the image to CampusVision C1 `POST /api/v1/search/query-faces` and returns the detected faces in the query image. This endpoint is used only for target selection before search; it does not create a search record.

Important fields:

- `source`: `c1`.
- `engine`: CampusVision C1 face engine, usually `insightface`.
- `faceCount`: number of faces detected in the query image.
- `queryFaces[]`: detected query faces.
- `queryFaces[].index`: face index later passed to `/c1/search/person-by-image`.
- `queryFaces[].score`: face-detection confidence, not person-match similarity.
- `queryFaces[].bbox`: face box in the query image, including pixel fields `x1`, `y1`, `x2`, `y2`, `width`, `height`, plus frontend-friendly `leftPct`, `topPct`, `widthPct`, and `heightPct`.
- `diagnostics`: CampusVision C1 query-image preprocessing and detection retry diagnostics, including original image size, attempted variants, and detected face counts per attempt. This is for troubleshooting and should not be shown to normal users.

Frontend behavior:

- `faceCount=0`: show a warning and ask for a clearer face image; do not enter results.
- `faceCount=1`: auto-select the only face and search directly. If that candidate is below `0.65` but at least `0.45`, the UI warns that it is low-confidence while still allowing the search.
- `faceCount>1`: overlay selectable face boxes and detection confidence on the original upload, then open an enlarged selection modal. Detection confidence is not person-match similarity; candidates below `0.65` but at least `0.45` stay visible with a low-confidence style and remain selectable, while candidates below `0.45` are not exposed as targets.

## CampusVision C1 Person Search By Image

`POST /c1/search/person-by-image`

Multipart form field:

- `file`: one query image uploaded by the GKGuard C2 frontend.

Query parameters:

- `top_k`: default `5`, range `1..20`.
- `min_score`: optional similarity threshold, range `0..1`.
- `max_gap_sec`: default `3.0`.
- `query_face_index`: optional selected face index from the query image; multi-face query images should pass this value so only the intended target face is searched.

GKGuard C2 forwards `file` as CampusVision C1's required `files` field and returns a normalized view model:

- `source`: `c1`.
- `searchId`: CampusVision C1 search ID.
- `engine`: usually `insightface`.
- `warning` / `ambiguous`: CampusVision C1 low-confidence or ambiguity information.
- `queryFaces[]`: faces detected in the query image.
- `selectedQueryFace`: query face actually used for this search; present after single-face auto-selection or manual multi-face selection.
- `person`: selected candidate person for the current UI.
- `records[]`: result-screen records; `faceUrl` powers record thumbnails, and `frameUrl` powers the detail keyframe.
- `records[].faceBox`: target-face box in the matched keyframe; GKGuard C2 uses it to overlay the target face and `records[].similarity` on detail keyframes and preview dialogs. The adapter accepts pixel coordinates, normalized coordinates, percentage fields, and common bbox field aliases.
- `routePoints[]`: route points for the route screen.
- `appearanceEvents[]`: CampusVision C1 appearance events.
- `raw`: original CampusVision C1 response for debugging and future mapping.

If the CampusVision C1 service is unavailable, GKGuard C2 returns a structured error. The current desktop UI first opens the CampusVision C1 connection prompt and retries once. Local mock data is still available when no image has been uploaded; after an image upload, query-face detection failures, real-search failures, empty `records[]` results, or request timeouts keep the UI on the upload screen with a retry/error message instead of falling back to mock results or staying in a loading state. The frontend uses about 15 seconds for `/c1/query-faces`, about 25 seconds for `/c1/search/person-by-image`, and an about 30-second overall watchdog to prevent stale requests from locking the UI.

## CampusVision C1 Media Proxy

`GET /c1/media/{kind}/{face_id}`

Path parameters:

- `kind`: `frame` or `face`.
- `face_id`: CampusVision C1 face record ID.

Returns CampusVision C1 image bytes, usually as `image/jpeg`.

GKGuard C2 uses a short-lived in-process cache for successfully fetched CampusVision C1 media bytes. The cache key includes the responding CampusVision C1 base URL, API key, candidate-URL configuration, and connection generation. It defaults to 300 seconds, 64 items, a 16 MiB total limit, and a 2 MiB per-item limit; tune these with `C1_MEDIA_CACHE_TTL_SEC`, `C1_MEDIA_CACHE_MAX_ITEMS`, `C1_MEDIA_CACHE_MAX_BYTES`, and `C1_MEDIA_CACHE_MAX_ITEM_BYTES`. Valid media cache entries are returned before a fresh CampusVision C1 status probe, reducing record-switch failures when the service is briefly unavailable; however, `GET /c1/status` or a desktop SSH-tunnel reconfirmation advances the connection generation and clears old media cache entries, preventing media from a previous instance from being reused after the same local tunnel reconnects. Normal proxy requests also reuse short-lived healthy CampusVision C1 status probes, defaulting to 15 seconds through `C1_STATUS_CACHE_TTL_SEC`; `GET /c1/status` still performs a fresh probe and clears stale healthy cache entries when a probe or identity check fails.

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

Limits:

- `Content-Length` must be present and fit within the file limit plus fixed multipart overhead.
- One image file may be at most `2 MiB`.
- Over-limit requests return HTTP 413.

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

Security requirements:

- The server must set `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN`.
- The request must include `X-GKGuard-Export-Token`.
- Missing server-side token returns HTTP 503; missing or invalid request token returns HTTP 401.

## Audit Logs

`GET /audit/logs`

Query parameters:

- `limit`: default `20`, max `100`.

Returns audit logs generated by sensitive demo actions.

Security requirements:

- The server must set `GKGUARD_AUDIT_TOKEN`.
- The request must include `X-GKGuard-Audit-Token`.
- Missing or invalid tokens return HTTP 403.
- Audit logs are compacted by per-field size, total line count, and total byte count so the log file cannot grow unbounded.

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
