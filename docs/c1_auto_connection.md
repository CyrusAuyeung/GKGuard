<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# C1 自动连接说明

GKGuard 可以做到“打开软件后自动连接 C1”，但前提是 C1 服务本身对这台电脑可达。校园网只是网络前提；真正生效的是 C2 后端能访问到某个 C1 HTTP 地址。

## 当前实现

后端会按顺序读取候选地址并自动探测；安装版默认优先本机 SSH 隧道，其次再尝试校园网直连地址：

1. 环境变量 `C1_BASE_URL`。
2. 环境变量 `C1_CANDIDATE_URLS`，多个地址用逗号或分号分隔。
3. 桌面端传入的配置文件：`%APPDATA%\GKGuard\c1-connection.json`。
4. 默认本机隧道地址：`http://127.0.0.1:18000`。
5. 内置服务器地址：`http://10.4.167.122:8000`。

探测时会访问每个候选 C1 的 `/openapi.json` 和 `/health`。第一个健康检查通过的地址会被选中，后续上传照片时会直接转发到这个 C1。真实检索如果遇到 C1 502/503/504，适配器会继续尝试下一个候选地址；桌面 UI 也会打开软件内 SSH 密码窗口并重试一次。

## 推荐方案 A：直连 C1 服务

这是最适合“自动连上”的方案。

服务器侧需要让 C1 监听校园网可访问地址，例如：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

同时需要用防火墙、反向代理或校园网策略限制访问范围，避免把识别服务暴露到不可信网络。

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

如果确认 C1 服务已经安全开放给校园网，可以把直连地址放在候选列表第一位。默认安装版仍优先本机 SSH 隧道，避免“直连健康但搜索返回 503”时静默回退。

## 推荐方案 B：自动识别已有 SSH 隧道

如果 C1 仍绑定在服务器本机 `127.0.0.1:8000`，客户端需要先建立隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

隧道建立后，GKGuard 会自动识别默认地址：

```text
http://127.0.0.1:18000
```

这种方案安全，但不是打开软件后自动建隧道；SSH 密码或密钥由用户在系统 SSH 中处理。不要把服务器密码写进软件或配置文件。

## 默认方案 C：打开应用后输入 SSH 密码

当前桌面端默认支持这个模式：应用启动时会优先检查本机 SSH 隧道；如果尚未通过隧道连接 C1，会在软件内弹出“连接 C1 服务器”密码窗口和连接进度条。你在该窗口输入服务器密码后，GKGuard 会用本次密码建立内嵌 SSH 隧道，不会保存、记录或写入密码。若进入页面后真实检索返回 C1 503，页面也会触发同一个内嵌连接窗口并自动重试一次。

默认内置参数：

```text
host = 10.4.167.122
user = speng
localPort = 18000
remoteHost = 127.0.0.1
remotePort = 8000
```

因此通常不需要手动创建配置文件。下面的配置文件只用于服务器地址、账号或端口变化时覆盖默认值。

配置文件示例：

```json
{
  "candidateUrls": [
    "http://10.4.167.122:8000",
    "http://127.0.0.1:18000"
  ],
  "sshTunnel": {
    "enabled": true,
    "host": "10.4.167.122",
    "user": "speng",
    "localPort": 18000,
    "remoteHost": "127.0.0.1",
    "remotePort": 8000
  }
}
```

可选覆盖路径：

```text
%APPDATA%\GKGuard\c1-connection.json
```

启动后的行为：

1. GKGuard 先探测 `candidateUrls`。
2. 如果本机隧道未连接，弹出“连接 C1 服务器”提示；即使直连地址可达，也会优先提示建立隧道。
3. 软件内弹出“连接 C1 服务器”窗口。
4. 你在该窗口输入服务器密码，主进程用本次密码建立 SSH 隧道。
5. 隧道建立后，桌面端直接探测 `http://127.0.0.1:18000/openapi.json` 和 `/health`；只要 C1 端点可达，就进入可检索状态，避免后端状态缓存未及时刷新造成误提示。

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

如果任一候选 C1 可达：

1. 前端把照片发给本机 C2 后端。
2. C2 自动选择健康的 C1 地址。
3. C2 把照片转发给 C1 `person-by-image`。
4. C1 返回候选人物、关键帧、相似度、摄像头、时间和轨迹。
5. 前端显示 `C1 CampusVision` 的真实结果。

如果所有候选 C1 都不可达：

1. 前端仍能上传照片到本机 C2。
2. C2 的 `/c1/...` 请求会返回不可用错误。
3. 桌面 UI 会打开软件内 C1 密码窗口；用户输入 SSH 密码后自动重试一次。
4. 如果仍不可用，前端才会回退到本地 mock fallback，继续展示演示结果。
5. 回退结果不是服务器真实数据。

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

