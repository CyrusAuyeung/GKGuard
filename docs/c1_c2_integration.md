<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 / GKGuard C2 集成说明

本文记录 CampusVision C1 服务与 GKGuard C2 工作台的职责边界、运行连接方式、已实现代理接口、字段映射和联调检查。CampusVision C1 是视频检索服务，负责视频索引、人脸向量、人物库、以图搜人、关键帧和轨迹输出；GKGuard C2 是桌面工作台和本地代理层，负责 UI、CampusVision C1 连接、结果归一化、路线展示、mock fallback 和 CampusCar/UE 占位合同。当前 `v0.1.17` 已包含 GKGuard C2 到 CampusVision C1 的真实检索链路，并在桌面端加入优先 SSH 隧道、CampusVision C1 503 后连接重试、内嵌 SSH 密码窗口、连接进度提示、细节修正后的线性功能图标、品牌图标资产、应用内更新安装和重新上传入口：GKGuard C2 前端只访问 GKGuard C2 后端，GKGuard C2 后端再通过 `/c1/...` 代理访问 CampusVision C1。

## 职责边界

- CampusVision C1（`services/campusvision-c1/`）：视频上传、抽帧、人脸 embedding、人物库、以图搜人、轨迹输出和媒体帧访问。
- GKGuard C2（`backend/`、`desktop/`）：检索工作台、结果与路线展示、事件研判、证据打包、审计日志、CampusCar/UE 占位合同和 CampusVision C1 代理。

## CampusVision C1 源码与运行数据

导入的 CampusVision C1 源码来自团队服务器项目：

```text
/home/<c1-user>/projects/campusvision-c1
```

仓库只跟踪源码、文档、脚本、示例、依赖文件和 `.env.example`。以下运行数据不得提交：真实视频、查询图片、抽帧图片、SQLite 数据库、模型缓存、`.env`、Python 缓存。

## 运行连接

GKGuard C2 适配器支持 CampusVision C1 候选地址自动探测；安装版默认候选地址优先本机隧道 `http://127.0.0.1:18000`，再尝试内置服务器地址 `http://10.4.167.122:8000`。完整读取顺序为 `C1_BASE_URL`、`C1_CANDIDATE_URLS`、安装版配置文件 `%APPDATA%\GKGuard\c1-connection.json`、内置候选地址。

```text
C1_BASE_URL=http://127.0.0.1:18000
```

如果 CampusVision C1 服务在远程服务器上并绑定服务器本机 `127.0.0.1:8000`，安装版会在软件内提示输入服务器密码并建立 SSH 隧道。开发或排障时也可以在运行 GKGuard C2 的机器上手动建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

这样 GKGuard C2 可以访问 `http://127.0.0.1:18000`，同时不把 CampusVision C1 直接暴露到网络。安装版默认会优先要求通过隧道连接；若直连可达但真实检索返回 503，前端会打开软件内 SSH 密码窗口并在连接后重试。密码只用于本次 SSH 连接，GKGuard 不保存密码。若部署环境不同，用 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或 `%APPDATA%\GKGuard\c1-connection.json` 覆盖。自动连接配置见 [c1_auto_connection.md](c1_auto_connection.md)。

CampusVision C1 必须以 `FACE_ENGINE=insightface` 运行。若 `/api/v1/persons` 正常，但 `/health` 或以图搜人返回 500，通常是运行中的 uvicorn worker 仍继承了旧环境变量，需要检查 `/proc/<pid>/environ` 并重启实际监听端口的 worker。

## 已实现 GKGuard C2 代理接口

| GKGuard C2 接口 | CampusVision C1 接口 | 作用 |
|---|---|---|
| `GET /c1/status` | `/openapi.json`、`/health` | 报告 CampusVision C1 可达性和 InsightFace 健康状态。 |
| `GET /c1/persons` | `/api/v1/persons` | 读取 CampusVision C1 人物库并改写媒体 URL。 |
| `GET /c1/videos` | `/api/v1/videos` | 读取 CampusVision C1 视频列表。 |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | 接收 GKGuard C2 `file` 字段，转发为 CampusVision C1 `files` 字段，并归一化人物检索结果。 |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | 代理 CampusVision C1 关键帧和人脸裁剪图。 |

