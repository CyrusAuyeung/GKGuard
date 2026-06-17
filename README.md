<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# GKGuard C2 AI 搜索演示

GKGuard 是校园安防 AI 检索项目中的 GKGuard C2 工作台：负责桌面界面、本地后端、检索结果展示、路线可视化、本地模拟回退、审计和外部服务代理。CampusVision C1 是独立的视频检索服务：负责视频上传、抽帧、人脸向量、人物库、以图搜人、关键帧和轨迹输出。当前 `v0.1.23` 状态下，仓库包含 GKGuard C2 后端、三屏人脸检索前端、Electron 桌面壳、CampusVision C1 自动连接/内嵌 SSH 密码窗口和连接进度、响应式宽屏布局、完整显示上传图、CampusVision C1 人脸裁剪缩略图和 CampusVision C1 关键帧的媒体展示、关键帧预览弹窗、路线点/时间线定位联动、空状态与键盘焦点状态、移动端上传页和操作按钮密度优化、结果/路线记录横向滚动提示、移动端路线当前轨迹摘要、窄屏路线图标签边缘避让和紧凑图例、统一且不会空白显示的状态提示、旧后台资源复用保护、Playwright 浏览器 E2E 回归、GKGuard Roadmap 半自动字段脚本、经过细节修正的线性功能图标、品牌图标文件、软件内下载并重启安装的更新入口，以及作为独立模块导入的 CampusVision C1 服务源码。

## 仓库版本

- 当前最新版本：`v0.1.23`。
- 桌面安装包：GitHub Release 中包含 Windows 安装包、`.blockmap` 和 `latest.yml`。
- 代码形态：仓库同时保留可本地运行的 FastAPI 后端、静态前端、Electron 桌面壳和导入的 CampusVision C1 源码。
- 文档形态：仓库内维护中英双语 README、API 规范、CampusVision C1 / GKGuard C2 集成说明、演示脚本、数据字典、发布说明和管理文档。

## 仓库内容

当前仓库包含以下主要模块：

- GKGuard C2 FastAPI 后端：健康检查、人员/车辆模拟 API、事件处置、审计、CampusVision C1 代理和 CampusCar/UE 占位接口。
- GKGuard C2 静态前端：人脸检索、检索结果、人物路线图三屏流程，支持上传、重新上传、结果查看、路线查看、响应式窗口宽度和导出入口。
- GKGuard C2 本地代理层：在 GKGuard C2 后端内探测 CampusVision C1 服务候选地址，检查 `/openapi.json` 与 `/health`，转发以图搜人请求，改写媒体 URL，并把 CampusVision C1 响应归一化为 GKGuard C2 视图模型。
- Electron 桌面壳：启动内置 GKGuard C2 后端、显示启动页、加载演示页、内嵌 CampusVision C1 SSH 密码窗口、连接进度和应用内更新。
- 发布工程：GitHub Actions 自动构建 Windows 安装包，生成发布说明，并上传安装包和 Electron 自动更新元数据。
- 文档与管理：双语 README、API 规范、CampusVision C1 / GKGuard C2 集成说明、自动连接说明、演示脚本、数据字典、发布说明、安全/隐私/贡献/支持声明。

## 仓库边界

- 不包含真实 CampusCar 控制、ROS2 节点、UE 运行时或底盘控制逻辑。
- 不包含真实 CampusVision C1 运行数据、真实视频、真实查询图片、SQLite 数据库、模型缓存或服务器 `.env`。
- 不把服务器密码、SSH 私钥、token 或 API key 写入仓库、配置文件或日志。
- 离线或无校园网/VPN/SSH 隧道环境下，真实 CampusVision C1 检索不可用；此时 GKGuard C2 前端使用本地模拟回退展示工作台流程。

## 当前状态

