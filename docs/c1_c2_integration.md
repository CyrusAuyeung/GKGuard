<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 / GKGuard C2 集成说明

本文记录 CampusVision C1 服务与 GKGuard C2 工作台的职责边界、运行连接方式、已实现代理接口、字段映射和联调检查。CampusVision C1 是视频检索服务，负责视频索引、人脸向量、人物库、以图搜人、人物事件、事件观测、外观属性分析、关键帧和轨迹输出；GKGuard C2 是桌面工作台和本地代理层，负责 UI、CampusVision C1 连接、结果归一化、路线展示、本地模拟回退和 CampusCar/UE 占位接口规范。当前 `v0.2.0` 已包含 GKGuard C2 到 CampusVision C1 的真实以图搜人链路、人物特征事件检索链路、查询图人脸检测预处理与重试、多人显式放大选人按钮、事件/观测媒体代理、结果页属性摘要、结果关键帧目标框和框外相似度标注、结果记录切换关键帧预加载与无黑屏切换，以及 CampusVision C1 候选地址允许列表、服务身份检查、受信 SSH 主机密钥自动比对、外部暴露时 API key、受保护媒体/视频列表/人物库/事件接口、按 CampusVision C1 响应地址、API key、候选配置和连接代次隔离的 GKGuard C2 进程内媒体缓存、媒体缓存容量上限、失败状态探测清理旧健康缓存、查询图解码超限 413 和索引失败清理当前尝试新增的人脸记录、人物观测与帧文件并保留既有成功记录。GKGuard C2 前端只访问 GKGuard C2 后端，GKGuard C2 后端再通过 `/c1/...` 代理访问 CampusVision C1。

本版还要求媒体请求发起前和返回前重新校验连接代次；如果 CampusVision C1 候选地址在健康探测、GET 发出前或 GET 返回前变化，GKGuard C2 会重新解析候选或返回可重试错误。中等宽度结果页会固定人物照片列的响应式范围，避免人物照片遮挡数据来源和命中记录信息。

## 职责边界

- CampusVision C1（`services/campusvision-c1/`）：视频上传、抽帧、人脸 embedding、人物库、以图搜人、轨迹输出和媒体帧访问。
- GKGuard C2（`backend/`、`desktop/`）：检索工作台、结果与路线展示、事件研判、证据打包、审计日志、CampusCar/UE 占位接口规范和 CampusVision C1 代理。

## CampusVision C1 源码与运行数据

导入的 CampusVision C1 源码来自团队服务器项目：

```text
/home/<c1-user>/projects/campusvision-c1
```

仓库只跟踪源码、文档、脚本、示例、依赖文件和 `.env.example`。以下运行数据不得提交：真实视频、查询图片、抽帧图片、SQLite 数据库、模型缓存、`.env`、Python 缓存。

## 运行连接

GKGuard C2 适配器支持 CampusVision C1 候选地址自动探测；安装版默认只内置本机隧道 `http://127.0.0.1:18000`。校园网直连地址或其他远端地址必须通过 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或安装版配置文件 `%APPDATA%\GKGuard\c1-connection.json` 显式提供，并且主机名必须通过 `C1_ALLOWED_HOSTS` 允许列表。完整读取顺序为 `C1_BASE_URL`、`C1_CANDIDATE_URLS`、安装版配置文件和默认本机隧道地址。

```text
C1_BASE_URL=http://127.0.0.1:18000
```

如果 CampusVision C1 服务在远程服务器上并绑定服务器本机 `127.0.0.1:8000`，安装版会在软件内提示输入服务器密码并建立 SSH 隧道。开发或排障时也可以在运行 GKGuard C2 的机器上手动建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

这样 GKGuard C2 可以访问 `http://127.0.0.1:18000`，同时不把 CampusVision C1 直接暴露到网络。安装版默认会优先要求通过隧道连接；若直连可达但真实检索返回 503，前端会打开软件内 SSH 密码窗口并在连接后重试。密码只用于本次 SSH 连接，GKGuard 不保存密码。若部署环境不同，用 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或 `%APPDATA%\GKGuard\c1-connection.json` 覆盖，并同步设置 `C1_ALLOWED_HOSTS`。自动连接配置见 [c1_auto_connection.md](c1_auto_connection.md)。