## 字段映射

| CampusVision C1 字段 | GKGuard C2 用途 |
|---|---|
| `persons[0]` | 当前 UI 选中的候选人物。 |
| `matches[]` | 结果页关键帧记录。 |
| `trajectory[]` | 路线图轨迹点。 |
| `appearance_events[]` | 后续更丰富时间线的事件段。 |
| `frame_url` / `best_frame_url` | 改写为 `/c1/media/frame/...` 后用于记录列表缩略图和详情关键帧。 |
| `representative_face_crop_url` | 改写为 `/c1/media/face/...` 后作为目标头像。 |
| `camera_id`、`camera_name` | 摄像头标识与展示名。 |
| `location`、`lat`、`lng` | 位置和地图信息。 |
| `score`、`best_score` | 相似度展示。 |
| `captured_at`、`time_display` | 时间展示。 |

## 适配器行为

```text
C1_BASE_URL -> health check -> image search -> normalize result -> C2 view model
```

- 前端只调用 GKGuard C2 后端，不直接访问 CampusVision C1。
- GKGuard C2 将 CampusVision C1 相对媒体 URL 改写为 `/c1/media/...`。
- GKGuard C2 将 CampusVision C1 `matches`、`trajectory` 和人物元数据转换为结果页与路线图可用的数据结构。
- 未上传图片、CampusVision C1 不可用或 CampusVision C1 请求失败时，桌面 UI 会先触发软件内 CampusVision C1 连接窗口并重试；仍失败时才回退本地模拟数据。
- 结果页显示当前数据来源：`C1 CampusVision` 或 `本地模拟`。

## 联调检查

- CampusVision C1 确认正式端口，以及服务绑定 `127.0.0.1` 还是 `0.0.0.0`。
- CampusVision C1 `/health` 返回 HTTP 200，且 `face_engine=insightface`。
- CampusVision C1 完成完整流程：创建摄像头、上传视频、索引视频、重建或更新人物库、以图搜人。
- GKGuard C2 验证 `/c1/status`、`/c1/persons`、`/c1/search/person-by-image` 和 `/c1/media/...`。
- CampusVision C1 提供安全的演示视频与查询图片规范，真实媒体不进入仓库。
- 后续 CampusVision C1 数据应补齐 `captured_at`、`camera_name`、`location`，否则 GKGuard C2 只能展示摄像头 ID 和视频内时间。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 / GKGuard C2 Integration Notes

This document records the responsibility boundary, runtime connection, implemented proxy endpoints, field mapping, and integration checklist between the CampusVision C1 service and the GKGuard C2 workbench. CampusVision C1 is the video-search service for video indexing, face embeddings, person indexing, image search, keyframes, and trajectory output. GKGuard C2 is the desktop workbench and local proxy layer for UI, CampusVision C1 connectivity, result normalization, route display, mock fallback, and CampusCar/UE placeholder contracts. As of `v0.1.17`, the real GKGuard C2-to-CampusVision C1 search path is included, and the desktop app adds SSH-tunnel priority, connection retry after CampusVision C1 503, an embedded SSH password prompt, connection progress, refined linear UI icons, brand icon assets, in-app update installation, and a return-to-upload action: the GKGuard C2 frontend talks only to the GKGuard C2 backend, and the GKGuard C2 backend accesses CampusVision C1 through `/c1/...` proxy endpoints.

## Ownership

- CampusVision C1 (`services/campusvision-c1/`): video upload, frame sampling, face embeddings, person indexing, image search, trajectory output, and media frame access.
- GKGuard C2 (`backend/`, `desktop/`): search workbench, result and route UI, event investigation, evidence packaging, audit logs, CampusCar/UE placeholder contracts, and the CampusVision C1 proxy.

## CampusVision C1 Source And Runtime Data

The imported CampusVision C1 source came from the team server project:

```text
/home/<c1-user>/projects/campusvision-c1
```

The repository should track only source code, documentation, scripts, examples, dependency files, and `.env.example`. Do not commit real videos, query images, extracted frames, SQLite databases, model caches, `.env`, or Python caches.

## Runtime Connection

