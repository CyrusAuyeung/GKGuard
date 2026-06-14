<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 演示脚本

## 目标

演示当前 GKGuard C2 闭环：上传人脸图片，优先调用 CampusVision C1 获取真实关键帧和轨迹；如果 C1 不可用，则回退本地模拟记录；同时保留案件研判、审计、CampusCar/UE 占位等 C2 mock 工作流。

## 主视觉流程：C1 真实检索

安装版 `v0.1.15` 推荐流程：

1. 下载并安装 `GKGuard-Setup-0.1.15.exe`。
2. 打开 GKGuard。
3. 软件会优先检查本机 SSH 隧道；如果尚未连接，在软件内“连接 C1 服务器”窗口输入服务器密码，并观察连接进度条。
4. 如果已经进入页面但真实检索返回 C1 503，页面会再次打开同一个内嵌连接窗口并在连接后自动重试一次。
5. 密码只用于本次 SSH 隧道连接，不会保存到配置或日志。
6. 等待软件检测到 `http://127.0.0.1:18000` 后进入演示页。
7. 搜索完成后可在结果页或路线页点击 `重新上传`，返回上传页开始下一次检索。
8. 后续需要升级时，点击右上角 `检查更新`，发现新版后再次点击会在应用内下载，完成后点击 `重启安装`。

GKGuard 不保存、不读取、不记录 SSH 密码。

本地开发流程：

1. 启动 C1，或连接团队 C1 服务器隧道。

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

期望 C1 状态：

```text
GET http://127.0.0.1:18000/health -> 200 OK, face_engine=insightface
```

1. 启动 C2 后端。

```powershell
cd backend
$env:C1_BASE_URL = "http://127.0.0.1:18000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

1. 打开视觉演示页。

```text
http://127.0.0.1:8002/demo
```

1. 需要直接测试接口时打开 API 文档。

```text
http://127.0.0.1:8002/docs
```

1. 检查 C1 适配器。

```text
GET /c1/status
```

期望结果：`reachable=true`、`healthOk=true`，且 C1 health 显示 `face_engine=insightface`。

1. 执行视觉检索。

```text
上传人脸或完整帧图片 -> 点击 开始检索 -> 查看 人脸检索结果
```

C1 已连接时期望结果：

- 结果页数据来源显示 `C1 CampusVision`。
- 上传页和结果页人物照片优先完整显示用户上传图；只有未上传图时才回退 C1 代表人脸。
- 检索记录列表展示 C1 关键帧缩略图，而不是默认人物占位图；若 C1 缩略图加载失败，才回退占位图。
- 记录列表显示 C1 摄像头和相似度。
- 详情区显示通过 `/c1/media/frame/...` 加载的真实关键帧。
- 点击 `查看人物路线图` 后，路线图使用 C1 trajectory 数据生成轨迹点、时间线和摘要。

C1 未连接、接口失败或未上传图片时期望结果：

- 桌面模式下，C1 检索失败会先打开软件内服务器密码窗口并重试一次。
- UI 回退到本地模拟记录。
- 结果页数据来源显示 `本地模拟`。
- 页面仍可用于演示 C2 壳和交互流程。

## 旧 mock API 演示

以下接口仍可用于不依赖 C1 的 API 级演示。

### 搜索演示人员

```text
GET /search/persons?student_id=S2026001
```

期望结果：返回 `P001` 这个主 demo 对象。

### 上传图片到 legacy mock 搜索

```text
POST /search/image?top_k=5&min_similarity=0.8
file: p001_target.jpg
```

期望结果：返回 `P001` 的 Top-K mock 记录。

### 生成人员时间线

```text
GET /persons/P001/timeline?min_similarity=0.9
```

期望结果：返回排序后的出现记录和摘要。

### 查看告警上下文

```text
GET /events/ALT-001/related-records
```

期望结果：返回告警详情、相关快照、时间线和摘要。

### 创建 CampusCar 模拟复核任务

```text
POST /car-tasks/mock-dispatch
```

请求体：

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "reason": "field review"
}
```

期望结果：返回 `arrived_mock` 状态和 `bridge_contract`。

### 查看 UE/CampusCar bridge 占位状态

```text
GET /car-tasks/ue-bridge-status
```

期望结果：返回 `/U2RTopic_Command`、`/R2UTopic_Pos`、`/R2UTopic_Text` 和未来视频流占位。

### 生成案件报告

```text
GET /events/ALT-001/report
```

期望结果：返回结构化报告、关键发现、建议动作和处置模板。

### 归档处置

```text
POST /events/ALT-001/disposition
```

期望结果：返回 `status_after=closed` 的模拟归档记录。

### 导出案件包

```text
GET /events/ALT-001/case-package
```

期望结果：返回 `PKG-ALT-001`，包含事件详情、对象信息、报告、时间线点、证据快照、审计日志和交接清单。

## 交接备注

- 当前前端使用 C1 归一化后的 `records` 和 `routePoints` 生成结果卡片、关键帧、地图点和路线。
- 控制/UE 组后续可替换 `/car-tasks/mock-dispatch` 背后的适配器，字段名保持稳定。
- 不要把 UE 测试 app 打包进 GKGuard；它应作为 ROS2/UE Bridge 回路的外部验证目标。
- 保留 legacy `/search/image` mock 接口用于非 C1 演示；真实人脸检索路径是 `/c1/search/person-by-image`。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Demo Script

