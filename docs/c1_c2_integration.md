<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# C1 / C2 集成说明

本文记录 GKGuard C2 与 CampusVision C1 的职责边界、运行连接方式、已实现代理接口、字段映射和交接检查。当前 `v0.1.12` 已完成 C2 到 C1 的真实检索链路，并在桌面端加入 C1 自动探测、SSH 密码提示和软件内更新入口：C2 前端只访问 C2 后端，C2 后端再通过 `/c1/...` 代理访问 C1。

## 职责边界

- C1（`services/campusvision-c1/`）：视频上传、抽帧、人脸 embedding、人物库、以图搜人、轨迹输出和媒体帧访问。
- C2（`backend/`、`desktop/`）：检索工作台、结果与路线展示、事件研判、证据打包、审计日志、CampusCar/UE 占位合同和 C1 代理。

## C1 源码与运行数据

导入的 C1 源码来自团队服务器项目：

```text
/home/<c1-user>/projects/campusvision-c1
```

仓库只跟踪源码、文档、脚本、示例、依赖文件和 `.env.example`。以下运行数据不得提交：真实视频、查询图片、抽帧图片、SQLite 数据库、模型缓存、`.env`、Python 缓存。

## 运行连接

C2 适配器支持候选地址自动探测，读取顺序为 `C1_BASE_URL`、`C1_CANDIDATE_URLS`、安装版配置文件 `%APPDATA%\GKGuard\c1-connection.json`、内置服务器地址 `http://10.4.167.122:8000`，最后回退到默认本机隧道地址：

```text
C1_BASE_URL=http://127.0.0.1:18000
```

如果 C1 服务在远程服务器上并绑定服务器本机 `127.0.0.1:8000`，在 C2 机器上建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

这样 C2 可以访问 `http://127.0.0.1:18000`，同时不把 C1 直接暴露到网络。安装版默认会在直连和本机隧道都不可达时弹出提示，打开 PowerShell SSH 窗口；用户只在 PowerShell 中输入服务器密码，GKGuard 不保存密码。若部署环境不同，用 `C1_BASE_URL`、`C1_CANDIDATE_URLS` 或 `%APPDATA%\GKGuard\c1-connection.json` 覆盖。自动连接配置见 [c1_auto_connection.md](c1_auto_connection.md)。

C1 必须以 `FACE_ENGINE=insightface` 运行。若 `/api/v1/persons` 正常，但 `/health` 或以图搜人返回 500，通常是运行中的 uvicorn worker 仍继承了旧环境变量，需要检查 `/proc/<pid>/environ` 并重启实际监听端口的 worker。

## 已实现 C2 代理接口

| C2 接口 | C1 接口 | 作用 |
|---|---|---|
| `GET /c1/status` | `/openapi.json`、`/health` | 报告 C1 可达性和 InsightFace 健康状态。 |
| `GET /c1/persons` | `/api/v1/persons` | 读取 C1 人物库并改写媒体 URL。 |
| `GET /c1/videos` | `/api/v1/videos` | 读取 C1 视频列表。 |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | 接收 C2 `file` 字段，转发为 C1 `files` 字段，并归一化人物检索结果。 |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | 代理 C1 关键帧和人脸裁剪图。 |

## 字段映射

| C1 字段 | C2 用途 |
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

- 前端只调用 C2，不直接访问 C1。
- C2 将 C1 相对媒体 URL 改写为 `/c1/media/...`。
- C2 将 C1 `matches`、`trajectory` 和人物元数据转换为结果页与路线图可用的数据结构。
- 未上传图片、C1 不可用或 C1 请求失败时，UI 回退本地模拟数据。
- 结果页显示当前数据来源：`C1 CampusVision` 或 `本地模拟`。

## 交接检查

- C1 确认正式端口，以及服务绑定 `127.0.0.1` 还是 `0.0.0.0`。
- C1 `/health` 返回 HTTP 200，且 `face_engine=insightface`。
- C1 完成完整流程：创建摄像头、上传视频、索引视频、重建或更新人物库、以图搜人。
- C2 验证 `/c1/status`、`/c1/persons`、`/c1/search/person-by-image` 和 `/c1/media/...`。
- C1 提供安全的演示视频与查询图片规范，真实媒体不进入仓库。
- 后续 C1 数据应补齐 `captured_at`、`camera_name`、`location`，否则 C2 只能展示摄像头 ID 和视频内时间。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# C1 / C2 Integration Notes

