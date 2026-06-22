<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 自动连接说明

这里的 CampusVision C1 指视频检索服务，GKGuard C2 指桌面工作台和本地代理层。GKGuard 可以做到“打开软件后自动连接 CampusVision C1 服务”，但前提是 CampusVision C1 服务本身对这台电脑可达。校园网只是网络前提；真正生效的是 GKGuard C2 后端能访问到某个 CampusVision C1 HTTP 地址。

## 当前实现

GKGuard C2 后端会按顺序读取候选地址并自动探测；安装版默认只内置本机 SSH 隧道地址。校园网直连地址必须通过环境变量或配置文件显式提供：

1. 环境变量 `C1_BASE_URL`。
2. 环境变量 `C1_CANDIDATE_URLS`，多个地址用逗号或分号分隔。
3. 桌面端传入的配置文件：`%APPDATA%\GKGuard\c1-connection.json`。
4. 默认本机隧道地址：`http://127.0.0.1:18000`。

探测时会先用 `C1_ALLOWED_HOSTS` 过滤候选主机，再访问每个候选 CampusVision C1 服务的 `/openapi.json` 和 `/health`。第一个通过允许列表、OpenAPI 身份检查和健康检查的地址会被选中，后续上传照片时会直接转发到这个 CampusVision C1 服务实例。真实检索如果遇到 CampusVision C1 502/503/504，适配器会继续尝试下一个显式候选地址；桌面 UI 也会打开软件内 SSH 密码窗口并重试一次。桌面端 SSH 隧道连接如果被远端重置，主进程会记录警告并关闭对应 socket，不再弹出 Electron 主进程 JavaScript 错误。

## 推荐方案 A：直连 CampusVision C1 服务

这是最适合“自动连上”的方案。

服务器侧需要让 CampusVision C1 监听校园网可访问地址，例如：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

同时需要用防火墙、反向代理或校园网策略限制访问范围，避免把识别服务暴露到不可信网络。CampusVision C1 绑定到 `0.0.0.0` 或 `::` 时会要求 API key；服务器配置 `CAMPUSVISION_API_KEY` 或 `C1_API_KEY` 后，GKGuard C2 侧也要配置同一密钥，并通过 `X-CampusVision-API-Key` 转发。

客户端配置文件：

```json
{
  "candidateUrls": [
    "http://10.4.167.122:8000",
    "http://127.0.0.1:18000"
  ]
}
```

安装版默认读取：

```text
%APPDATA%\GKGuard\c1-connection.json
```

如果确认 CampusVision C1 服务已经安全开放给校园网，可以把直连地址放在候选列表第一位。默认安装版仍优先本机 SSH 隧道，避免“直连健康但搜索返回 503”时静默回退。

直连地址还需要加入 GKGuard C2 允许列表，例如：

```powershell
$env:C1_ALLOWED_HOSTS = "127.0.0.1,localhost,10.4.167.122"
```

## 推荐方案 B：自动识别已有 SSH 隧道

如果 CampusVision C1 仍绑定在服务器本机 `127.0.0.1:8000`，客户端需要先建立隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

隧道建立后，GKGuard 会自动识别默认地址：

```text
http://127.0.0.1:18000
```

这种方案安全，但不是打开软件后自动建隧道；SSH 密码或密钥由用户在系统 SSH 中处理。不要把服务器密码写进软件或配置文件。

## 默认方案 C：打开应用后输入 SSH 密码

当前桌面端默认支持这个模式：应用启动时会优先检查本机 SSH 隧道；如果尚未通过隧道连接 CampusVision C1 服务，会在软件内弹出“连接 CampusVision C1 服务”窗口。窗口会显示服务器账号、隧道目标、连接原因、四步连接进度和密码安全说明。你在该窗口输入服务器密码后，GKGuard 会用本次密码建立内嵌 SSH 隧道，不会保存、记录或写入密码；如果连接失败，窗口会停留在当前界面并允许重新输入。若进入页面后真实检索返回 CampusVision C1 503，页面也会触发同一个内嵌连接窗口并自动重试一次。

默认内置参数：

```text
host = 10.4.167.122
user = speng
localPort = 18000
remoteHost = 127.0.0.1
remotePort = 8000
```

使用内置 SSH 隧道时，GKGuard 会在发送服务器密码前自动比对 SSH 主机密钥固定指纹。如果服务器地址或 SSH 主机密钥变化，必须在可信网络或服务器控制台运行以下命令获取新的 OpenSSH `SHA256:...` 指纹，并写入 `sshTunnel.hostFingerprint`：