CampusVision C1 必须以 `FACE_ENGINE=insightface` 运行。若服务绑定 `0.0.0.0`、`::` 或显式设置 `CAMPUSVISION_REQUIRE_API_KEY=true`，必须配置 `CAMPUSVISION_API_KEY` 或 `C1_API_KEY`，GKGuard C2 会按相同优先级读取密钥并通过 `X-CampusVision-API-Key` 转发。若 `/api/v1/persons` 正常，但 `/health` 或以图搜人返回 500，通常是运行中的 uvicorn worker 仍继承了旧环境变量，需要检查 `/proc/<pid>/environ` 并重启实际监听端口的 worker。

CampusVision C1 服务依赖建议保持 `numpy<2`、`opencv-python<4.13`。当前 InsightFace / ONNXRuntime 环境可以在 NumPy 1.26.x 下通过检查；若 pip 将 NumPy 升级到 2.x，可能导致运行时依赖不一致，应按 `services/campusvision-c1/requirements.txt` 重新安装后重启服务。

## 已实现 GKGuard C2 代理接口

| GKGuard C2 接口 | CampusVision C1 接口 | 作用 |
|---|---|---|
| `GET /c1/status` | `/openapi.json`、`/health` | 报告 CampusVision C1 可达性和 InsightFace 健康状态。 |
| `GET /c1/persons` | `/api/v1/persons` | 读取 CampusVision C1 人物库并改写媒体 URL。 |
| `GET /c1/videos` | `/api/v1/videos` | 读取 CampusVision C1 视频列表。 |
| `POST /c1/query-faces` | `/api/v1/search/query-faces` | 检测查询图中的人脸，返回每张人脸的 bbox 和检测置信度，用于单人自动检索或多人目标选择。 |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | 接收 GKGuard C2 `file` 字段，转发为 CampusVision C1 `files` 字段，并归一化人物检索结果。 |
| `GET /c1/events` | `/api/v1/events` | 读取 CampusVision C1 人物事件列表。 |
| `GET /c1/persons/{person_id}/events` | `/api/v1/persons/{person_id}/events` | 读取指定人物关联事件。 |
| `GET /c1/events/{event_id}/observations` | `/api/v1/events/{event_id}/observations` | 读取事件观测帧、人体框、人脸框和媒体 URL。 |
| `POST /c1/query/face-image` | `/api/v1/query/face-image` | 返回查询图候选人物、候选事件和查询图人脸信息。 |
| `POST /c1/query/person-attributes` | `/api/v1/query/person-attributes` | 按上装颜色、眼镜状态、外观倾向、摄像头和时间范围检索人物事件。 |
| `GET /c1/media/{media_path}` | `/api/v1/media/...` | 代理 CampusVision C1 关键帧、人脸裁剪图、人体裁剪图和事件代表图，并对成功响应使用按响应地址、API key、候选配置和连接代次隔离的 GKGuard C2 进程内短期缓存。 |

## 字段映射

| CampusVision C1 字段 | GKGuard C2 用途 |
|---|---|
| `persons[0]` | 当前 UI 选中的候选人物。 |
| `query_faces[]` | 查询图内检测到的人脸；GKGuard C2 映射为 `queryFaces[]`，用于上传页原图框选。 |
| `selected_query_face` | 实际用于检索的查询图人脸；GKGuard C2 映射为 `selectedQueryFace`。 |
| `matches[]` | 结果页关键帧记录。 |
| `trajectory[]` | 路线图轨迹点。 |
| `appearance_events[]` | 以图搜人结果中的连续出现事件段。 |
| `events[]` | 人物特征检索或人物事件列表，GKGuard C2 映射为结果页 `records[]` 和路线页 `routePoints[]`。 |
| `observations[]` | 事件观测帧，包含事件下的帧、人体框、人脸框、时间和摄像头信息。 |
| `frame_url` / `best_frame_url` | 改写为 `/c1/media/frame/...` 后用于详情关键帧。 |
| `face_url` / `face_crop_url` / `face_id` | 改写为 `/c1/media/face/...` 后用于记录列表缩略图。 |
| `body_crop_url` / `body_image_url` | 改写为 `/c1/media/observation/body/...` 或 `/c1/media/event/body/...` 后用于特征检索结果缩略图。 |
| `attributes` / `condition_scores` / `failed_conditions` | 人物特征检索命中条件、分项分数和未满足条件，GKGuard C2 在结果页相关信息区域展示。 |
| `bbox` | 查询图或命中帧中的人脸框；查询图 bbox 用于选择目标，命中帧 bbox 映射为 `records[].faceBox` 并用于关键帧目标框。GKGuard C2 兼容像素坐标、归一化坐标、百分比字段和常见 bbox 字段别名，并按实际图片内容区域计算显示位置。 |
| `diagnostics` | CampusVision C1 查询图预处理与检测重试诊断信息，只用于排障，不进入普通展示。 |
| `representative_face_crop_url` | 改写为 `/c1/media/face/...` 后作为目标头像。 |
| `camera_id`、`camera_name` | 摄像头标识与展示名。 |
| `location`、`lat`、`lng` | 位置和地图信息。 |
| `score`、`best_score` | 相似度展示。 |
| `captured_at`、`time_display` | 时间展示。 |

