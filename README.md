<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# GKGuard C2 AI 搜索演示

GKGuard 是校园安防 AI 检索项目中的 C2 演示端。当前 `v0.1.8` 状态下，仓库包含 C2 后端、三界面人脸检索前端、Electron 桌面壳，以及作为独立模块导入的 C1 CampusVision 视频检索服务。

## 当前状态

- C2 后端位于 `backend/`，提供 FastAPI API、静态演示页、C1 代理、mock fallback、审计和 CampusCar/UE 占位接口。
- C2 前端位于 `backend/app/static/`，当前主流程为 `人脸检索`、`人脸检索结果`、`人物路线图` 三个界面。
- Electron 桌面壳位于 `desktop/`，GitHub Actions 可构建 Windows 安装包。
- C1 源码位于 `services/campusvision-c1/`，负责视频上传、抽帧、人脸 embedding、人物库、以图搜人和轨迹输出。
- C2 已实现 `/c1/...` 代理，可以通过 SSH 隧道连接服务器上的真实 C1 服务。
- 当 C1 不可用、未上传图片或接口报错时，C2 前端会自动回退到本地模拟记录，方便离线演示。

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

如果 C1 在远程服务器上并绑定到服务器本机 `127.0.0.1:8000`，先在 C2 机器上建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

C1 真实检索需要 `FACE_ENGINE=insightface`。如果 `/api/v1/persons` 正常但 `/health` 或以图搜人返回 500，优先检查运行中 uvicorn worker 的环境变量，并用当前 `.env` 重启 C1 服务。

更多字段映射和交接检查见 [docs/c1_c2_integration.md](docs/c1_c2_integration.md)。

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

tag 推送后，workflow 会安装 Python 和 Node.js、运行后端测试、构建 Electron Windows 安装包、生成 Release 说明，并把安装包和更新元数据附到 GitHub Release。

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

GKGuard is the C2  demo shell for the campus security AI search project. As of `v0.1.8`, this repository contains the C2 backend, the three-screen face-search frontend, the Electron desktop shell, and the imported C1 CampusVision video retrieval service as a separate module.

## Current Status

- The C2 backend lives in `backend/` and provides FastAPI APIs, the static demo UI, the C1 proxy, mock fallback, audit APIs, and CampusCar/UE placeholder APIs.
- The C2 frontend lives in `backend/app/static/` and currently focuses on three screens: face search, face-search results, and person route map.
- The Electron shell lives in `desktop/`; GitHub Actions can build the Windows installer.
- The C1 source lives in `services/campusvision-c1/` and owns video upload, frame sampling, face embeddings, person indexing, image search, and trajectory output.
- C2 now exposes `/c1/...` proxy endpoints and can connect to the real C1 service through an SSH tunnel.
- If C1 is unavailable, no image is uploaded, or the C1 request fails, the frontend falls back to local mock records for offline demonstrations.

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

If C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, create an SSH tunnel first:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

Real C1 search requires `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, inspect the environment of the running uvicorn worker and restart C1 with the current `.env`.

See [docs/c1_c2_integration.md](docs/c1_c2_integration.md) for the service boundary, field mapping, and handoff checklist.

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

After a tag is pushed, the workflow installs Python and Node.js, runs backend tests, builds the Electron Windows installer, generates release notes, and attaches the installer and update metadata to the GitHub Release.

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
