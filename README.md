<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# GKGuard C2 AI 搜索演示

GKGuard 是校园安防 AI 检索项目中的 C2 演示端。当前 `v0.1.13` 状态下，仓库包含 C2 后端、三界面人脸检索前端、Electron 桌面壳、C1 自动连接/SSH 密码提示、软件内更新入口，以及作为独立模块导入的 C1 CampusVision 视频检索服务。

## 当前状态

- C2 后端位于 `backend/`，提供 FastAPI API、静态演示页、C1 代理、mock fallback、审计和 CampusCar/UE 占位接口。
- C2 前端位于 `backend/app/static/`，当前主流程为 `人脸检索`、`人脸检索结果`、`人物路线图` 三个界面；上传页和结果页会优先完整显示用户上传的目标照片，并在记录列表展示 C1 关键帧缩略图。
- Electron 桌面壳位于 `desktop/`，GitHub Actions 可构建 Windows 安装包；安装版打开后会优先建立 SSH 隧道并提示输入服务器密码，真实检索遇到 C1 503 时也会打开连接窗口并重试；桌面模式右上角提供 `检查更新` 入口，可直接下载最新安装包。
- C1 源码位于 `services/campusvision-c1/`，负责视频上传、抽帧、人脸 embedding、人物库、以图搜人和轨迹输出。
- C2 已实现 `/c1/...` 代理，可以通过 SSH 隧道连接服务器上的真实 C1 服务。
- 当 C1 不可用、未上传图片或接口报错时，C2 前端会先尝试桌面端 C1 连接/重试；仍不可用时才回退到本地模拟记录，方便离线演示。

## 项目结构

```text
backend/
  app/
    main.py
    routers/
    services/
    static/
  data/mock/
  tests/
  requirements.txt
desktop/
docs/
  api_contract.md
  c1_c2_integration.md
  c1_auto_connection.md
  campuscar_ue_integration.md
  data_dictionary.md
  demo_script.md
  releases/
services/
  campusvision-c1/
    app/
    docs/
    scripts/
    README.md
```

## 仓库治理与使用声明

- [LICENSE](LICENSE)：当前 source-available / 保留所有权利声明。
- [OPEN_SOURCE.md](OPEN_SOURCE.md)：开源与闭源边界、允许使用范围和第三方依赖说明。
- [PRIVACY.md](PRIVACY.md)：真实媒体、个人信息、C1 运行数据和凭据处理规则。
- [SECURITY.md](SECURITY.md)：安全问题报告方式和敏感信息处理要求。
- [CONTRIBUTING.md](CONTRIBUTING.md)：贡献流程、验证命令和文档规范。
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)：项目协作行为准则。
- [SUPPORT.md](SUPPORT.md)：问题反馈入口和支持边界。
- [GOVERNANCE.md](GOVERNANCE.md)：C1、C2、CampusCar/UE 和文档维护职责。

## C1 / C2 接入

当前 C2 已实现以下 C1 代理接口：

- `GET /c1/status`：检查 C1 OpenAPI 与 `/health`。
- `GET /c1/persons`：读取 C1 人物库，并把媒体 URL 改写为 C2 可访问路径。
- `GET /c1/videos`：读取 C1 视频列表。
- `POST /c1/search/person-by-image`：接收前端上传字段 `file`，转发给 C1 的 `files` 字段，并归一化为 C2 前端视图模型。
- `GET /c1/media/{frame|face}/{face_id}`：代理 C1 关键帧和人脸裁剪图。

本地开发默认使用：

```text
C1_BASE_URL=http://127.0.0.1:18000
```

安装版内置默认 C1 候选地址 `http://127.0.0.1:18000` 和 `http://10.4.167.122:8000`，并优先使用本机 SSH 隧道。打开应用后如果尚未通过隧道连接 C1，会提示是否打开 SSH 登录窗口；如果直连服务可达但真实检索返回 503，页面也会触发同一个连接窗口并重试一次。你只需要在 PowerShell 中输入服务器密码，GKGuard 不保存密码。

通常不需要额外配置。若服务器地址或账号变化，可用 `%APPDATA%\GKGuard\c1-connection.json` 覆盖默认值，示例见 [docs/examples/c1-connection.example.json](docs/examples/c1-connection.example.json)。