## 适配器行为

```text
C1_BASE_URL -> health check -> image search -> normalize result -> GKGuard C2 view model
```

- 前端只调用 GKGuard C2 后端，不直接访问 CampusVision C1。
- GKGuard C2 只会向通过允许列表、OpenAPI 身份检查和 `/health` 检查的 CampusVision C1 候选地址发送查询图、视频或检索请求。
- 上传图片后，前端先调用 `/c1/query-faces`；CampusVision C1 会对查询图做 EXIF 转正、RGB 标准化、透明通道处理、贴边/大脸补边和小图放大重试；检测到一张有效候选人脸时自动检索，多张有效候选人脸时在放大原图弹窗中选择目标人脸；低于 `0.65` 但不低于 `0.45` 的候选以低置信样式显示并仍可选择，低于 `0.45` 的候选不作为可选目标。
- CampusVision C1 会限制查询图数量、查询图上传体积、视频上传体积、解码后图片尺寸和视频索引帧数；超限请求返回结构化错误并清理已经保存的临时上传。
- 前端调用 `/c1/search/person-by-image` 时会在需要时附带 `query_face_index`，CampusVision C1 只用选中的查询图人脸 embedding 检索。
- 人物特征检索不需要上传图片；GKGuard C2 前端将筛选条件提交到 `/c1/query/person-attributes`，后端转发给 CampusVision C1 并把事件结果归一化为结果页记录。低分或部分匹配结果保留分数和未命中条件供人工复核，不表述为确定身份。
- GKGuard C2 可以通过 `/c1/events`、`/c1/persons/{person_id}/events` 和 `/c1/events/{event_id}/observations` 读取 CampusVision C1 事件与观测明细，用于后续事件详情、轨迹和证据展示。
- GKGuard C2 将 CampusVision C1 相对媒体 URL 改写为 `/c1/media/...`。
- GKGuard C2 对成功读取的 CampusVision C1 媒体响应使用进程内短期缓存，缓存键包含实际响应的 CampusVision C1 base URL、API key、候选地址配置和连接代次，并设置条目数、总字节和单项字节上限；有效媒体缓存可先于实时状态探测返回，但 `GET /c1/status` 或桌面端 SSH 隧道重新确认会推进连接代次并清理旧媒体缓存。媒体请求若已解析出候选地址，但在健康探测、发起媒体 GET 前或媒体 GET 返回前连接代次变化，会重新解析候选或返回可重试错误；不会把旧 CampusVision C1 实例的媒体或错误直接返回给前端、写入新缓存或回写选中地址。同一次媒体请求内从失效候选回退到可用候选时，会保留成功候选并写入对应代次缓存。GKGuard C2 也会复用短期 CampusVision C1 健康状态探测结果；实时状态探测失败或身份校验失败时会清理对应地址的旧健康缓存。
- GKGuard C2 将 CampusVision C1 `query_faces`、`selected_query_face`、`matches`、`events`、`observations`、`trajectory`、人物元数据和属性分数转换为上传页、特征检索页、结果页与路线图可用的数据结构。
- 若 CampusVision C1 返回命中帧 `bbox`，GKGuard C2 前端会在详情关键帧和预览弹窗上按渲染后的图片内容区域显示目标人脸框，并把匹配相似度显示在框外，避免遮挡人脸。
- 结果页切换左侧记录时，GKGuard C2 前端保留当前关键帧，预加载并解码目标记录关键帧，加载完成后再替换详情图；加载期间显示轻量提示，失败预加载可重试，快速切回当前记录时旧加载任务不会覆盖当前详情。
- 未上传图片时可以使用本地模拟数据演示流程；已上传图片后，查询图人脸检测、CampusVision C1 真实检索失败、空 `records[]` 结果或请求超时都会停留在上传页提示重试，不展示本地模拟命中结果，也不保持“检索中”状态。
- 结果页显示当前数据来源：`CampusVision C1` 或 `本地模拟`。