- GKGuard C2 后端位于 `backend/`，提供 FastAPI API、静态演示页、CampusVision C1 代理、本地模拟回退、审计和 CampusCar/UE 占位接口。
- GKGuard C2 前端位于 `backend/app/static/`，当前主流程为 `人脸检索`、`人脸检索结果`、`人物路线图` 三个界面；页面宽度会随桌面窗口扩展，支持 `680x640` 小窗口下无横向溢出；上传页和结果页会优先完整显示用户上传的目标照片，记录列表优先展示 CampusVision C1 人脸裁剪缩略图，详情区完整展示 CampusVision C1 关键帧，并支持打开关键帧预览弹窗；结果页和路线页都可一键返回重新上传；移动端上传页压缩表单和上传区高度，结果页和路线页操作按钮使用约 42px 触控高度的双列紧凑布局；结果页和路线页记录列表提供横向滚动提示与右侧渐隐；路线页工具栏将 `重新上传` 固定在最左侧，并在地图前展示轨迹点、起点、终点、总时长和当前轨迹摘要，路线图点位、关联记录和时间线可联动定位当前记录，窄屏地图标签会避让边缘且图例压缩为横向条；390px 视口下模拟关键帧装饰和路线地图元素保持在容器内；检索、CampusVision C1 回退、定位、导出和更新入口使用统一状态提示，初始和切屏状态不会显示空白 toast。
- Electron 桌面壳位于 `desktop/`，GitHub Actions 可构建 Windows 安装包；安装版打开后会优先建立通向 CampusVision C1 的 SSH 隧道，并在软件内连接窗口显示服务器账号、隧道目标、四步连接进度、失败重试和密码安全说明；真实检索遇到 CampusVision C1 503 时也会打开同一个内嵌连接窗口并重试；桌面模式右上角提供 `检查更新` 入口，可在应用内下载新版并重启安装。
- CampusVision C1 源码位于 `services/campusvision-c1/`，负责视频上传、抽帧、人脸 embedding、人物库、以图搜人和轨迹输出。
- GKGuard C2 已实现 `/c1/...` 代理，可以通过 SSH 隧道连接服务器上的真实 CampusVision C1 服务。
- 当 CampusVision C1 不可用、未上传图片或接口报错时，GKGuard C2 前端会先尝试桌面端 CampusVision C1 连接/重试；仍不可用时才回退到本地模拟记录，方便离线演示。

## 架构概览

```text
Windows Desktop App (Electron)
  -> bundled local GKGuard C2 backend (FastAPI)
  -> /demo static UI
  -> /c1/... adapter endpoints
  -> CampusVision C1 candidate URLs
       -> local SSH tunnel http://127.0.0.1:18000
       -> campus direct URL http://10.4.167.122:8000
       -> custom URLs from environment or c1-connection.json

External integration boundary:
  -> /car-tasks/... placeholder interface specification
  -> external CampusCar / ROS2 / UE adapter service
```

GKGuard C2 前端只访问 GKGuard C2 后端。真实 CampusVision C1 检索、CampusVision C1 媒体帧、CampusCar/UE 占位能力都通过 GKGuard C2 后端接口暴露，避免前端直接依赖多个外部服务。

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
tests/
  e2e/
    gkguard-ui.spec.js
desktop/
  assets/
docs/
  api_contract.md
  c1_c2_integration.md
  c1_auto_connection.md
  campuscar_ue_integration.md
  data_dictionary.md
  demo_script.md
  examples/
  releases/
services/
  campusvision-c1/
    app/
    docs/
    scripts/
    README.md
scripts/
  Update-RoadmapItem.ps1
.github/
  workflows/ci.yml
  workflows/release-desktop.yml
  ISSUE_TEMPLATE/