如果 C1 在远程服务器上并绑定到服务器本机 `127.0.0.1:8000`，先在 C2 机器上建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

C1 真实检索需要 `FACE_ENGINE=insightface`。如果 `/api/v1/persons` 正常但 `/health` 或以图搜人返回 500，优先检查运行中 uvicorn worker 的环境变量，并用当前 `.env` 重启 C1 服务。

更多字段映射和交接检查见 [docs/c1_c2_integration.md](docs/c1_c2_integration.md)。
自动连接、候选 C1 地址和 SSH 隧道配置见 [docs/c1_auto_connection.md](docs/c1_auto_connection.md)。

## CampusCar / UE 占位

当前 C2 只保留稳定的 CampusCar/UE 集成占位合同，不打包 UE 运行时，也不在桌面 app 内运行 ROS2 节点。

占位接口：

- `POST /car-tasks/mock-dispatch`：创建模拟现场复核任务，并返回 `bridge_contract`。
- `GET /car-tasks/ue-bridge-status`：返回 rosbridge、UE 测试 app 和预期 topic 的占位状态。

预期外部 topic：

- `/U2RTopic_Command`：C2 或适配器下发命令意图。
- `/R2UTopic_Pos`：车辆或 UE 位姿反馈。
- `/R2UTopic_Text`：文本或状态反馈。

更多说明见 [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md)。

## 本地运行 C2

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:C1_BASE_URL = "http://127.0.0.1:18000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

打开：

```text
http://127.0.0.1:8002/demo
http://127.0.0.1:8002/docs
```

未连接 C1 时，演示页仍可通过本地 mock fallback 运行。

## 运行桌面端

从 GitHub Release 下载的最新 Windows 安装包用于 C2 桌面端演示。安装后直接打开即可启动内置本地 C2 后端并进入 `/demo`，不需要另外安装 Python、Node.js 或手动启动 C2 服务。

桌面软件右上角提供 `检查更新` 入口：点击后会查询 GitHub 最新 Release；发现新版时再次点击即可直接下载最新 `GKGuard-Setup-*.exe`，下载完成后软件会提示打开所在文件夹。

本地开发或打包桌面端时建议使用 Node.js `22.12.0` 或更高版本；当前 Electron 42 依赖链要求 Node 22+。

网络边界：

- 离线或非校园网环境：可以正常打开软件，使用本地 mock fallback 演示三屏人脸检索壳体、路线图和占位数据。
- 校园网、VPN 或 SSH 隧道可用时：可以连接服务器上的真实 CampusVision C1 服务，执行真实视频/人脸检索并显示 C1 关键帧和轨迹。
- 如果不在校园网且没有到 C1 服务器的 VPN/隧道，真实 C1 检索不可用，但软件本身仍可打开并演示 mock 流程。

```powershell
python -m pip install -r backend/requirements.txt
npm install
npm run desktop
```

开发时打开 DevTools：

```powershell
npm run desktop:dev
```

## 发布桌面安装包

Windows 安装包由 GitHub Actions 构建。发布流程：

```powershell
npm version 0.1.x --no-git-tag-version
git add package.json package-lock.json
git commit -m "Bump version to 0.1.x"
git push
git tag -a v0.1.x -m "GKGuard v0.1.x"
git push origin v0.1.x
```

tag 推送后，workflow 会安装 Python 和 Node.js 22、运行后端测试、构建 Electron Windows 安装包、生成 Release 说明，并把安装包和更新元数据附到 GitHub Release。

如果 `docs/releases/v0.1.x.md` 存在，workflow 会优先使用这份人工维护的双语详细说明；否则会生成带中文/English 跳转、安装说明、提交和文件变更的兜底 Release 正文。

本地只做冒烟打包时可运行：

```powershell
npm run pack
```

`release/` 为本地构建产物目录，已被 git 忽略。

## 测试

```powershell
cd backend
python -m pytest
```

## 演示路径

主演示流程：