## 联调检查

- CampusVision C1 确认正式端口，以及服务绑定 `127.0.0.1` 还是 `0.0.0.0`。
- 若 CampusVision C1 绑定到外部地址，确认 `CAMPUSVISION_API_KEY` 或 `C1_API_KEY` 已配置，GKGuard C2 侧同步配置相同密钥，并确认未把密钥写入仓库。
- GKGuard C2 确认 `C1_ALLOWED_HOSTS` 覆盖所有显式候选地址，且 `/c1/status` 中只有通过服务身份检查的候选会被选为 `selectedBaseUrl`。
- CampusVision C1 `/health` 返回 HTTP 200，且 `face_engine=insightface`。
- CampusVision C1 完成完整流程：创建摄像头、上传视频、索引视频、重建或更新人物库、以图搜人。
- GKGuard C2 验证 `/c1/status`、`/c1/persons`、`/c1/query-faces`、`/c1/search/person-by-image` 和 `/c1/media/...`。
- GKGuard C2 验证 `/c1/events`、`/c1/persons/{person_id}/events`、`/c1/events/{event_id}/observations`、`/c1/query/face-image` 和 `/c1/query/person-attributes`。
- 多人查询图联调时，应确认 `/c1/query-faces` 返回多张有效查询人脸，GKGuard C2 上传页能打开放大弹窗并选中目标，低置信候选可见但样式区分，后续 `/c1/search/person-by-image` 带上正确的 `query_face_index`。
- 关键帧联调时，应确认 CampusVision C1 返回命中帧 `bbox`，GKGuard C2 详情区和关键帧预览弹窗能显示目标框和相似度。
- 人物特征检索联调时，应确认 CampusVision C1 返回事件、属性分数、未命中条件和可访问媒体 URL，GKGuard C2 结果页能展示事件记录、属性摘要、关键帧、缩略图和路线点。
- 若多人图只返回一张查询人脸，应优先检查 CampusVision C1 是否使用 `INSIGHTFACE_DET_SIZE=1280` 或更高检测尺寸，并确认服务已重启。
- CampusVision C1 提供安全的演示视频与查询图片规范，真实媒体不进入仓库。
- 后续 CampusVision C1 数据应补齐 `captured_at`、`camera_name`、`location`，否则 GKGuard C2 只能展示摄像头 ID 和视频内时间。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 / GKGuard C2 Integration Notes

This document records the responsibility boundary, runtime connection, implemented proxy endpoints, field mapping, and integration checklist between the CampusVision C1 service and the GKGuard C2 workbench. CampusVision C1 is the video-search service for video indexing, face embeddings, person indexing, image search, person events, event observations, appearance-attribute analysis, keyframes, and trajectory output. GKGuard C2 is the desktop workbench and local proxy layer for UI, CampusVision C1 connectivity, result normalization, route display, mock fallback, and CampusCar/UE placeholder interface specifications. As of `v0.2.0`, the real GKGuard C2-to-CampusVision C1 integration includes image-based person search, person-attribute event search, query-face preprocessing and retry, explicit enlarged face selection, event/observation media proxying, result-page attribute summaries, target-face overlays with outside-box similarity labels, preloaded no-black-screen keyframe switching, CampusVision C1 candidate URL allowlisting, service-identity checks, automatic trusted SSH host-key comparison, API-key protection when CampusVision C1 is exposed, protected media/video-list/person-index/event endpoints, GKGuard C2 in-process media caching scoped by responding CampusVision C1 base URL, API key, candidate configuration, and connection generation, media-cache byte limits, stale healthy-cache eviction after failed status probes, 413 handling for decoded over-limit query images, and failed-index cleanup for current-attempt face records, person observations, and frame files while preserving existing successful records. The GKGuard C2 frontend talks only to the GKGuard C2 backend, and the GKGuard C2 backend accesses CampusVision C1 through `/c1/...` proxy endpoints.