```

## 文档索引

- [docs/README.md](docs/README.md)：文档地图和维护阅读顺序。
- [docs/api_contract.md](docs/api_contract.md)：GKGuard C2 API、CampusVision C1 代理接口和字段说明。
- [docs/c1_c2_integration.md](docs/c1_c2_integration.md)：CampusVision C1 与 GKGuard C2 的职责边界、字段映射和联调清单。
- [docs/c1_auto_connection.md](docs/c1_auto_connection.md)：CampusVision C1 候选地址、SSH 隧道和内嵌密码窗口策略。
- [docs/demo_script.md](docs/demo_script.md)：安装版和本地开发版演示流程。
- [docs/data_dictionary.md](docs/data_dictionary.md)：模拟数据、CampusVision C1 检索结果和 CampusCar/UE 占位字段。
- [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md)：CampusCar、ROS2、UE Bridge 的当前占位接口规范。
- [docs/releases/](docs/releases/)：各版本双语发布说明。

## 仓库管理与使用声明

- [LICENSE](LICENSE)：当前 source-available / 保留所有权利声明。
- [OPEN_SOURCE.md](OPEN_SOURCE.md)：开源与闭源边界、允许使用范围和第三方依赖说明。
- [PRIVACY.md](PRIVACY.md)：真实媒体、个人信息、CampusVision C1 运行数据和凭据处理规则。
- [SECURITY.md](SECURITY.md)：安全问题报告方式和敏感信息处理要求。
- [CONTRIBUTING.md](CONTRIBUTING.md)：贡献流程、验证命令和文档规范。
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)：项目协作行为准则。
- [SUPPORT.md](SUPPORT.md)：问题反馈入口和支持边界。
- [GOVERNANCE.md](GOVERNANCE.md)：A组机械结构、B组嵌入式控制、C组算法感知的模块维护职责。

## 仓库协作流程

- `main` 是稳定基线，受 GitHub 规则集 `Protect main` 保护；常规功能、配置、发布和文档协作改动通过 `codex/...` 或其他短期分支提交 Pull Request 后合并。
- 小范围文档勘误、GitHub Release 正文同步或紧急低风险修复可由维护者直接提交到 `main`，但必须保留清晰提交记录。
- Pull Request 合并前需要 `.github/workflows/ci.yml` 中的 `Verify` 检查通过，完成审查，并解决所有对话；仓库使用 squash merge，合并后删除源分支。
- Issue 和 Pull Request 使用 `area:*`、`type:*`、`priority:*`、`blocked`、`needs-info` 标签归类，并放入 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) 跟踪；Project item 应补齐 `Status`、`Area`、`Type`、`Priority`、`Blocked`、`Start date`、`End date`、`Timeline order` 和必要的 `Target version`，按真实日期和先后顺序展示。
- Milestone 暂不强制使用；CODEOWNERS 暂不启用，后续明确发布节奏或审查归属后再补充。

## CampusVision C1 / GKGuard C2 接入

这里的 CampusVision C1 指 CampusVision 视频检索服务，GKGuard C2 指 GKGuard 桌面工作台和本地代理层。当前 GKGuard C2 已实现以下 CampusVision C1 代理接口：

- `GET /c1/status`：检查 CampusVision C1 OpenAPI 与 `/health`。
- `GET /c1/persons`：读取 CampusVision C1 人物库，并把媒体 URL 改写为 GKGuard C2 可访问路径。
- `GET /c1/videos`：读取 CampusVision C1 视频列表。
- `POST /c1/search/person-by-image`：接收 GKGuard C2 前端上传字段 `file`，转发给 CampusVision C1 的 `files` 字段，并归一化为 GKGuard C2 前端视图模型。
- `GET /c1/media/{frame|face}/{face_id}`：代理 CampusVision C1 关键帧和人脸裁剪图。

本地开发默认使用：

```text
C1_BASE_URL=http://127.0.0.1:18000
```

安装版内置默认 CampusVision C1 候选地址 `http://127.0.0.1:18000` 和 `http://10.4.167.122:8000`，并优先使用本机 SSH 隧道。打开应用后如果尚未通过隧道连接 CampusVision C1，会在软件内弹出服务器密码窗口；窗口会显示服务器账号、隧道目标、连接原因和四步连接进度，连接失败时停留在窗口内允许重新输入。若直连服务可达但真实检索返回 503，页面也会触发同一个内嵌连接窗口并重试一次。密码只用于本次 SSH 连接，GKGuard 不保存、不落盘、不记录密码。

通常不需要额外配置。若服务器地址或账号变化，可用 `%APPDATA%\GKGuard\c1-connection.json` 覆盖默认值，示例见 [docs/examples/c1-connection.example.json](docs/examples/c1-connection.example.json)。

如果 CampusVision C1 在远程服务器上并绑定到服务器本机 `127.0.0.1:8000`，安装版会自动建立内嵌 SSH 隧道。开发或排障时也可以在运行 GKGuard C2 的机器上手动建立 SSH 隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

CampusVision C1 真实检索需要 `FACE_ENGINE=insightface`。如果 `/api/v1/persons` 正常但 `/health` 或以图搜人返回 500，优先检查运行中 uvicorn worker 的环境变量，并用当前 `.env` 重启 CampusVision C1 服务。

更多字段映射和联调检查见 [docs/c1_c2_integration.md](docs/c1_c2_integration.md)。
自动连接、候选 CampusVision C1 地址和 SSH 隧道配置见 [docs/c1_auto_connection.md](docs/c1_auto_connection.md)。

## CampusCar / UE 占位

当前 GKGuard C2 只保留稳定的 CampusCar/UE 占位接口规范，不打包 UE 运行时，也不在桌面应用内运行 ROS2 节点。

