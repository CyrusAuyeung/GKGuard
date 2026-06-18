<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 / GKGuard C2 集成说明

本文记录 CampusVision C1 服务与 GKGuard C2 工作台的职责边界、运行连接方式、已实现代理接口、字段映射和联调检查。CampusVision C1 是视频检索服务，负责视频索引、人脸向量、人物库、以图搜人、关键帧和轨迹输出；GKGuard C2 是桌面工作台和本地代理层，负责 UI、CampusVision C1 连接、结果归一化、路线展示、本地模拟回退和 CampusCar/UE 占位接口规范。当前 `v0.1.27` 已包含 GKGuard C2 到 CampusVision C1 的真实检索链路、查询图人脸检测预处理与重试、多人放大弹窗选人、低置信候选可见标注、选中人脸检索、目标人脸裁切展示、无匹配和超时状态恢复、结果关键帧目标框和框外相似度标注：GKGuard C2 前端只访问 GKGuard C2 后端，GKGuard C2 后端再通过 `/c1/...` 代理访问 CampusVision C1。

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

GKGuard C2 适配器支持 CampusVision C1 候选地址自动探测；安装版默认候选地址优先本机隧道 `http://127.0.0.1:18000`，再尝试内置服务器地址 `http://10.4.167.122:8000`。完整读取顺序为 `C1_BASE_URL`、`C1_CANDIDATE_URLS`、安装版配置文件 `%APPDATA%\GKGuard\c1-connection.json`、默认本机隧道地址、内置服务器地址。

```text
C1_BASE_URL=http://127.0.0.1:18000
```

如果 CampusVision C1 服务在远程服务器上并绑定服务器本机 `127.0.0.1:8000`，安装版会在软件内提示输入服务器密码并建立 SSH 隧道。开发或排障时也可以在运行 GKGuard C2 的机器上手动建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

这样 GKGuard C2 可以访问 `http://127.0.0.1:18000`，同时不把 CampusVision C1 直接暴露到网络。安装版默认会优先要求通过隧道连接；若直连可达但真实检索返回 503，前端会打开软件内 SSH 密码窗口并在连接后重试。密码只用于本次 SSH 连接，GKGuard 不保存密码。若部署环境不同，用 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或 `%APPDATA%\GKGuard\c1-connection.json` 覆盖。自动连接配置见 [c1_auto_connection.md](c1_auto_connection.md)。

CampusVision C1 必须以 `FACE_ENGINE=insightface` 运行。若 `/api/v1/persons` 正常，但 `/health` 或以图搜人返回 500，通常是运行中的 uvicorn worker 仍继承了旧环境变量，需要检查 `/proc/<pid>/environ` 并重启实际监听端口的 worker。

CampusVision C1 服务依赖建议保持 `numpy<2`、`opencv-python<4.13`。当前 InsightFace / ONNXRuntime 环境可以在 NumPy 1.26.x 下通过检查；若 pip 将 NumPy 升级到 2.x，可能导致运行时依赖不一致，应按 `services/campusvision-c1/requirements.txt` 重新安装后重启服务。

## 已实现 GKGuard C2 代理接口

| GKGuard C2 接口 | CampusVision C1 接口 | 作用 |
|---|---|---|
| `GET /c1/status` | `/openapi.json`、`/health` | 报告 CampusVision C1 可达性和 InsightFace 健康状态。 |
| `GET /c1/persons` | `/api/v1/persons` | 读取 CampusVision C1 人物库并改写媒体 URL。 |
| `GET /c1/videos` | `/api/v1/videos` | 读取 CampusVision C1 视频列表。 |
| `POST /c1/query-faces` | `/api/v1/search/query-faces` | 检测查询图中的人脸，返回每张人脸的 bbox 和检测置信度，用于单人自动检索或多人目标选择。 |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | 接收 GKGuard C2 `file` 字段，转发为 CampusVision C1 `files` 字段，并归一化人物检索结果。 |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | 代理 CampusVision C1 关键帧和人脸裁剪图。 |

## 字段映射