This version also re-checks the connection generation before sending media requests and before returning media responses. If the CampusVision C1 candidate changes during healthy-candidate probing, before the GET is sent, or before the GET response is returned, GKGuard C2 re-resolves candidates or returns a retryable error. Medium-width result layouts constrain the target-portrait column so it cannot cover the source and hit-count summary.

## Ownership

- CampusVision C1 (`services/campusvision-c1/`): video upload, frame sampling, face embeddings, person indexing, image search, trajectory output, and media frame access.
- GKGuard C2 (`backend/`, `desktop/`): search workbench, result and route UI, event investigation, evidence packaging, audit logs, CampusCar/UE placeholder interface specifications, and the CampusVision C1 proxy.

## CampusVision C1 Source And Runtime Data

The imported CampusVision C1 source came from the team server project:

```text
/home/<c1-user>/projects/campusvision-c1
```

The repository should track only source code, documentation, scripts, examples, dependency files, and `.env.example`. Do not commit real videos, query images, extracted frames, SQLite databases, model caches, `.env`, or Python caches.

## Runtime Connection

The GKGuard C2 adapter supports CampusVision C1 candidate URL auto-detection. The packaged app includes only the local tunnel URL `http://127.0.0.1:18000` by default. Campus-network direct URLs or other remote URLs must be explicitly provided through `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or packaged-app config file `%APPDATA%\GKGuard\c1-connection.json`, and their hostnames must pass the `C1_ALLOWED_HOSTS` allowlist. The full read order is `C1_BASE_URL`, `C1_CANDIDATE_URLS`, packaged-app config file, and the default local tunnel URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

If CampusVision C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, the packaged app prompts for the server password inside the app and creates the SSH tunnel. For development or troubleshooting, you can also create a tunnel manually on the machine running GKGuard C2:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

GKGuard C2 can then call `http://127.0.0.1:18000` without exposing CampusVision C1 directly on the network. By default, the packaged app prefers the tunnel; if direct CampusVision C1 is reachable but real search returns 503, the frontend opens the embedded SSH password prompt and retries after connection. The password is used only for the current SSH session, and GKGuard does not store it. Use `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or `%APPDATA%\GKGuard\c1-connection.json` to override this for other deployments, and update `C1_ALLOWED_HOSTS` accordingly. See [c1_auto_connection.md](c1_auto_connection.md) for automatic connection setup.

CampusVision C1 must run with `FACE_ENGINE=insightface`. If the service binds to `0.0.0.0`, `::`, or explicitly sets `CAMPUSVISION_REQUIRE_API_KEY=true`, configure `CAMPUSVISION_API_KEY` or `C1_API_KEY`; GKGuard C2 reads the key with the same precedence and forwards it through `X-CampusVision-API-Key`. If `/api/v1/persons` works but `/health` or image search returns 500, the active uvicorn worker may still have stale environment variables. Inspect `/proc/<pid>/environ` and restart the actual worker that owns the listening port.

Keep the CampusVision C1 service dependencies on `numpy<2` and `opencv-python<4.13`. The current InsightFace / ONNXRuntime environment checks pass on NumPy 1.26.x; if pip upgrades NumPy to 2.x, reinstall from `services/campusvision-c1/requirements.txt` and restart the service.

## Implemented GKGuard C2 Proxy Endpoints

| GKGuard C2 endpoint | CampusVision C1 endpoint | Purpose |
|---|---|---|
| `GET /c1/status` | `/openapi.json`, `/health` | Report CampusVision C1 reachability and InsightFace health. |
| `GET /c1/persons` | `/api/v1/persons` | Read the CampusVision C1 person index and rewrite media URLs. |
| `GET /c1/videos` | `/api/v1/videos` | Read CampusVision C1 videos. |
| `POST /c1/query-faces` | `/api/v1/search/query-faces` | Detect faces in the query image and return each face bbox plus detection confidence for single-face auto-search or multi-face target selection. |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | Accept GKGuard C2 field `file`, forward it as CampusVision C1 field `files`, and normalize person-search results. |
| `GET /c1/events` | `/api/v1/events` | Read CampusVision C1 person events. |
| `GET /c1/persons/{person_id}/events` | `/api/v1/persons/{person_id}/events` | Read events linked to one person. |
| `GET /c1/events/{event_id}/observations` | `/api/v1/events/{event_id}/observations` | Read event observation frames, body boxes, face boxes, and media URLs. |
| `POST /c1/query/face-image` | `/api/v1/query/face-image` | Return query-image candidate persons, candidate events, and query-face information. |
| `POST /c1/query/person-attributes` | `/api/v1/query/person-attributes` | Search person events by upper-body color, glasses status, appearance presentation, camera, and time range. |
| `GET /c1/media/{media_path}` | `/api/v1/media/...` | Proxy CampusVision C1 keyframes, face crops, body crops, and event representative images, with a short-lived GKGuard C2 in-process cache for successful responses scoped by responding address, API key, candidate configuration, and connection generation. |