This document records the responsibility boundary, runtime connection, implemented proxy endpoints, field mapping, and handoff checklist between GKGuard C2 and CampusVision C1. As of `v0.1.12`, the real C2-to-C1 search path is implemented, and the desktop app adds C1 auto-probing, an SSH password prompt, and an in-app update entry: the C2 frontend talks only to the C2 backend, and the C2 backend accesses C1 through `/c1/...` proxy endpoints.

## Ownership

- C1 (`services/campusvision-c1/`): video upload, frame sampling, face embeddings, person indexing, image search, trajectory output, and media frame access.
- C2 (`backend/`, `desktop/`): search workbench, result and route UI, event investigation, evidence packaging, audit logs, CampusCar/UE placeholder contracts, and the C1 proxy.

## C1 Source And Runtime Data

The imported C1 source came from the team server project:

```text
/home/<c1-user>/projects/campusvision-c1
```

The repository should track only source code, documentation, scripts, examples, dependency files, and `.env.example`. Do not commit real videos, query images, extracted frames, SQLite databases, model caches, `.env`, or Python caches.

## Runtime Connection

The C2 adapter supports candidate URL auto-detection in this order: `C1_BASE_URL`, `C1_CANDIDATE_URLS`, packaged-app config file `%APPDATA%\GKGuard\c1-connection.json`, built-in server URL `http://10.4.167.122:8000`, and finally the default local tunnel URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

If C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, create an SSH tunnel on the C2 machine:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

C2 can then call `http://127.0.0.1:18000` without exposing C1 directly on the network. By default, the packaged app prompts to open a PowerShell SSH window if both direct C1 and the local tunnel are unavailable; the user enters the server password only in PowerShell, and GKGuard does not store it. Use `C1_BASE_URL`, `C1_CANDIDATE_URLS`, or `%APPDATA%\GKGuard\c1-connection.json` to override this for other deployments. See [c1_auto_connection.md](c1_auto_connection.md) for automatic connection setup.

C1 must run with `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, the active uvicorn worker may still have stale environment variables. Inspect `/proc/<pid>/environ` and restart the actual worker that owns the listening port.

## Implemented C2 Proxy Endpoints

| C2 endpoint | C1 endpoint | Purpose |
|---|---|---|
| `GET /c1/status` | `/openapi.json`, `/health` | Report C1 reachability and InsightFace health. |
| `GET /c1/persons` | `/api/v1/persons` | Read the C1 person index and rewrite media URLs. |
| `GET /c1/videos` | `/api/v1/videos` | Read C1 videos. |
| `POST /c1/search/person-by-image` | `/api/v1/search/person-by-image` | Accept C2 field `file`, forward it as C1 field `files`, and normalize person-search results. |
| `GET /c1/media/{kind}/{face_id}` | `/api/v1/media/{kind}/{face_id}` | Proxy C1 frame and face-crop images. |

## Field Mapping

| C1 field | C2 usage |
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

- The frontend calls C2 only and never calls C1 directly.
- C2 rewrites C1 relative media URLs to `/c1/media/...`.
- C2 converts C1 `matches`, `trajectory`, and person metadata into the result and route view models.
- If no image is uploaded, C1 is unavailable, or the C1 request fails, the UI falls back to local mock data.
- The result screen shows the active data source: `C1 CampusVision` or `本地模拟`.

## Handoff Checklist

- C1 confirms the official port and whether the service binds to `127.0.0.1` or `0.0.0.0`.
- C1 `/health` returns HTTP 200 with `face_engine=insightface`.
- C1 completes the full flow: create camera, upload video, index video, rebuild or update person index, and search person by image.
- C2 verifies `/c1/status`, `/c1/persons`, `/c1/search/person-by-image`, and `/c1/media/...`.
- C1 provides a safe demo video and query-image policy; real media must not enter this repository.
- Future C1 data should include meaningful `captured_at`, `camera_name`, and `location`; otherwise C2 can only display camera IDs and in-video time.

<p align="right"><a href="#english">Back to English top</a></p>