1. 启动 C1 和 C2，或只启动 C2 使用 mock fallback。
2. 打开 `/demo`。
3. 上传目标人脸图片。
4. 点击 `开始检索`。
5. 在结果页确认数据来源为 `C1 CampusVision` 或 `本地模拟`。
6. 点击 `查看人物路线图` 查看轨迹、时间线和摘要。

保留的旧 mock API 如 `GET /search/persons?student_id=S2026001`、`POST /search/image`、`GET /persons/P001/timeline` 仍可用于 API 级演示。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# GKGuard C2 AI Search Demo

GKGuard is the C2 demo shell for the campus security AI search project. As of `v0.1.13`, this repository contains the C2 backend, the three-screen face-search frontend, the Electron desktop shell, C1 auto-connection with an SSH password prompt, an in-app update entry, and the imported C1 CampusVision video retrieval service as a separate module.

## Current Status

- The C2 backend lives in `backend/` and provides FastAPI APIs, the static demo UI, the C1 proxy, mock fallback, audit APIs, and CampusCar/UE placeholder APIs.
- The C2 frontend lives in `backend/app/static/` and currently focuses on three screens: face search, face-search results, and person route map; the upload and result screens prefer the full uploaded target image and render C1 keyframe thumbnails in the record list.
- The Electron shell lives in `desktop/`; GitHub Actions can build the Windows installer. The packaged app prioritizes the SSH tunnel, prompts for the server SSH password when needed, also opens the connection window and retries when real C1 search returns 503, and exposes a top-right `检查更新` entry in desktop mode to download the latest installer directly.
- The C1 source lives in `services/campusvision-c1/` and owns video upload, frame sampling, face embeddings, person indexing, image search, and trajectory output.
- C2 now exposes `/c1/...` proxy endpoints and can connect to the real C1 service through an SSH tunnel.
- If C1 is unavailable, no image is uploaded, or the C1 request fails, the frontend first attempts the desktop C1 connection/retry path; it falls back to local mock records only when C1 remains unavailable.

## Project Structure

```text
backend/
  app/
    main.py
    routers/
    services/
    static/
  data/mock/
  tests/
  requirements.txt
desktop/
docs/
  api_contract.md
  c1_c2_integration.md
  c1_auto_connection.md
  campuscar_ue_integration.md
  data_dictionary.md
  demo_script.md
  releases/
services/
  campusvision-c1/
    app/
    docs/
    scripts/
    README.md
```

## Repository Governance And Usage

- [LICENSE](LICENSE): current source-available / all rights reserved notice.
- [OPEN_SOURCE.md](OPEN_SOURCE.md): open/closed-source boundary, allowed usage scope, and third-party dependency notes.
- [PRIVACY.md](PRIVACY.md): real media, personal information, C1 runtime data, and credential handling rules.
- [SECURITY.md](SECURITY.md): security reporting and sensitive information handling requirements.
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution flow, validation commands, and documentation rules.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): collaboration behavior rules.
- [SUPPORT.md](SUPPORT.md): support paths and support boundaries.
- [GOVERNANCE.md](GOVERNANCE.md): C1, C2, CampusCar/UE, and documentation ownership.

## C1 / C2 Integration

C2 currently implements these C1 proxy endpoints:

- `GET /c1/status`: checks C1 OpenAPI and `/health`.
- `GET /c1/persons`: reads the C1 person index and rewrites media URLs for C2.
- `GET /c1/videos`: reads C1 videos.
- `POST /c1/search/person-by-image`: accepts frontend field `file`, forwards it to C1 field `files`, and normalizes the result for the C2 UI.
- `GET /c1/media/{frame|face}/{face_id}`: proxies C1 frame and face-crop images.

Default local adapter URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

The packaged app has built-in C1 candidates: `http://10.4.167.122:8000` and `http://127.0.0.1:18000`. After opening the app, it probes them automatically. If C1 is not detected, it prompts to open an SSH login window. You only type the server password in PowerShell, and GKGuard does not store it.

Extra configuration is usually not required. If the server address or account changes, override defaults with `%APPDATA%\GKGuard\c1-connection.json`; see [docs/examples/c1-connection.example.json](docs/examples/c1-connection.example.json).

If C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, create an SSH tunnel first:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