## Field Mapping

| CampusVision C1 field | GKGuard C2 usage |
|---|---|
| `persons[0]` | Candidate person selected by the current UI. |
| `query_faces[]` | Faces detected in the query image; GKGuard C2 maps this to `queryFaces[]` for original-image target selection. |
| `selected_query_face` | Query face actually used for search; GKGuard C2 maps this to `selectedQueryFace`. |
| `matches[]` | Keyframe records in the result screen. |
| `trajectory[]` | Route points in the route screen. |
| `appearance_events[]` | Continuous appearance event segments returned by image search. |
| `events[]` | Person-attribute query or person-event list entries; GKGuard C2 maps them to result-screen `records[]` and route-screen `routePoints[]`. |
| `observations[]` | Event observation frames with frame media, body boxes, face boxes, time, and camera data. |
| `frame_url` / `best_frame_url` | Rewritten to `/c1/media/frame/...` for the detail keyframe. |
| `face_url` / `face_crop_url` / `face_id` | Rewritten to `/c1/media/face/...` for record-list thumbnails. |
| `body_crop_url` / `body_image_url` | Rewritten to `/c1/media/observation/body/...` or `/c1/media/event/body/...` for attribute-search thumbnails. |
| `attributes` / `condition_scores` / `failed_conditions` | Person-attribute query matched conditions, per-condition scores, and unmet conditions; GKGuard C2 shows them in result details. |
| `bbox` | Face box in a query image or matched frame; query-image bbox powers target selection, and matched-frame bbox becomes `records[].faceBox` for keyframe overlays. GKGuard C2 accepts pixel, normalized, percentage, and common alias fields, then positions the overlay against the rendered image content. |
| `diagnostics` | CampusVision C1 query-image preprocessing and detection retry diagnostics for troubleshooting only; not part of normal user-facing display. |
| `representative_face_crop_url` | Rewritten to `/c1/media/face/...` for the target portrait. |
| `camera_id`, `camera_name` | Camera identity and display name. |
| `location`, `lat`, `lng` | Location and map data. |
| `score`, `best_score` | Similarity display. |
| `captured_at`, `time_display` | Time display. |

## Adapter Behavior

```text
C1_BASE_URL -> health check -> image search -> normalize result -> GKGuard C2 view model
```