占位接口：

- `POST /car-tasks/mock-dispatch`：创建模拟现场复核任务，并返回 `bridge_contract`，用于 C组算法感知与 B组嵌入式控制后续对接。
- `GET /car-tasks/ue-bridge-status`：返回 rosbridge、UE 测试应用和预期话题的占位状态。

预期外部话题：

- `/U2RTopic_Command`：GKGuard C2 或适配器下发命令意图。
- `/R2UTopic_Pos`：车辆或 UE 位姿反馈。
- `/R2UTopic_Text`：文本或状态反馈。

更多说明见 [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md)。

## 本地运行 GKGuard C2

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

未连接 CampusVision C1 服务时，演示页仍可通过本地模拟回退运行。

## 运行桌面端

从 GitHub Release 下载的最新 Windows 安装包用于 GKGuard C2 桌面端演示。安装后直接打开即可启动内置本地 GKGuard C2 后端并进入 `/demo`，不需要另外安装 Python、Node.js 或手动启动 GKGuard C2 服务。

桌面软件右上角提供 `检查更新` 入口：点击后会查询 GitHub 最新 Release；发现新版时再次点击会在应用内下载更新，下载完成后点击 `重启安装` 即可完成升级，不需要手动到 GitHub 重新下载安装包。

本地开发或打包桌面端时建议使用 Node.js `22.12.0` 或更高版本；当前 Electron 42 依赖链要求 Node 22+。

网络边界：

- 离线或非校园网环境：可以正常打开软件，使用本地模拟回退演示三屏人脸检索壳体、路线图和占位数据。
- 校园网、VPN 或 SSH 隧道可用时：可以连接服务器上的真实 CampusVision C1 服务，执行真实视频/人脸检索并显示 CampusVision C1 关键帧和轨迹。
- 如果不在校园网且没有到 CampusVision C1 服务所在服务器的 VPN/隧道，真实 CampusVision C1 检索不可用，但软件本身仍可打开并演示本地模拟流程。

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

版本标签推送后，发布工作流会安装 Python 和 Node.js 22、运行后端测试、前端/桌面端语法检查、浏览器 E2E 回归、构建 Electron Windows 安装包、生成发布说明，并把安装包和更新元数据附到 GitHub Release。

如果 `docs/releases/v0.1.x.md` 存在，发布工作流会优先使用这份人工维护的双语详细说明；否则会生成带中文/English 跳转、安装说明、提交和文件变更的兜底 GitHub Release 正文。

Pull Request 和 `main` 分支推送会触发 `.github/workflows/ci.yml`，执行后端测试、前端脚本语法检查、桌面端语法检查、桌面后端入口编译、浏览器 E2E 回归和 npm 安全审计。Release 安装包仍只由 `v*` 标签触发的 `.github/workflows/release-desktop.yml` 构建。

本地只做冒烟打包时可运行：

```powershell
npm run pack
```

`release/` 为本地构建产物目录，已被 git 忽略。

## 验证命令

