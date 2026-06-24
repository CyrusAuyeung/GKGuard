<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 演示脚本

## 目标

演示当前 GKGuard C2 工作台闭环：未上传图片时可用本地模拟记录展示三屏流程；上传人脸图片后，GKGuard C2 前端只访问 GKGuard C2 后端，GKGuard C2 后端调用 CampusVision C1 服务获取真实关键帧和轨迹；若查询图人脸检测或真实检索失败，界面停留在上传页提示重试，不展示伪成功结果；同时保留案件研判、审计、CampusCar/UE 占位等 GKGuard C2 模拟工作流。

## 主视觉流程：CampusVision C1 真实检索

安装版 `v0.2.2` 推荐流程：

1. 从 GitHub Release 下载当前系统对应的桌面端安装文件：Windows 使用 `GKGuard-Setup-0.2.2.exe`，macOS 使用 `GKGuard-macOS-*.dmg` 或 `GKGuard-macOS-*.zip`，Linux 使用 `GKGuard-Linux-*.AppImage` 或 `GKGuard-Linux-*.deb`。macOS 当前为未签名/未公证的内部测试包。
2. 打开 GKGuard。
3. 软件会优先检查本机 SSH 隧道；如果尚未连接，在软件内“连接 CampusVision C1 服务”窗口确认服务器账号和隧道目标，输入服务器密码，并观察四步连接进度。若连接失败，可在同一窗口重新输入。
4. 如果已经进入页面但真实检索返回 CampusVision C1 503，页面会再次打开同一个内嵌连接窗口并在连接后自动重试一次。
5. 密码只用于本次 SSH 隧道连接，不会保存到配置或日志。
6. 等待软件检测到 `http://127.0.0.1:18000` 后进入演示页。
7. 上传查询图片。若图片只有一张有效候选人脸，GKGuard C2 会自动选中并直接检索；若图片有多张有效候选人脸，上传页会在原图上显示人脸框和检测置信度，并自动打开放大选择弹窗，需要确认目标人脸后再检索；低于 `0.65` 但不低于 `0.45` 的候选应以低置信样式显示并仍可选择。
8. 搜索完成后，在结果页检查目标人物照片为选中的查询人脸，且在方框内完整显示并充分利用可见空间；详情关键帧和关键帧预览弹窗应在目标人脸位置显示框，相似度应显示在框外且不遮挡人脸，目标框不应出现在图片左上角或黑边区域。连续点击左侧检索记录时，右侧详情区应保留当前关键帧并显示轻量加载提示，目标记录关键帧加载完成后再替换，不应出现整块黑屏。
9. 若 CampusVision C1 返回无匹配结果、请求超时或检索失败，页面应停留在上传页并显示中文提示，不应卡在“检索中”，也不应进入本地模拟结果。
10. 搜索完成后可在结果页或路线页点击 `重新上传`，返回上传页开始下一次检索。
11. 后续需要升级时，点击右上角 `检查更新`。Windows 版发现新版后再次点击会在应用内下载，完成后点击 `重启安装`；macOS/Linux 版会打开当前平台的 GitHub Release 安装文件。重启后页面应加载带版本参数的新 `/demo` 页面，不应继续显示旧布局。
12. 在最大化窗口、常规桌面窗口、约 `820px` 中等宽度、`680x640` 小窗口和 `390x720` 移动端视口下检查页面无横向滚动，上传图、结果缩略图、目标人脸框和关键帧不被裁切；中等宽度结果页的人物照片不应遮挡数据来源和命中记录信息；桌面结果页记录列表应位于左侧，移动端结果页和路线页记录列表显示横向滑动提示，移动端路线页能在地图前看到当前轨迹摘要。

GKGuard 不保存、不读取、不记录 SSH 密码。

## 人物特征检索流程

当前版本包含的 CampusVision C1 人物特征检索不需要上传查询图，适合演示“按条件查事件”的入口；该入口由 `v0.2.0` 引入，并在 `v0.2.1` 修正路线顺序、路线点到结果记录的稳定映射、重复索引、受影响人物索引与 appearance session 重建和 API 规范示例。`v0.2.2` 继续补齐 review 后续，确保查询图候选接口参数位置、CampusVision C1 4xx 校验错误透传、5xx 服务错误详情脱敏、输入校验失败不触发桌面端重连和路线点唯一高亮行为与 API 规范一致。