- The frontend calls only the GKGuard C2 backend and never calls CampusVision C1 directly.
- GKGuard C2 sends query images, videos, and search requests only to CampusVision C1 candidates that pass the host allowlist, OpenAPI identity check, and `/health` check.
- After upload, the frontend calls `/c1/query-faces`; CampusVision C1 applies EXIF orientation normalization, RGB conversion, alpha compositing, padding retries for tight or large faces, and small-image upscale retries. One effective candidate face is auto-selected and searched, while multiple effective candidates require selecting a target in an enlarged original-image modal. Candidates below `0.65` but at least `0.45` stay visible with a low-confidence style and remain selectable, while candidates below `0.45` are not exposed as targets.
- CampusVision C1 limits query-image count, query-image upload size, video upload size, decoded image dimensions, and video indexing frames; over-limit requests return structured errors and clean up saved temporary uploads.
- When needed, the frontend calls `/c1/search/person-by-image` with `query_face_index`, so CampusVision C1 searches with only the selected query-face embedding.
- Person-attribute search does not require an uploaded image. The GKGuard C2 frontend submits filters to `/c1/query/person-attributes`; the backend forwards them to CampusVision C1 and normalizes returned events into result-screen records. Low-score or partial-match results retain scores and unmet conditions for human review, and are not described as confirmed identity.
- GKGuard C2 can read CampusVision C1 event and observation detail through `/c1/events`, `/c1/persons/{person_id}/events`, and `/c1/events/{event_id}/observations` for future event detail, trajectory, and evidence presentation.
- GKGuard C2 rewrites CampusVision C1 relative media URLs to `/c1/media/...`.
- GKGuard C2 uses a short-lived in-process cache for successful CampusVision C1 media responses, with the responding CampusVision C1 base URL, API key, candidate-URL configuration, and connection generation included in the cache key, plus item-count, total-byte, and per-item byte limits. Valid media cache entries can be returned before a fresh status probe, but `GET /c1/status` or a desktop SSH-tunnel reconfirmation advances the connection generation and clears old media cache entries. If a media request has resolved a candidate address but the connection generation changes during healthy-candidate probing, before the media GET is sent, or before the media GET response is returned, GKGuard C2 re-resolves the candidate or returns a retryable error; it does not return media or media errors from the old CampusVision C1 instance to the UI, write them into the new cache, or overwrite the selected address. When the same media request falls back from a failed candidate to a healthy candidate, GKGuard C2 preserves the successful candidate and writes the media into that resulting generation's cache. GKGuard C2 also reuses short-lived healthy CampusVision C1 status probes; failed fresh probes or identity checks clear stale healthy cache entries for the affected address.
- GKGuard C2 converts CampusVision C1 `query_faces`, `selected_query_face`, `matches`, `events`, `observations`, `trajectory`, person metadata, and attribute scores into upload, attribute-search, result, and route view models.
- If CampusVision C1 returns a matched-frame `bbox`, the GKGuard C2 frontend overlays the target face on the detail keyframe and preview dialog using the rendered image content area, and keeps the similarity label outside the box so it does not cover the face.
- When switching records from the left list, the GKGuard C2 frontend keeps the current keyframe visible, preloads and decodes the target record keyframe, and replaces the detail image only after loading finishes. A lightweight loading hint is shown during the transition, failed preloads can be retried, and stale load tasks cannot overwrite the current detail after users switch back.
- Without an uploaded image, the UI can use local mock data for the demo flow; after an image is uploaded, query-face detection failures, real CampusVision C1 search failures, empty `records[]` results, or request timeouts keep the UI on the upload screen with a retry/error message instead of showing mock hits or staying in a loading state.

## Integration Checklist

- CampusVision C1 confirms the official port and whether the service binds to `127.0.0.1` or `0.0.0.0`.
- If CampusVision C1 binds to an external address, confirm `CAMPUSVISION_API_KEY` or `C1_API_KEY` is configured, GKGuard C2 uses the same key, and no key is written to the repository.
- GKGuard C2 confirms that `C1_ALLOWED_HOSTS` covers all explicit candidate URLs, and `/c1/status` selects only candidates that pass service identity checks as `selectedBaseUrl`.
- CampusVision C1 `/health` returns HTTP 200 with `face_engine=insightface`.
- CampusVision C1 completes the full flow: create camera, upload video, index video, rebuild or update person index, and search person by image.
- GKGuard C2 verifies `/c1/status`, `/c1/persons`, `/c1/query-faces`, `/c1/search/person-by-image`, and `/c1/media/...`.
- GKGuard C2 verifies `/c1/events`, `/c1/persons/{person_id}/events`, `/c1/events/{event_id}/observations`, `/c1/query/face-image`, and `/c1/query/person-attributes`.
- For multi-face query-image testing, confirm `/c1/query-faces` returns multiple valid faces, the GKGuard C2 upload screen opens the enlarged selector and can select the intended target, low-confidence candidates remain visible with distinct styling, and the following `/c1/search/person-by-image` request includes the correct `query_face_index`.
- If a multi-face image returns only one query face, first check that CampusVision C1 is running with `INSIGHTFACE_DET_SIZE=1280` or a larger detection size, then restart the service.
- For keyframe testing, confirm CampusVision C1 returns matched-frame `bbox` data and GKGuard C2 shows the target box plus similarity in the detail view and preview dialog.
- For person-attribute search testing, confirm CampusVision C1 returns events, attribute scores, unmet conditions, and accessible media URLs, and that GKGuard C2 shows event records, attribute summaries, keyframes, thumbnails, and route points.
- CampusVision C1 provides a safe demo video and query-image policy; real media must not enter this repository.
- Future CampusVision C1 data should include meaningful `captured_at`, `camera_name`, and `location`; otherwise GKGuard C2 can only display camera IDs and in-video time.

<p align="right"><a href="#english">Back to English top</a></p>