代码或打包相关改动后，建议执行：

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check backend/app/static/app.js
node --check desktop/main.js
node --check desktop/preload.js
npm run test:e2e
npm audit --audit-level=low
npm run dist
```

当前 `v0.1.23` 的基线结果：后端测试 `25 passed`，前端脚本、Electron 主进程和 preload 语法检查通过，桌面后端入口编译通过，`npm run test:e2e` 通过 6 个 Chromium 用例，`npm audit --audit-level=low` 无漏洞，`git diff --check` 通过；浏览器 E2E 覆盖 `1280x720`、`680x640` 和 `390x720` 视口下的本地模拟检索、检索结果、路线图、路线点定位、时间线定位、返回结果页、重新上传流程，以及模拟 CampusVision C1 媒体结果的关键帧预览弹窗，并检查无页面级横向溢出、无空白 toast、浏览器 console warning/error 为 0；GitHub Actions CI 工作流覆盖 PR 基础检查，发布工作流会生成 Windows 安装包和 Electron 自动更新元数据。

只修改文档时，可至少执行：

```powershell
git diff --check
```

并检查 README、相关 docs 文件和发布说明是否保持中英双语同步。

## 后端测试

```powershell
cd backend
python -m pytest
```

## 演示路径

主演示流程：

1. 启动 CampusVision C1 服务和 GKGuard C2 后端，或只启动 GKGuard C2 后端使用本地模拟回退。
2. 打开 `/demo`。
3. 上传目标人脸图片。
4. 点击 `开始检索`。
5. 在结果页确认数据来源为 `CampusVision C1` 或 `本地模拟`。
6. 点击 `查看人物路线图` 查看地图路线、地图上方摘要、时间线和轨迹摘要。

保留的旧版模拟 API 如 `GET /search/persons?student_id=S2026001`、`POST /search/image`、`GET /persons/P001/timeline` 仍可用于 API 级演示。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# GKGuard C2 AI Search Demo

GKGuard is the GKGuard C2 workbench for the campus security AI search project: it owns the desktop UI, local backend, result presentation, route visualization, mock fallback, audit features, and external-service proxy layer. CampusVision C1 is the separate video-search service for video upload, frame sampling, face embeddings, person indexing, image-based person search, keyframes, and trajectory output. As of `v0.1.23`, this repository contains the GKGuard C2 backend, the three-screen face-search frontend, the Electron desktop shell, CampusVision C1 auto-connection with an embedded SSH password prompt and connection progress, responsive wide-window layout, full-display media handling for uploaded targets, CampusVision C1 face-crop thumbnails, CampusVision C1 keyframes, a keyframe preview dialog, route-point/timeline selection sync, empty states and keyboard focus states, mobile upload/action density improvements, horizontal-scroll hints for result and route records, a mobile current-trajectory summary, narrow-screen route-map label edge avoidance with a compact legend, unified status feedback that does not show empty toasts, stale-backend asset reuse protection, Playwright browser E2E regression, a GKGuard Roadmap field helper script, polished linear UI icons, brand icon assets, an in-app update flow that downloads and restarts to install updates, and the imported CampusVision C1 service source as a separate module.

## Repository Version

- Latest version: `v0.1.23`.
- Desktop installer: GitHub Releases contain the Windows installer, `.blockmap`, and `latest.yml`.
- Code shape: the repository keeps the locally runnable FastAPI backend, static frontend, Electron desktop shell, and imported CampusVision C1 source.
- Documentation shape: the repository maintains bilingual README, API specification, CampusVision C1 / GKGuard C2 integration notes, demo script, data dictionary, release notes, and management documents.

## Repository Contents

GKGuard is the GKGuard C2 workbench for the campus-security AI search project: it owns the desktop UI, local backend, result presentation, route visualization, mock fallback, audit features, and external-service proxy layer. CampusVision C1 is the separate video-search service: it owns video upload, frame sampling, face embeddings, person indexing, image-based person search, keyframes, and trajectory output.

This repository currently covers:

- GKGuard C2 FastAPI backend: health checks, people/vehicle mock APIs, event disposition, audit, CampusVision C1 proxy, and CampusCar/UE placeholder endpoints.
- GKGuard C2 static frontend: face search, search results, and person route map screens with upload, re-upload, result review, route review, responsive window width, and export entry points.
- GKGuard C2 local proxy layer: inside the GKGuard C2 backend, probes CampusVision C1 service candidate URLs, checks `/openapi.json` and `/health`, forwards image-search requests, rewrites media URLs, and normalizes CampusVision C1 responses into GKGuard C2 view models.
- Electron desktop shell: bundled GKGuard C2 backend startup, loading page, demo page loading, embedded CampusVision C1 SSH password window, connection progress, and in-app updates.
- Release engineering: GitHub Actions builds the Windows installer, generates Release notes, and uploads the installer plus Electron update metadata.
- Documentation and management: bilingual README, API specification, CampusVision C1 / GKGuard C2 integration notes, auto-connection guide, demo script, data dictionary, release notes, and security/privacy/contribution/support statements.

## Repository Boundary

- Real CampusCar control, ROS2 nodes, UE runtime, and chassis-control logic are not included.
- Real CampusVision C1 runtime data, real videos, real query images, SQLite databases, model caches, and server `.env` files are not included.
- Server passwords, SSH private keys, tokens, and API keys must not be written to the repository, config files, or logs.
- Real CampusVision C1 search is unavailable offline or without campus network, VPN, or SSH tunnel access; in that case, the GKGuard C2 frontend uses mock fallback for the workbench flow.

## Current Status

- The GKGuard C2 backend lives in `backend/` and provides FastAPI APIs, the static demo UI, the CampusVision C1 proxy, mock fallback, audit APIs, and CampusCar/UE placeholder APIs.
- The GKGuard C2 frontend lives in `backend/app/static/` and currently focuses on three screens: face search, face-search results, and person route map; the layout expands with the desktop window, avoids horizontal overflow down to `680x640`, prefers the full uploaded target image on upload and result screens, uses CampusVision C1 face crops for record thumbnails, renders complete CampusVision C1 keyframes in detail panels, provides a return action to upload a new target from result or route screens, compacts the mobile upload form, and uses two-column mobile action groups with about 42px touch height; result and route record lists include horizontal-scroll hints and a right fade; the route screen keeps `重新上传` as the leftmost toolbar control and shows route points, start, end, duration, and current-trajectory summary before the map on mobile; narrow-screen route-map labels stay inside the viewport with a compact legend; simulated keyframe decoration and route-map elements stay inside their containers at 390px; and the unified status feedback layer does not show empty toasts during initialization or screen switches.
- The Electron shell lives in `desktop/`; GitHub Actions can build the Windows installer. The packaged app prioritizes the SSH tunnel to CampusVision C1 and shows an embedded connection window with the server account, tunnel target, four-step progress, retry-on-failure state, and password-safety note when needed. It also opens the same embedded connection window and retries when real CampusVision C1 search returns 503, and exposes a top-right `检查更新` entry in desktop mode for in-app update download and restart-to-install.
- The CampusVision C1 source lives in `services/campusvision-c1/` and owns video upload, frame sampling, face embeddings, person indexing, image search, and trajectory output.
- GKGuard C2 now exposes `/c1/...` proxy endpoints and can connect to the real CampusVision C1 service through an SSH tunnel.
- If CampusVision C1 is unavailable, no image is uploaded, or the CampusVision C1 request fails, the frontend first attempts the desktop CampusVision C1 connection/retry path; it falls back to local mock records only when CampusVision C1 remains unavailable.

## Architecture Overview

```text
Windows Desktop App (Electron)
  -> bundled local GKGuard C2 backend (FastAPI)
  -> /demo static UI
  -> /c1/... adapter endpoints
  -> CampusVision C1 candidate URLs
       -> local SSH tunnel http://127.0.0.1:18000
       -> campus direct URL http://10.4.167.122:8000
       -> custom URLs from environment or c1-connection.json