1. 在搜索页切换到 `人物特征检索`。
2. 选择上装颜色、眼镜状态、外观倾向、摄像头、时间范围、最低匹配分和返回数量；条件可以留空，留空表示不限制。
3. 点击 `开始检索`。GKGuard C2 会调用 `/c1/query/person-attributes`，后端再代理到 CampusVision C1 的 `/api/v1/query/person-attributes`。
4. 结果页标题会切换为 `人物特征检索结果`，记录列表优先展示事件人体图，其次回退事件关键帧或人脸图。
5. 详情区显示事件关键帧、人体图或人脸图，并在 `相关信息` 中展示上装颜色、眼镜状态、外观倾向、匹配类型、未满足条件和条件评分。
6. `exact` 表示已填写条件全部满足；`partial` 表示相似但部分条件不满足，应结合未满足条件人工判断；`unknown` 表示模型无法判断，不等同于否定结果。
7. 若 CampusVision C1 返回空结果，页面应停留在搜索页并提示未匹配事件，不应进入本地模拟结果。

本地开发流程：

1. 启动 CampusVision C1 服务，或连接团队 CampusVision C1 服务所在服务器隧道。

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

期望 CampusVision C1 状态：

```text
GET http://127.0.0.1:18000/health -> 200 OK, face_engine=insightface
```

1. 启动 GKGuard C2 后端。

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

1. 检查 GKGuard C2 内的 CampusVision C1 适配器。

```text
GET /c1/status
```

期望结果：`reachable=true`、`healthOk=true`，且 CampusVision C1 health 显示 `face_engine=insightface`。

1. 执行视觉检索。

```text
上传人脸或完整帧图片 -> 单人自动检索或多人框选目标 -> 查看 人脸检索结果
```

CampusVision C1 已连接时期望结果：

- 结果页数据来源显示 `CampusVision C1`。
- 上传页会先检测查询图人脸；单人图会自动检索，多人图会在原图上显示人脸框和检测置信度，用户选择后只检索目标人脸。
- 结果页人物照片优先显示选中的查询人脸裁切图；裁切图会从选中框向外扩边，空间允许时调整为方形裁切，并在靠近图像边缘时向内平移，最终在人物照片方框内完整显示并充分利用空间；无法裁切时才回退 CampusVision C1 代表人脸或完整上传图。
- 检索记录列表优先展示 CampusVision C1 人脸裁剪缩略图，而不是默认人物占位图；若 CampusVision C1 缩略图加载失败，才回退占位图。
- 最大化窗口会使用更多可用宽度，约 `820px` 中等宽度下人物照片与数据来源信息不重叠，小窗口下仍不出现横向溢出。
- 记录列表显示 CampusVision C1 摄像头和相似度。
- 详情区显示通过 `/c1/media/frame/...` 加载的真实关键帧。
- 详情关键帧和关键帧预览弹窗会在目标人脸位置显示框和相似度。
- 连续切换检索记录时，详情区保留当前关键帧，预加载目标记录关键帧，加载完成后再替换；慢媒体响应期间不应短暂黑屏。
- 点击 `查看人物路线图` 后，路线图使用 CampusVision C1 trajectory 数据生成轨迹点、地图上方摘要、时间线和轨迹摘要。
- 检索、查询图人脸检测、定位、导出和更新入口会显示统一状态提示，按处理中、完成、注意和失败区分反馈。

CampusVision C1 未连接、接口失败或未上传图片时期望结果：

- 桌面模式下，CampusVision C1 检索失败会先打开软件内服务器密码窗口并重试一次。
- 未上传图片时，UI 回退到本地模拟记录；已上传图片但查询图人脸检测或真实检索失败时，UI 停留在上传页并提示重试。
- 只有未上传图片时，结果页数据来源才显示 `本地模拟`；已上传图片但检测或检索失败时不会进入模拟结果页。
- 页面仍可用于演示 GKGuard C2 工作台和交互流程。

## 旧版模拟 API 演示

以下接口仍可用于不依赖 CampusVision C1 的 API 级演示。

### 搜索演示人员

```text
GET /search/persons?student_id=S2026001
```

期望结果：返回 `P001` 这个主演示对象。

### 上传图片到旧版模拟搜索

```text
POST /search/image?top_k=5&min_similarity=0.8
file: p001_target.jpg
```

期望结果：返回 `P001` 的 Top-K 模拟记录。

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

### 查看 UE/CampusCar 桥接占位状态

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

期望结果：服务端配置 `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN` 且请求带 `X-GKGuard-Export-Token` 时返回 `PKG-ALT-001`，包含事件详情、对象信息、报告、时间线点、证据快照、审计日志和处理清单。未配置或未携带 token 时应返回结构化错误。

### 读取审计日志

```text
GET /audit/logs
X-GKGuard-Audit-Token: <configured-token>
```

期望结果：服务端配置 `GKGUARD_AUDIT_TOKEN` 且请求带 `X-GKGuard-Audit-Token` 时返回脱敏审计日志；未携带 token 时返回 403。审计日志文件应按长度和字节上限自动压缩保留。

## 维护备注