| CampusVision C1 字段 | GKGuard C2 用途 |
|---|---|
| `persons[0]` | 当前 UI 选中的候选人物。 |
| `query_faces[]` | 查询图内检测到的人脸；GKGuard C2 映射为 `queryFaces[]`，用于上传页原图框选。 |
| `selected_query_face` | 实际用于检索的查询图人脸；GKGuard C2 映射为 `selectedQueryFace`。 |
| `matches[]` | 结果页关键帧记录。 |
| `trajectory[]` | 路线图轨迹点。 |
| `appearance_events[]` | 后续更丰富时间线的事件段。 |
| `frame_url` / `best_frame_url` | 改写为 `/c1/media/frame/...` 后用于详情关键帧。 |
| `face_url` / `face_crop_url` / `face_id` | 改写为 `/c1/media/face/...` 后用于记录列表缩略图。 |
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
- 上传图片后，前端先调用 `/c1/query-faces`；CampusVision C1 会对查询图做 EXIF 转正、RGB 标准化、透明通道处理、贴边/大脸补边和小图放大重试；检测到一张有效候选人脸时自动检索，多张有效候选人脸时在放大原图弹窗中选择目标人脸；低于 `0.65` 但不低于 `0.45` 的候选以低置信样式显示并仍可选择，低于 `0.45` 的候选不作为可选目标。
- 前端调用 `/c1/search/person-by-image` 时会在需要时附带 `query_face_index`，CampusVision C1 只用选中的查询图人脸 embedding 检索。
- GKGuard C2 将 CampusVision C1 相对媒体 URL 改写为 `/c1/media/...`。
- GKGuard C2 将 CampusVision C1 `query_faces`、`selected_query_face`、`matches`、`trajectory` 和人物元数据转换为上传页、结果页与路线图可用的数据结构。
- 若 CampusVision C1 返回命中帧 `bbox`，GKGuard C2 前端会在详情关键帧和预览弹窗上按渲染后的图片内容区域显示目标人脸框，并把匹配相似度显示在框外，避免遮挡人脸。
- 未上传图片时可以使用本地模拟数据演示流程；已上传图片后，查询图人脸检测、CampusVision C1 真实检索失败、空 `records[]` 结果或请求超时都会停留在上传页提示重试，不展示本地模拟命中结果，也不保持“检索中”状态。
- 结果页显示当前数据来源：`CampusVision C1` 或 `本地模拟`。

## 联调检查

- CampusVision C1 确认正式端口，以及服务绑定 `127.0.0.1` 还是 `0.0.0.0`。
- CampusVision C1 `/health` 返回 HTTP 200，且 `face_engine=insightface`。
- CampusVision C1 完成完整流程：创建摄像头、上传视频、索引视频、重建或更新人物库、以图搜人。
- GKGuard C2 验证 `/c1/status`、`/c1/persons`、`/c1/query-faces`、`/c1/search/person-by-image` 和 `/c1/media/...`。
- 多人查询图联调时，应确认 `/c1/query-faces` 返回多张有效查询人脸，GKGuard C2 上传页能打开放大弹窗并选中目标，低置信候选可见但样式区分，后续 `/c1/search/person-by-image` 带上正确的 `query_face_index`。
- 关键帧联调时，应确认 CampusVision C1 返回命中帧 `bbox`，GKGuard C2 详情区和关键帧预览弹窗能显示目标框和相似度。
- 若多人图只返回一张查询人脸，应优先检查 CampusVision C1 是否使用 `INSIGHTFACE_DET_SIZE=1280` 或更高检测尺寸，并确认服务已重启。
- CampusVision C1 提供安全的演示视频与查询图片规范，真实媒体不进入仓库。
- 后续 CampusVision C1 数据应补齐 `captured_at`、`camera_name`、`location`，否则 GKGuard C2 只能展示摄像头 ID 和视频内时间。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 / GKGuard C2 Integration Notes

This document records the responsibility boundary, runtime connection, implemented proxy endpoints, field mapping, and integration checklist between the CampusVision C1 service and the GKGuard C2 workbench. CampusVision C1 is the video-search service for video indexing, face embeddings, person indexing, image search, keyframes, and trajectory output. GKGuard C2 is the desktop workbench and local proxy layer for UI, CampusVision C1 connectivity, result normalization, route display, mock fallback, and CampusCar/UE placeholder interface specifications. As of `v0.1.27`, the real GKGuard C2-to-CampusVision C1 search path is included, with query-face preprocessing and retry, enlarged multi-face selection, visible low-confidence candidate labels, selected-face search, selected query-face crop display, no-match and timeout recovery, and target-face overlays with outside-box similarity labels on result keyframes: the GKGuard C2 frontend talks only to the GKGuard C2 backend, and the GKGuard C2 backend accesses CampusVision C1 through `/c1/...` proxy endpoints.

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

The GKGuard C2 adapter supports CampusVision C1 candidate URL auto-detection in this order: `C1_BASE_URL`, `C1_CANDIDATE_URLS`, packaged-app config file `%APPDATA%\GKGuard\c1-connection.json`, default local tunnel URL `http://127.0.0.1:18000`, and finally built-in server URL `http://10.4.167.122:8000`:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

If CampusVision C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, the packaged app prompts for the server password inside the app and creates the SSH tunnel. For development or troubleshooting, you can also create a tunnel manually on the machine running GKGuard C2:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

GKGuard C2 can then call `http://127.0.0.1:18000` without exposing CampusVision C1 directly on the network. By default, the packaged app prefers the tunnel; if direct CampusVision C1 is reachable but real search returns 503, the frontend opens the embedded SSH password prompt and retries after connection. The password is used only for the current SSH session, and GKGuard does not store it. Use `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or `%APPDATA%\GKGuard\c1-connection.json` to override this for other deployments. See [c1_auto_connection.md](c1_auto_connection.md) for automatic connection setup.

CampusVision C1 must run with `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, the active uvicorn worker may still have stale environment variables. Inspect `/proc/<pid>/environ` and restart the actual worker that owns the listening port.