External integration boundary:
  -> /car-tasks/... placeholder interface specifications
  -> external CampusCar / ROS2 / UE adapter service
```

The GKGuard C2 frontend calls only the GKGuard C2 backend. Real CampusVision C1 search, CampusVision C1 media frames, and CampusCar/UE placeholder capabilities are exposed through GKGuard C2 backend API specifications so the frontend does not directly depend on multiple external services.

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
tests/
  e2e/
    gkguard-ui.spec.js
desktop/
  assets/
docs/
  api_contract.md
  c1_c2_integration.md
  c1_auto_connection.md
  campuscar_ue_integration.md
  data_dictionary.md
  demo_script.md
  examples/
  releases/
services/
  campusvision-c1/
    app/
    docs/
    scripts/
    README.md
scripts/
  Update-RoadmapItem.ps1
.github/
  workflows/ci.yml
  workflows/release-desktop.yml
  ISSUE_TEMPLATE/
```

## Documentation Index

- [docs/README.md](docs/README.md): documentation map and maintenance reading order.
- [docs/api_contract.md](docs/api_contract.md): GKGuard C2 APIs, CampusVision C1 proxy endpoints, and fields.
- [docs/c1_c2_integration.md](docs/c1_c2_integration.md): CampusVision C1 and GKGuard C2 boundary, field mapping, and integration checklist.
- [docs/c1_auto_connection.md](docs/c1_auto_connection.md): CampusVision C1 candidate URLs, SSH tunnel, and embedded password prompt strategy.
- [docs/demo_script.md](docs/demo_script.md): packaged-app and local-development demo flows.
- [docs/data_dictionary.md](docs/data_dictionary.md): mock data, CampusVision C1 search results, and CampusCar/UE placeholder fields.
- [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md): current placeholder interface specification for CampusCar, ROS2, and UE Bridge.
- [docs/releases/](docs/releases/): bilingual Release notes for each version.

## Repository Management And Usage