- 当前前端使用 CampusVision C1 归一化后的 `records` 和 `routePoints` 生成结果卡片、关键帧、地图点和路线；人物特征检索路线点按时间排序时，应通过 `recordIndex` / `eventId` 点击回对应结果记录。
- B组嵌入式控制后续可替换 `/car-tasks/mock-dispatch` 背后的适配器，字段名保持稳定。
- 不要把 UE 测试应用打包进 GKGuard；它应作为 ROS2/UE Bridge 回路的外部验证目标。
- 保留旧版 `/search/image` 模拟接口用于非 CampusVision C1 演示；真实人脸检索路径是 `/c1/search/person-by-image`。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Demo Script

## Goal

Demonstrate the current GKGuard C2 workbench loop: use local mock records for the three-screen flow when no image is uploaded; after uploading a face image, let the GKGuard C2 frontend call only the GKGuard C2 backend and let the GKGuard C2 backend call CampusVision C1 for real keyframes and trajectory. If query-face detection or real search fails, the UI stays on the upload screen with a retry/error message instead of showing false successful results. GKGuard C2 mock workflows for case review, audit, and CampusCar/UE placeholders remain available.

## Primary Visual Flow: Real CampusVision C1 Search

Recommended packaged-app flow for `v0.2.2`:

1. Download the desktop package for the current system from GitHub Releases: `GKGuard-Setup-0.2.2.exe` on Windows, `GKGuard-macOS-*.dmg` or `GKGuard-macOS-*.zip` on macOS, and `GKGuard-Linux-*.AppImage` or `GKGuard-Linux-*.deb` on Linux. The current macOS package is an unsigned and unnotarized internal test build.
2. Open GKGuard.
3. The app checks the local SSH tunnel first; if it is not connected, confirm the server account and tunnel target in the embedded “连接 CampusVision C1 服务” window, enter the server password, and watch the four-step connection progress. If connection fails, re-enter the password in the same window.
4. If the page is already open but real search returns CampusVision C1 503, the page opens the same embedded connection window again and retries once after connection.
5. The password is used only for the current SSH tunnel and is not stored in config or logs.
6. Wait for the app to detect `http://127.0.0.1:18000` and enter the demo page.
7. Upload the query image. If it contains one effective candidate face, GKGuard C2 auto-selects it and searches directly; if it contains multiple effective candidates, the upload screen overlays face boxes and detection confidence on the original image and opens an enlarged selection modal before search. Candidates below `0.65` but at least `0.45` should remain visible with a low-confidence style and remain selectable.
8. After the search finishes, confirm that the result portrait uses the selected query face, fully fits inside the portrait frame, and uses the available frame space well; the detail keyframe and keyframe preview dialog should show a target-face box, the similarity score should sit outside the box without covering the face, and the target box should not appear in the image top-left corner or letterbox area. When clicking result records in the left list repeatedly, the right detail area should keep the current keyframe visible with a lightweight loading hint, then replace it only after the target keyframe finishes loading. It should not flash into a full black panel.
9. If CampusVision C1 returns no matched records, times out, or fails during search, the UI should stay on the upload screen with a Chinese warning; it should not stay in `检索中` or enter local mock results.
10. After a search finishes, click `重新上传` from the result or route screen to return to the upload screen for a new target.
11. For future upgrades, click the top-right `检查更新`. On Windows, if a newer version is found, click again to download inside the app, then click `重启安装`. On macOS/Linux, the app opens the current platform's GitHub Release package. After restart, the page should load the versioned `/demo` page and should not keep the old layout.
12. Check maximized, regular desktop, roughly `820px` medium-width, `680x640` small-window, and `390x720` mobile layouts for no horizontal scrolling and uncropped uploaded images, result thumbnails, target-face boxes, and keyframes. In medium-width result layouts, the target portrait must not cover the source and hit-count summary. The desktop result record list should stay on the left side, mobile result and route record lists should show horizontal-scroll hints, and the mobile route page should show the current-trajectory summary before the map.

GKGuard does not store, read, or log the SSH password.

Local development flow:

1. Start the CampusVision C1 service or connect to the team CampusVision C1 server through a tunnel.

```powershell
ssh -L 18000:127.0.0.1:8000 <user>@<c1-server>
```

Expected CampusVision C1 status:

```text
GET http://127.0.0.1:18000/health -> 200 OK, face_engine=insightface
```

1. Start the GKGuard C2 backend.

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

1. Check the CampusVision C1 adapter inside GKGuard C2.

```text
GET /c1/status
```

Expected result: `reachable=true`, `healthOk=true`, and CampusVision C1 health reports `face_engine=insightface`.

1. Run the visual search.

```text
Upload a face or full-frame image -> auto-search one face or select a target from multiple boxed faces -> inspect 人脸检索结果
```

Expected result with CampusVision C1 connected:

- The result source shows `CampusVision C1`.
- The upload screen detects faces in the query image; single-face uploads search automatically, while multi-face uploads show face boxes and detection confidence on the original image so the user can search only the selected target face.
- The result portrait shows the selected query face; the crop is padded from the selected box, made square when source-image space allows, shifted inward near image edges, and rendered fully inside the portrait frame while using the available space. If cropping is unavailable, the UI falls back to the full upload or the CampusVision C1 representative face.
- The search record list prefers CampusVision C1 face-crop thumbnails instead of the default person placeholder; if a CampusVision C1 thumbnail fails to load, the UI falls back to the placeholder.
- Maximized windows use more available width, roughly `820px` medium-width layouts keep the target portrait separate from source information, and small windows avoid horizontal overflow.
- The record list shows CampusVision C1 camera IDs and similarity scores.
- The detail panel shows a real keyframe loaded through `/c1/media/frame/...`.
- The detail keyframe and keyframe preview dialog show the target-face box with similarity.
- When switching result records repeatedly, the detail panel keeps the current keyframe visible, preloads the target record keyframe, and replaces it after loading finishes; slow media responses should not create a brief black panel.
- `查看人物路线图` opens a route view generated from CampusVision C1 trajectory data, with a top route overview, timeline, and summary.
- Search, query-face detection, navigation, export, and update actions use unified status feedback for loading, success, warning, and failure states.

Expected result without CampusVision C1, after a CampusVision C1 failure, or without an uploaded image:

- In desktop mode, failed CampusVision C1 search first opens the server login window and retries once.
- The UI falls back to local mock records only when no image has been uploaded; uploaded-image detection or real-search failures keep the UI on the upload screen with a retry/error message.
- The result source shows `本地模拟` only when no image has been uploaded; uploaded-image detection or search failures do not enter the mock result screen.
- The page remains usable for demonstrating the GKGuard C2 workbench and interactions.

## Person-Attribute Search Flow

The current CampusVision C1 person-attribute search does not require a query image and is suitable for demonstrating event lookup by conditions. This entry was introduced in `v0.2.0`, and `v0.2.1` corrected route ordering, stable route-to-record mapping, duplicate indexing, affected person-index and appearance-session rebuilds, and API specification examples. `v0.2.2` completes the review follow-up by keeping query-image candidate parameter placement, CampusVision C1 4xx validation propagation, 5xx service-error detail sanitization, input-validation failures without desktop reconnection, and single active route-point highlighting aligned with the API specification.

1. Switch to `人物特征检索` on the search screen.
2. Select upper color, glasses status, appearance presentation, camera, time range, minimum match score, and result limit. Any condition can be left empty to mean unrestricted.
3. Click `开始检索`. GKGuard C2 calls `/c1/query/person-attributes`, and the backend proxies it to CampusVision C1 `/api/v1/query/person-attributes`.
4. The result title changes to `人物特征检索结果`. The record list prefers event body crops, then falls back to event keyframes or face crops.
5. The detail panel shows the event keyframe, body crop, or face crop, and `相关信息` shows upper color, glasses status, appearance presentation, match type, failed conditions, and condition scores.
6. `exact` means all filled conditions match. `partial` means the event is similar but some conditions failed and needs human judgment. `unknown` means the model cannot determine the attribute, not that the attribute is false.
7. If CampusVision C1 returns no results, the UI should stay on the search screen with a no-event warning instead of entering local mock results.

## Legacy Mock API Walkthrough

The following endpoints remain useful for API-level demos that do not depend on CampusVision C1.

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

Expected result: when the server sets `GKGUARD_CASE_PACKAGE_EXPORT_TOKEN` and the request includes `X-GKGuard-Export-Token`, returns `PKG-ALT-001` with event detail, subject data, report, timeline points, evidence snapshots, audit logs, and an action checklist. Missing server-side or request token should return a structured error.

### Read Audit Logs

```text
GET /audit/logs
X-GKGuard-Audit-Token: <configured-token>
```

Expected result: when the server sets `GKGUARD_AUDIT_TOKEN` and the request includes `X-GKGuard-Audit-Token`, returns redacted audit logs; missing request token returns 403. The audit log file should be compacted automatically by length and byte limits.

## Maintenance Notes

- The current frontend consumes CampusVision C1-normalized `records` and `routePoints` for result cards, keyframes, map points, and route lines. When person-attribute route points are time-sorted, `recordIndex` / `eventId` should click back to the matching result record.
- Group B embedded control can later replace the adapter behind `/car-tasks/mock-dispatch` while keeping field names stable.
- Do not package the UE test app into GKGuard; keep it as an external validation target for the ROS2/UE Bridge loop.
- Keep the legacy `/search/image` mock endpoint for non-CampusVision C1 demos. The real face-search path is `/c1/search/person-by-image`.

<p align="right"><a href="#english">Back to English top</a></p>