The GKGuard C2 adapter supports CampusVision C1 candidate URL auto-detection in this order: `C1_BASE_URL`, `C1_CANDIDATE_URLS`, packaged-app config file `%APPDATA%\GKGuard\c1-connection.json`, built-in server URL `http://10.4.167.122:8000`, and finally the default local tunnel URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

If CampusVision C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, the packaged app prompts for the server password inside the app and creates the SSH tunnel. For development or troubleshooting, you can also create a tunnel manually on the machine running GKGuard C2:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

GKGuard C2 can then call `http://127.0.0.1:18000` without exposing CampusVision C1 directly on the network. By default, the packaged app prefers the tunnel; if direct CampusVision C1 is reachable but real search returns 503, the frontend opens the embedded SSH password prompt and retries after connection. The password is used only for the current SSH session, and GKGuard does not store it. Use `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or `%APPDATA%\GKGuard\c1-connection.json` to override this for other deployments. See [c1_auto_connection.md](c1_auto_connection.md) for automatic connection setup.

CampusVision C1 must run with `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, the active uvicorn worker may still have stale environment variables. Inspect `/proc/<pid>/environ` and restart the actual worker that owns the listening port.

## Implemented GKGuard C2 Proxy Endpoints

| GKGuard C2 endpoint | CampusVision C1 endpoint | Purpose |
|---|---|---|
| `GET /c1/status` | `/openapi.json`, `/health` | Report CampusVision C1 reachability and InsightFace health. |
| `GET /c1/persons` | `/api/v1/persons` | Read the CampusVision C1 person index and rewrite media URLs. |
| `GET /c1/videos` | `/api/v1/videos` | Read CampusVision C1 videos. |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | Accept GKGuard C2 field `file`, forward it as CampusVision C1 field `files`, and normalize person-search results. |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | Proxy CampusVision C1 frame and face-crop images. |

## Field Mapping

| CampusVision C1 field | GKGuard C2 usage |
|---|---|
| `persons[0]` | Candidate person selected by the current UI. |
| `matches[]` | Keyframe records in the result screen. |
| `trajectory[]` | Route points in the route screen. |
| `appearance_events[]` | Event segments for a richer future timeline. |
| `frame_url` / `best_frame_url` | Rewritten to `/c1/media/frame/...` for record-list thumbnails and the detail keyframe. |
| `representative_face_crop_url` | Rewritten to `/c1/media/face/...` for the target portrait. |
| `camera_id`, `camera_name` | Camera identity and display name. |
| `location`, `lat`, `lng` | Location and map data. |
| `score`, `best_score` | Similarity display. |
| `captured_at`, `time_display` | Time display. |

## Adapter Behavior

```text
C1_BASE_URL -> health check -> image search -> normalize result -> C2 view model
```

- The frontend calls only the GKGuard C2 backend and never calls CampusVision C1 directly.
- GKGuard C2 rewrites CampusVision C1 relative media URLs to `/c1/media/...`.
- GKGuard C2 converts CampusVision C1 `matches`, `trajectory`, and person metadata into the result and route view models.
- If no image is uploaded, CampusVision C1 is unavailable, or the CampusVision C1 request fails, the UI first triggers the embedded CampusVision C1 connection prompt and retries; it falls back to local mock data only if CampusVision C1 remains unavailable.
- The result screen shows the active data source: `C1 CampusVision` or `本地模拟`.

## Integration Checklist

- CampusVision C1 confirms the official port and whether the service binds to `127.0.0.1` or `0.0.0.0`.
- CampusVision C1 `/health` returns HTTP 200 with `face_engine=insightface`.
- CampusVision C1 completes the full flow: create camera, upload video, index video, rebuild or update person index, and search person by image.
- GKGuard C2 verifies `/c1/status`, `/c1/persons`, `/c1/search/person-by-image`, and `/c1/media/...`.
- CampusVision C1 provides a safe demo video and query-image policy; real media must not enter this repository.
- Future CampusVision C1 data should include meaningful `captured_at`, `camera_name`, and `location`; otherwise GKGuard C2 can only display camera IDs and in-video time.

<p align="right"><a href="#english">Back to English top</a></p>