Real C1 search requires `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, inspect the environment of the running uvicorn worker and restart C1 with the current `.env`.

See [docs/c1_c2_integration.md](docs/c1_c2_integration.md) for the service boundary, field mapping, and handoff checklist.
See [docs/c1_auto_connection.md](docs/c1_auto_connection.md) for automatic connection, candidate C1 URLs, and SSH tunnel setup.

## CampusCar / UE Placeholder

C2 keeps a stable CampusCar/UE integration contract only. It does not package the UE runtime and does not run ROS2 nodes inside the desktop app.

Placeholder endpoints:

- `POST /car-tasks/mock-dispatch`: creates a mock field-review task and returns `bridge_contract`.
- `GET /car-tasks/ue-bridge-status`: returns placeholder rosbridge, UE test app, and topic information.

Expected external topics:

- `/U2RTopic_Command`: command intent from C2 or an adapter.
- `/R2UTopic_Pos`: vehicle or UE pose feedback.
- `/R2UTopic_Text`: text or status feedback.

See [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md) for details.

## Run C2 Locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:C1_BASE_URL = "http://127.0.0.1:18000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Open:

```text
http://127.0.0.1:8002/demo
http://127.0.0.1:8002/docs
```

If C1 is not connected, the demo UI still works through the local mock fallback.

## Run The Desktop App

The latest Windows installer from GitHub Releases is for the C2 desktop demo. After installation, opening the app starts the bundled local C2 backend and loads `/demo`; Python, Node.js, and manual C2 startup are not required for the packaged app.

The desktop app includes a top-right `检查更新` entry. It checks the latest GitHub Release, and when a newer version is available, clicking again downloads the newest `GKGuard-Setup-*.exe` directly and prompts you to open the download folder when complete.

For local desktop development or packaging, use Node.js `22.12.0` or later. The current Electron 42 dependency chain requires Node 22+.

Network boundary:

- Offline or outside campus network: the app opens normally and can use local mock fallback for the three-screen face-search shell, route map, and placeholder data.
- Campus network, VPN, or SSH tunnel available: the app can connect to the server-side CampusVision C1 service for real video/face search, C1 keyframes, and trajectories.
- Without campus access or a VPN/tunnel to the C1 server, real C1 search is unavailable, but the app itself still opens and can demonstrate the mock flow.

```powershell
python -m pip install -r backend/requirements.txt
npm install
npm run desktop
```

For DevTools:

```powershell
npm run desktop:dev
```

## Build A Desktop Release

Windows installers are built by GitHub Actions:

```powershell
npm version 0.1.x --no-git-tag-version
git add package.json package-lock.json
git commit -m "Bump version to 0.1.x"
git push
git tag -a v0.1.x -m "GKGuard v0.1.x"
git push origin v0.1.x
```

After a tag is pushed, the workflow installs Python and Node.js 22, runs backend tests, builds the Electron Windows installer, generates release notes, and attaches the installer and update metadata to the GitHub Release.

If `docs/releases/v0.1.x.md` exists, the workflow uses that curated bilingual detailed note first; otherwise it generates a fallback Release body with Chinese/English jump links, installation notes, commits, and file changes.

For local smoke packaging only:

```powershell
npm run pack
```

`release/` is ignored by git.

## Tests

```powershell
cd backend
python -m pytest
```

## Demo Path

Primary visual demo flow:

1. Start C1 and C2, or start only C2 for mock fallback.
2. Open `/demo`.
3. Upload a target face image.
4. Click `开始检索`.
5. Confirm whether the result source is `C1 CampusVision` or `本地模拟`.
6. Click `查看人物路线图` to inspect the route, timeline, and summary.

When C1 is connected, the UI calls `/c1/search/person-by-image` and displays real C1 frames through `/c1/media/...`. When C1 is not available or no image is uploaded, the UI uses the local mock records so the shell can still be demonstrated.

Legacy mock API demos such as `GET /search/persons?student_id=S2026001`, `POST /search/image`, and `GET /persons/P001/timeline` remain available for API-level walkthroughs and non-C1 demos.

<p align="right"><a href="#english">Back to English top</a></p>