Keep the CampusVision C1 service dependencies on `numpy<2` and `opencv-python<4.13`. The current InsightFace / ONNXRuntime environment checks pass on NumPy 1.26.x; if pip upgrades NumPy to 2.x, reinstall from `services/campusvision-c1/requirements.txt` and restart the service.

## Implemented GKGuard C2 Proxy Endpoints

| GKGuard C2 endpoint | CampusVision C1 endpoint | Purpose |
|---|---|---|
| `GET /c1/status` | `/openapi.json`, `/health` | Report CampusVision C1 reachability and InsightFace health. |
| `GET /c1/persons` | `/api/v1/persons` | Read the CampusVision C1 person index and rewrite media URLs. |
| `GET /c1/videos` | `/api/v1/videos` | Read CampusVision C1 videos. |
| `POST /c1/query-faces` | `/api/v1/search/query-faces` | Detect faces in the query image and return each face bbox plus detection confidence for single-face auto-search or multi-face target selection. |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | Accept GKGuard C2 field `file`, forward it as CampusVision C1 field `files`, and normalize person-search results. |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | Proxy CampusVision C1 frame and face-crop images. |

## Field Mapping

| CampusVision C1 field | GKGuard C2 usage |
|---|---|
| `persons[0]` | Candidate person selected by the current UI. |
| `query_faces[]` | Faces detected in the query image; GKGuard C2 maps this to `queryFaces[]` for original-image target selection. |
| `selected_query_face` | Query face actually used for search; GKGuard C2 maps this to `selectedQueryFace`. |
| `matches[]` | Keyframe records in the result screen. |
| `trajectory[]` | Route points in the route screen. |
| `appearance_events[]` | Event segments for a richer future timeline. |
| `frame_url` / `best_frame_url` | Rewritten to `/c1/media/frame/...` for the detail keyframe. |
| `face_url` / `face_crop_url` / `face_id` | Rewritten to `/c1/media/face/...` for record-list thumbnails. |
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
- After upload, the frontend calls `/c1/query-faces`; CampusVision C1 applies EXIF orientation normalization, RGB conversion, alpha compositing, padding retries for tight or large faces, and small-image upscale retries. One effective candidate face is auto-selected and searched, while multiple effective candidates require selecting a target in an enlarged original-image modal. Candidates below `0.65` but at least `0.45` stay visible with a low-confidence style and remain selectable, while candidates below `0.45` are not exposed as targets.
- When needed, the frontend calls `/c1/search/person-by-image` with `query_face_index`, so CampusVision C1 searches with only the selected query-face embedding.
- GKGuard C2 rewrites CampusVision C1 relative media URLs to `/c1/media/...`.
- GKGuard C2 converts CampusVision C1 `query_faces`, `selected_query_face`, `matches`, `trajectory`, and person metadata into upload, result, and route view models.
- If CampusVision C1 returns a matched-frame `bbox`, the GKGuard C2 frontend overlays the target face on the detail keyframe and preview dialog using the rendered image content area, and keeps the similarity label outside the box so it does not cover the face.
- Without an uploaded image, the UI can use local mock data for the demo flow; after an image is uploaded, query-face detection failures, real CampusVision C1 search failures, empty `records[]` results, or request timeouts keep the UI on the upload screen with a retry/error message instead of showing mock hits or staying in a loading state.

## Integration Checklist

- CampusVision C1 confirms the official port and whether the service binds to `127.0.0.1` or `0.0.0.0`.
- CampusVision C1 `/health` returns HTTP 200 with `face_engine=insightface`.
- CampusVision C1 completes the full flow: create camera, upload video, index video, rebuild or update person index, and search person by image.
- GKGuard C2 verifies `/c1/status`, `/c1/persons`, `/c1/query-faces`, `/c1/search/person-by-image`, and `/c1/media/...`.
- For multi-face query-image testing, confirm `/c1/query-faces` returns multiple valid faces, the GKGuard C2 upload screen opens the enlarged selector and can select the intended target, low-confidence candidates remain visible with distinct styling, and the following `/c1/search/person-by-image` request includes the correct `query_face_index`.
- If a multi-face image returns only one query face, first check that CampusVision C1 is running with `INSIGHTFACE_DET_SIZE=1280` or a larger detection size, then restart the service.
- For keyframe testing, confirm CampusVision C1 returns matched-frame `bbox` data and GKGuard C2 shows the target box plus similarity in the detail view and preview dialog.
- CampusVision C1 provides a safe demo video and query-image policy; real media must not enter this repository.
- Future CampusVision C1 data should include meaningful `captured_at`, `camera_name`, and `location`; otherwise GKGuard C2 can only display camera IDs and in-video time.

<p align="right"><a href="#english">Back to English top</a></p>