```bash
ssh-keygen -l -E sha256 -f /etc/ssh/ssh_host_ed25519_key.pub
```

如果没有配置 `hostFingerprint`，或服务器返回的指纹与固定值不一致，软件会阻断连接并停留在密码窗口，不再允许通过人工确认未知指纹继续发送密码。下面的配置文件用于固定指纹，或在服务器地址、账号、端口变化时覆盖默认值。

配置文件示例：

```json
{
  "candidateUrls": [
    "http://127.0.0.1:18000"
  ],
  "sshTunnel": {
    "enabled": true,
    "host": "10.4.167.122",
    "user": "speng",
    "localPort": 18000,
    "remoteHost": "127.0.0.1",
    "remotePort": 8000,
    "hostFingerprint": "SHA256:<trusted-c1-host-key-fingerprint>"
  }
}
```

可选覆盖路径：

```text
%APPDATA%\GKGuard\c1-connection.json
```

启动后的行为：

1. GKGuard 先探测 `candidateUrls`。
2. 如果本机隧道未连接，弹出“连接 CampusVision C1 服务”提示；即使直连地址可达，也会优先提示建立隧道。
3. 软件内弹出“连接 CampusVision C1 服务”窗口，展示服务器账号、隧道目标和连接原因。
4. 你在该窗口输入服务器密码；主进程会先校验 CampusVision C1 SSH 主机密钥，校验通过后才用本次密码建立 SSH 隧道，并显示“输入密码、建立 SSH、打开隧道、验证服务”四步进度。
5. 如果连接失败，窗口会提示失败原因并允许重新输入密码；如果成功，桌面端直接探测 `http://127.0.0.1:18000/openapi.json` 和 `/health`。
6. 只要 CampusVision C1 端点可达，就进入可检索状态，避免后端状态缓存未及时刷新造成误提示。

安装版进入演示页前会清理 Electron renderer cache，并加载带 `asset=v0.1.36-ui` 参数的 `/demo` 页面。这样安装更新后，桌面端不会继续复用旧的 HTML/CSS/JS 造成布局或功能看起来没有变化。

这个方案满足“打开应用后输入服务器密码”，同时避免把服务器密码写进配置或仓库。

## 可选方案 D：手动或免密 SSH 隧道

如果需要排障，仍可以手动在终端中建立隧道；如果后续改用 SSH key，也可以在系统侧配置免密连接：

```powershell
ssh -N -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

完全无感的免密方案只建议在配置好 SSH key 后使用。原因：

- 不应把服务器密码打包进客户端。
- 需要处理端口占用、隧道断线重连、退出清理和错误提示。

## 上传照片时会发生什么

如果任一候选 CampusVision C1 服务可达：

1. GKGuard C2 前端把照片发给本机 GKGuard C2 后端。
2. GKGuard C2 自动选择健康的 CampusVision C1 地址。
3. GKGuard C2 先调用 CampusVision C1 查询图人脸检测；一张有效候选人脸会自动选中，多张有效候选人脸由前端打开放大原图弹窗选择目标；低于 `0.65` 但不低于 `0.45` 的候选会以低置信样式显示并仍可选择，低于 `0.45` 的候选不作为可选目标。
4. GKGuard C2 把照片和可选 `query_face_index` 转发给 CampusVision C1 `person-by-image`。
5. CampusVision C1 返回候选人物、关键帧、目标人脸框、相似度、摄像头、时间和轨迹。
6. 前端显示 `CampusVision C1` 的真实结果。

如果所有候选 CampusVision C1 服务都不可达：

1. GKGuard C2 前端仍能上传照片到本机 GKGuard C2 后端。
2. GKGuard C2 的 `/c1/...` 请求会返回不可用错误。
3. 桌面 UI 会打开软件内 CampusVision C1 密码窗口；用户输入 SSH 密码后自动重试一次。
4. 如果没有上传图片，前端可回退到本地模拟数据，继续展示演示结果。
5. 如果已经上传图片但查询图人脸检测、真实检索仍不可用、CampusVision C1 返回空 `records[]` 无匹配结果，或请求超时，前端停留在上传页提示重试，不展示模拟结果，也不保持“检索中”状态。
6. 回退结果不是服务器真实数据。

## 检查方式

打开：

```text
http://127.0.0.1:8000/c1/status
```

或开发端口：

```text
http://127.0.0.1:8002/c1/status
```

重点看：

- `selectedBaseUrl`：当前自动选中的 CampusVision C1 地址。
- `candidateUrls`：当前候选地址列表。
- `candidates[].identityOk`：候选地址是否通过 CampusVision C1 OpenAPI 身份检查。
- `candidates[].healthOk`：各候选 CampusVision C1 服务的健康检查结果。
- `health.face_engine`：应为 `insightface`。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 Auto-Connection Guide

Here, CampusVision C1 means the video-search service, and GKGuard C2 means the desktop workbench plus local proxy layer. GKGuard can auto-connect to the CampusVision C1 service after the desktop app opens, but only if that service is reachable from this computer. Campus network access is only the network prerequisite; the actual requirement is that the GKGuard C2 backend can reach a CampusVision C1 HTTP URL.

## Current Implementation

The GKGuard C2 backend reads and probes candidate URLs in this order; the packaged app only includes the local SSH tunnel by default. Campus-network direct URLs must be provided explicitly through environment variables or the config file:

1. Environment variable `C1_BASE_URL`.
2. Environment variable `C1_CANDIDATE_URLS`, separated by commas or semicolons.
3. Desktop-provided config file: `%APPDATA%\GKGuard\c1-connection.json`.
4. Default local tunnel URL: `http://127.0.0.1:18000`.