## Goal

Demonstrate the current GKGuard C2 loop: upload a face image, prefer CampusVision C1 for real keyframes and trajectory, fall back to local mock records if C1 is unavailable, and keep C2 mock workflows for case review, audit, and CampusCar/UE placeholders.

## Primary Visual Flow: Real C1 Search

Recommended packaged-app flow for `v0.1.15`:

1. Download and install `GKGuard-Setup-0.1.15.exe`.
2. Open GKGuard.
3. The app checks the local SSH tunnel first; if it is not connected, enter the server password in the embedded “连接 C1 服务器” window and watch the connection progress.
4. If the page is already open but real search returns C1 503, the page opens the same embedded connection window again and retries once after connection.
5. The password is used only for the current SSH tunnel and is not stored in config or logs.
6. Wait for the app to detect `http://127.0.0.1:18000` and enter the demo page.
7. After a search finishes, click `重新上传` from the result or route screen to return to the upload screen for a new target.
8. For future upgrades, click the top-right `检查更新`; if a newer version is found, click again to download inside the app, then click `重启安装`.

GKGuard does not store, read, or log the SSH password.

Local development flow:

1. Start C1 or connect to the team C1 server through a tunnel.

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

Expected C1 status:

```text
GET http://127.0.0.1:18000/health -> 200 OK, face_engine=insightface
```

1. Start the C2 backend.

```powershell
cd backend
$env:C1_BASE_URL = "http://127.0.0.1:18000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

1. Open the visual demo page.

```text
http://127.0.0.1:8002/demo
```

1. Open API docs for direct endpoint testing if needed.

```text
http://127.0.0.1:8002/docs
```

1. Check the C1 adapter.

```text
GET /c1/status
```

Expected result: `reachable=true`, `healthOk=true`, and C1 health reports `face_engine=insightface`.

1. Run the visual search.

```text
Upload a face or full-frame image -> click 开始检索 -> inspect 人脸检索结果
```

Expected result with C1 connected:

- The result source shows `C1 CampusVision`.
- The upload and result portraits prefer the full user-uploaded image; C1 representative faces are used only when no upload is available.
- The search record list shows C1 keyframe thumbnails instead of the default person placeholder; if a C1 thumbnail fails to load, the UI falls back to the placeholder.
- The record list shows C1 camera IDs and similarity scores.
- The detail panel shows a real keyframe loaded through `/c1/media/frame/...`.
- `查看人物路线图` opens a route view generated from C1 trajectory data.

Expected result without C1, after a C1 failure, or without an uploaded image:

- In desktop mode, failed C1 search first opens the server login window and retries once.
- The UI falls back to local mock records.
- The result source shows `本地模拟`.
- The page remains usable for demonstrating the C2 shell and interactions.

## Legacy Mock API Walkthrough

The following endpoints remain useful for API-level demos that do not depend on C1.

### Search The Demo Person

```text
GET /search/persons?student_id=S2026001
```

Expected result: returns `P001`, the main demo subject.

### Upload An Image To Legacy Mock Search

```text
POST /search/image?top_k=5&min_similarity=0.8
file: p001_target.jpg
```

Expected result: Top-K mock records for `P001`.

### Generate A Person Timeline

```text
GET /persons/P001/timeline?min_similarity=0.9
```

Expected result: sorted appearance records and a summary.

### Review Alert Context

```text
GET /events/ALT-001/related-records
```

Expected result: alert detail, related snapshots, timeline, and summary.

### Create A Mock CampusCar Review Task

```text
POST /car-tasks/mock-dispatch
```

Body:

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "reason": "field review"
}
```

Expected result: `arrived_mock` status and `bridge_contract`.

### Check UE/CampusCar Bridge Placeholder Status

```text
GET /car-tasks/ue-bridge-status
```

Expected result: `/U2RTopic_Command`, `/R2UTopic_Pos`, `/R2UTopic_Text`, and future stream placeholders.

### Generate A Case Report

```text
GET /events/ALT-001/report
```

Expected result: structured report, key findings, recommended actions, and disposition template.

### Archive The Disposition

```text
POST /events/ALT-001/disposition
```

Expected result: a mock archive record with `status_after=closed`.

### Export The Case Package

```text
GET /events/ALT-001/case-package
```

Expected result: `PKG-ALT-001` with event detail, subject data, report, timeline points, evidence snapshots, audit logs, and a handoff checklist.

## Handoff Notes

- The current frontend consumes C1-normalized `records` and `routePoints` for result cards, keyframes, map points, and route lines.
- The control/UE team can later replace the adapter behind `/car-tasks/mock-dispatch` while keeping field names stable.
- Do not package the UE test app into GKGuard; keep it as an external validation target for the ROS2/UE Bridge loop.
- Keep the legacy `/search/image` mock endpoint for non-C1 demos. The real face-search path is `/c1/search/person-by-image`.

<p align="right"><a href="#english">Back to English top</a></p>