- [LICENSE](LICENSE): current source-available / all rights reserved notice.
- [OPEN_SOURCE.md](OPEN_SOURCE.md): open/closed-source boundary, allowed usage scope, and third-party dependency notes.
- [PRIVACY.md](PRIVACY.md): real media, personal information, CampusVision C1 runtime data, and credential handling rules.
- [SECURITY.md](SECURITY.md): security reporting and sensitive information handling requirements.
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution flow, validation commands, and documentation rules.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): collaboration behavior rules.
- [SUPPORT.md](SUPPORT.md): support paths and support boundaries.
- [GOVERNANCE.md](GOVERNANCE.md): CampusVision C1, GKGuard C2, CampusCar/UE, and documentation ownership.

## Repository Collaboration Workflow

- `main` is the stable baseline and is protected by the GitHub ruleset `Protect main`; normal feature, configuration, release, and documentation collaboration changes should enter through a Pull Request from `codex/...` or another short-lived branch.
- Maintainers may commit small documentation corrections, GitHub Release body synchronization, or urgent low-risk fixes directly to `main`, while keeping clear commit history.
- Before merge, Pull Requests must pass the `Verify` check from `.github/workflows/ci.yml`, complete review, and resolve all conversations. The repository uses squash merge and deletes merged head branches.
- Issues and Pull Requests use `area:*`, `type:*`, `priority:*`, `blocked`, and `needs-info` labels, and are tracked in the [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project. Project items should include `Status`, `Area`, `Type`, `Priority`, `Blocked`, `Start date`, `End date`, `Timeline order`, and required `Target version` so work is shown by real date and sequence.
- Milestones are not mandatory yet. CODEOWNERS is not enabled yet and should be added only after the release cadence or review ownership is clearer.

## CampusVision C1 / GKGuard C2 Integration

Here, CampusVision C1 means the CampusVision video-search service, and GKGuard C2 means the GKGuard desktop workbench plus local proxy layer. GKGuard C2 currently implements these CampusVision C1 proxy endpoints:

- `GET /c1/status`: checks CampusVision C1 OpenAPI and `/health`.
- `GET /c1/persons`: reads the CampusVision C1 person index and rewrites media URLs for GKGuard C2.
- `GET /c1/videos`: reads CampusVision C1 videos.
- `POST /c1/search/person-by-image`: accepts the GKGuard C2 frontend field `file`, forwards it to CampusVision C1 field `files`, and normalizes the result for the GKGuard C2 UI.
- `GET /c1/media/{frame|face}/{face_id}`: proxies CampusVision C1 frame and face-crop images.

Default local adapter URL:

```text
C1_BASE_URL=http://127.0.0.1:18000
```

The packaged app has built-in CampusVision C1 candidates: `http://127.0.0.1:18000` and `http://10.4.167.122:8000`, with the local SSH tunnel first. After opening the app, it probes them automatically. If the tunnel is not connected, it shows an embedded server-password window with account, tunnel target, connection reason, and four-step progress. Failed connections stay in that window so the password can be re-entered. The password is used only for the current SSH session; GKGuard does not store it, write it to disk, or log it.

Extra configuration is usually not required. If the server address or account changes, override defaults with `%APPDATA%\GKGuard\c1-connection.json`; see [docs/examples/c1-connection.example.json](docs/examples/c1-connection.example.json).

If CampusVision C1 runs on a remote server and is bound to that server's `127.0.0.1:8000`, the packaged app creates the embedded SSH tunnel for you. For development or troubleshooting, you can also create the tunnel manually on the GKGuard C2 machine:

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

Real CampusVision C1 search requires `FACE_ENGINE=insightface`. If `/api/v1/persons` works but `/health` or image search returns 500, inspect the environment of the running uvicorn worker and restart CampusVision C1 with the current `.env`.

See [docs/c1_c2_integration.md](docs/c1_c2_integration.md) for the service boundary, field mapping, and integration checklist.
See [docs/c1_auto_connection.md](docs/c1_auto_connection.md) for automatic connection, candidate CampusVision C1 URLs, and SSH tunnel setup.

## CampusCar / UE Placeholder

GKGuard C2 keeps a stable CampusCar/UE interface specification only. It does not package the UE runtime and does not run ROS2 nodes inside the desktop app.

Placeholder endpoints:

- `POST /car-tasks/mock-dispatch`: creates a mock field-review task and returns `bridge_contract`.
- `GET /car-tasks/ue-bridge-status`: returns placeholder rosbridge, UE test app, and topic information.

Expected external topics:

- `/U2RTopic_Command`: command intent from GKGuard C2 or an adapter.
- `/R2UTopic_Pos`: vehicle or UE pose feedback.
- `/R2UTopic_Text`: text or status feedback.

See [docs/campuscar_ue_integration.md](docs/campuscar_ue_integration.md) for details.

## Run GKGuard C2 Locally

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

If the CampusVision C1 service is not connected, the demo UI still works through the local mock fallback.

## Run The Desktop App

The latest Windows installer from GitHub Releases is for the GKGuard C2 desktop demo. After installation, opening the app starts the bundled local GKGuard C2 backend and loads `/demo`; Python, Node.js, and manual GKGuard C2 startup are not required for the packaged app.

The desktop app includes a top-right `检查更新` entry. It checks the latest GitHub Release, and when a newer version is available, clicking again downloads the update inside the app. After the download finishes, click `重启安装` to complete the upgrade without manually downloading another installer from GitHub.

For local desktop development or packaging, use Node.js `22.12.0` or later. The current Electron 42 dependency chain requires Node 22+.

Network boundary:

- Offline or outside campus network: the app opens normally and can use local mock fallback for the three-screen face-search shell, route map, and placeholder data.
- Campus network, VPN, or SSH tunnel available: the app can connect to the server-side CampusVision C1 service for real video/face search, CampusVision C1 keyframes, and trajectories.
- Without campus access or a VPN/tunnel to the CampusVision C1 server, real CampusVision C1 search is unavailable, but the app itself still opens and can demonstrate the mock flow.

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

After a tag is pushed, the workflow installs Python and Node.js 22, runs backend tests, frontend/desktop syntax checks, browser E2E regression, builds the Electron Windows installer, generates release notes, and attaches the installer and update metadata to the GitHub Release.

If `docs/releases/v0.1.x.md` exists, the workflow uses that curated bilingual detailed note first; otherwise it generates a fallback Release body with Chinese/English jump links, installation notes, commits, and file changes.

Pull requests and pushes to `main` trigger `.github/workflows/ci.yml`, which runs backend tests, frontend script syntax checks, desktop syntax checks, desktop backend entrypoint compilation, browser E2E regression, and npm security audit. Windows installer assets are still built only by `.github/workflows/release-desktop.yml` on `v*` tags.

For local smoke packaging only:

```powershell
npm run pack
```

`release/` is ignored by git.

## Validation Commands

For code or packaging changes, run:

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check backend/app/static/app.js
node --check desktop/main.js
node --check desktop/preload.js
npm run test:e2e
npm audit --audit-level=low
npm run dist
```

Current `v0.1.23` baseline: backend tests pass with `25 passed`, frontend script, Electron main-process, and preload syntax checks pass, the desktop backend entrypoint compiles, `npm run test:e2e` passes 6 Chromium cases, `npm audit --audit-level=low` reports no vulnerabilities, and `git diff --check` passes. Browser E2E covers mock search, results, route map, route-point locate, timeline locate, return to results, re-upload, and a mocked CampusVision C1 media keyframe preview dialog at `1280x720`, `680x640`, and `390x720`, with no page-level horizontal overflow, empty toast, or browser console warning/error. The GitHub Actions CI workflow covers PR checks, and the Release workflow produces the Windows installer and Electron auto-update metadata.

For documentation-only changes, run at least:

```powershell
git diff --check
```

Then check that README, related docs, and Release notes remain synchronized in Chinese and English.

## Backend Tests

```powershell
cd backend
python -m pytest
```

## Demo Path

Primary visual demo flow:

1. Start CampusVision C1 and GKGuard C2, or start only GKGuard C2 for mock fallback.
2. Open `/demo`.
3. Upload a target face image.
4. Click `开始检索`.
5. Confirm whether the result source is `CampusVision C1` or `本地模拟`.
6. Click `查看人物路线图` to inspect the route map, top route overview, timeline, and summary.

When CampusVision C1 is connected, the UI calls `/c1/search/person-by-image` and displays real CampusVision C1 frames through `/c1/media/...`. When CampusVision C1 is not available or no image is uploaded, the UI uses the local mock records so the shell can still be demonstrated.

Legacy mock API demos such as `GET /search/persons?student_id=S2026001`, `POST /search/image`, and `GET /persons/P001/timeline` remain available for API-level walkthroughs and non-CampusVision C1 demos.

<p align="right"><a href="#english">Back to English top</a></p>