During probing, GKGuard C2 first filters candidate hosts with `C1_ALLOWED_HOSTS`, then calls `/openapi.json` and `/health` on each CampusVision C1 candidate. The first candidate that passes the allowlist, OpenAPI identity check, and health check is selected, and image uploads are forwarded to that CampusVision C1 instance. If real search hits CampusVision C1 502/503/504, the adapter tries the next explicitly configured candidate URL; the desktop UI also opens the embedded SSH password prompt and retries once. If the remote side resets an SSH tunnel connection, the desktop main process records a warning and closes the socket instead of showing an Electron main-process JavaScript error dialog.

## Recommended Option A: Direct CampusVision C1 Access

This is the best option for true auto-connect.

On the server, CampusVision C1 should listen on an address reachable from campus network, for example:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use firewall rules, reverse proxy rules, or campus network policy to restrict access. Do not expose the recognition service to untrusted networks. When CampusVision C1 binds to `0.0.0.0` or `::`, it requires an API key; after setting `CAMPUSVISION_API_KEY` or `C1_API_KEY` on the server, configure the same key on GKGuard C2 so it can forward `X-CampusVision-API-Key`.

Client config file:

```json
{
  "candidateUrls": [
    "http://10.4.167.122:8000",
    "http://127.0.0.1:18000"
  ]
}
```

The packaged desktop app reads this path by default:

```text
%APPDATA%\GKGuard\c1-connection.json
```

If CampusVision C1 is safely exposed to the campus network, put the direct URL first in this candidate list. The default packaged app still prefers the local SSH tunnel to avoid silently falling back when direct access is healthy but real search returns 503.

The direct host must also be included in the GKGuard C2 allowlist, for example:

```powershell
$env:C1_ALLOWED_HOSTS = "127.0.0.1,localhost,10.4.167.122"
```

## Recommended Option B: Auto-Detect SSH Tunnel

If CampusVision C1 still binds to the server's local `127.0.0.1:8000`, create a tunnel first:

```powershell
ssh -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

After the tunnel is up, GKGuard automatically detects the default URL:

```text
http://127.0.0.1:18000
```

This is secure but not fully automatic, because the SSH password or key still belongs to the user. Do not store the server password in the app.

## Default Option C: Enter SSH Password After Opening The App

The desktop app supports this mode by default: at startup it checks the local SSH tunnel first. If the tunnel is not connected, the app shows an embedded “Connect CampusVision C1 service” password window with progress. After you type the server password, GKGuard uses it for the current SSH tunnel only; it does not store, log, or write the password. If real search returns CampusVision C1 503 after the page opens, the UI triggers the same embedded connection window and retries once.

Built-in defaults:

```text
host = 10.4.167.122
user = speng
localPort = 18000
remoteHost = 127.0.0.1
remotePort = 8000
```

Before sending the server password, GKGuard automatically compares the pinned SSH host-key fingerprint. If the server address or SSH host key changes, obtain the new OpenSSH `SHA256:...` fingerprint from a trusted network or the server console and store it in `sshTunnel.hostFingerprint`:

```bash
ssh-keygen -l -E sha256 -f /etc/ssh/ssh_host_ed25519_key.pub
```

If `hostFingerprint` is not configured, or if the server returns a different fingerprint, the app blocks the connection and stays in the password window. It no longer allows manual approval of an unknown fingerprint before sending the password. The config below is for pinning that fingerprint or overriding defaults when the server address, account, or ports change.

Example config:

```json
{
  "candidateUrls": [
    "http://127.0.0.1:18000"
  ],
  "sshTunnel": {
    "enabled": true,
    "host": "10.4.167.122",
    "user": "speng",
    "localPort": 18000,
    "remoteHost": "127.0.0.1",
    "remotePort": 8000,
    "hostFingerprint": "SHA256:<trusted-c1-host-key-fingerprint>"
  }
}
```

Optional override path:

```text
%APPDATA%\GKGuard\c1-connection.json
```

Startup behavior:

1. GKGuard probes `candidateUrls` first.
2. If the local tunnel is not connected, it shows a “Connect CampusVision C1 service” prompt; even when the direct URL is reachable, the app prefers establishing the tunnel.
3. The app opens the embedded “Connect CampusVision C1 service” window.
4. You type the server password in that window; the main process verifies the CampusVision C1 SSH host key before using the one-time password to create the SSH tunnel.
5. Once the tunnel is up, the desktop app probes `http://127.0.0.1:18000/openapi.json` and `/health` directly; as soon as the CampusVision C1 endpoint is reachable, it enters the searchable state and avoids false warnings caused by stale backend status selection.

Before entering the demo page, the packaged app clears the Electron renderer cache and loads `/demo` with `asset=v0.1.36-ui`. This prevents installed updates from reusing stale HTML/CSS/JS and making the UI appear unchanged after an upgrade.

This gives an “enter server password after opening the app” flow without writing the server password to config files or the repository.

## Optional Option D: Manual Or Passwordless SSH Tunnel

For troubleshooting, you can still create the tunnel manually in a terminal. If you later move to SSH keys, configure passwordless login at the system level:

```powershell
ssh -N -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

Only use a fully silent passwordless flow after SSH keys are configured. Reasons:

- Server passwords should not be bundled into the client.
- The app must handle port conflicts, tunnel reconnects, shutdown cleanup, and clear error messages.

## What Happens When A Photo Is Uploaded

If any candidate CampusVision C1 service is reachable:

1. The GKGuard C2 frontend sends the photo to the local GKGuard C2 backend.
2. GKGuard C2 selects a healthy CampusVision C1 URL automatically.
3. GKGuard C2 first calls CampusVision C1 query-face detection; one effective candidate face is auto-selected, while multiple effective candidates are selected in an enlarged original-image modal. Candidates below `0.65` but at least `0.45` stay visible with a low-confidence style and remain selectable, while candidates below `0.45` are not exposed as targets.
4. GKGuard C2 forwards the image and optional `query_face_index` to CampusVision C1 `person-by-image`.
5. CampusVision C1 returns candidate persons, keyframes, target-face boxes, similarity, camera, time, and route points.
6. The frontend shows real `CampusVision C1` results.

If all candidate CampusVision C1 URLs are unavailable:

1. The GKGuard C2 frontend still uploads the photo to the local GKGuard C2 backend.
2. GKGuard C2 `/c1/...` requests return unavailable errors.
3. The desktop UI opens the embedded CampusVision C1 password prompt; after the user enters the SSH password, it retries once automatically.
4. If no image has been uploaded, the frontend can fall back to local mock data and continue the demo.
5. If an image has been uploaded but query-face detection, real search, an empty `records[]` no-match result, or a request timeout prevents a real hit, the frontend stays on the upload screen with a retry/error message instead of showing mock results or staying in a loading state.
6. The fallback result is not real server data.

## How To Check

Open:

```text
http://127.0.0.1:8000/c1/status
```

or the development port:

```text
http://127.0.0.1:8002/c1/status
```

Check these fields:

- `selectedBaseUrl`: currently selected CampusVision C1 URL.
- `candidateUrls`: current candidate URL list.
- `candidates[].identityOk`: whether the candidate passed the CampusVision C1 OpenAPI identity check.
- `candidates[].healthOk`: health-check result for each candidate.
- `health.face_engine`: should be `insightface`.

<p align="right"><a href="#english">Back to English top</a></p>