- `selectedBaseUrl`：当前自动选中的 C1 地址。
- `candidateUrls`：当前候选地址列表。
- `candidates[].healthOk`：各候选 C1 的健康检查结果。
- `health.face_engine`：应为 `insightface`。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# C1 Auto-Connection Guide

GKGuard can auto-connect to C1 after the desktop app opens, but only if the C1 service is reachable from this computer. Campus network access is only the network prerequisite; the actual requirement is that the C2 backend can reach a C1 HTTP URL.

## Current Implementation

The backend reads and probes candidate URLs in this order; the packaged app prefers the local SSH tunnel before the campus-network direct URL:

1. Environment variable `C1_BASE_URL`.
2. Environment variable `C1_CANDIDATE_URLS`, separated by commas or semicolons.
3. Desktop-provided config file: `%APPDATA%\GKGuard\c1-connection.json`.
4. Default local tunnel URL: `http://127.0.0.1:18000`.
5. Built-in server URL: `http://10.4.167.122:8000`.

During probing, C2 calls `/openapi.json` and `/health` on each candidate. The first candidate with a healthy response is selected, and image uploads are forwarded to that C1 instance. If real search hits C1 502/503/504, the adapter tries the next candidate URL; the desktop UI also opens the embedded SSH password prompt and retries once.

## Recommended Option A: Direct C1 Access

This is the best option for true auto-connect.

On the server, C1 should listen on an address reachable from campus network, for example:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use firewall rules, reverse proxy rules, or campus network policy to restrict access. Do not expose the recognition service to untrusted networks.

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

If C1 is safely exposed to the campus network, put the direct URL first in this candidate list. The default packaged app still prefers the local SSH tunnel to avoid silently falling back when direct access is healthy but real search returns 503.

## Recommended Option B: Auto-Detect SSH Tunnel

If C1 still binds to the server's local `127.0.0.1:8000`, create a tunnel first:

```powershell
ssh -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

After the tunnel is up, GKGuard automatically detects the default URL:

```text
http://127.0.0.1:18000
```

This is secure but not fully automatic, because the SSH password or key still belongs to the user. Do not store the server password in the app.

## Default Option C: Enter SSH Password After Opening The App

The desktop app supports this mode by default: at startup it checks the local SSH tunnel first. If the tunnel is not connected, the app shows an embedded “Connect C1 server” password window with progress. After you type the server password, GKGuard uses it for the current SSH tunnel only; it does not store, log, or write the password. If real search returns C1 503 after the page opens, the UI triggers the same embedded connection window and retries once.

Built-in defaults:

```text
host = 10.4.167.122
user = speng
localPort = 18000
remoteHost = 127.0.0.1
remotePort = 8000
```

So normally you do not need to create a config file manually. The config below is only for overriding defaults when the server address, account, or ports change.

Example config:

```json
{
  "candidateUrls": [
    "http://10.4.167.122:8000",
    "http://127.0.0.1:18000"
  ],
  "sshTunnel": {
    "enabled": true,
    "host": "10.4.167.122",
    "user": "speng",
    "localPort": 18000,
    "remoteHost": "127.0.0.1",
    "remotePort": 8000
  }
}
```

Optional override path:

```text
%APPDATA%\GKGuard\c1-connection.json
```

Startup behavior:

1. GKGuard probes `candidateUrls` first.
2. If the local tunnel is not connected, it shows a “Connect C1 server” prompt; even when the direct URL is reachable, the app prefers establishing the tunnel.
3. The app opens the embedded “Connect C1 server” window.
4. You type the server password in that window, and the main process creates the SSH tunnel with that one-time password.
5. Once the tunnel is up, the desktop app probes `http://127.0.0.1:18000/openapi.json` and `/health` directly; as soon as the C1 endpoint is reachable, it enters the searchable state and avoids false warnings caused by stale backend status selection.

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

If any candidate C1 is reachable:

1. The frontend sends the photo to the local C2 backend.
2. C2 selects a healthy C1 URL automatically.
3. C2 forwards the image to C1 `person-by-image`.
4. C1 returns candidate persons, keyframes, similarity, camera, time, and route points.
5. The frontend shows real `C1 CampusVision` results.

If all candidate C1 URLs are unavailable:

1. The frontend still uploads the photo to local C2.
2. C2 `/c1/...` requests return unavailable errors.
3. The desktop UI opens the embedded C1 password prompt; after the user enters the SSH password, it retries once automatically.
4. If C1 is still unavailable, the frontend falls back to local mock data and continues the demo.
5. The fallback result is not real server data.

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

- `selectedBaseUrl`: currently selected C1 URL.
- `candidateUrls`: current candidate URL list.
- `candidates[].healthOk`: health-check result for each candidate.
- `health.face_engine`: should be `insightface`.

<p align="right"><a href="#english">Back to English top</a></p>
