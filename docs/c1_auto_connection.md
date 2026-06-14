<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# C1 自动连接说明

GKGuard 可以做到“打开软件后自动连接 C1”，但前提是 C1 服务本身对这台电脑可达。校园网只是网络前提；真正生效的是 C2 后端能访问到某个 C1 HTTP 地址。

## 当前实现

C2 会按顺序读取候选地址并自动探测：

1. 环境变量 `C1_BASE_URL`。
2. 环境变量 `C1_CANDIDATE_URLS`，多个地址用逗号或分号分隔。
3. 桌面端传入的配置文件：`%APPDATA%\GKGuard\c1-connection.json`。
4. 默认本机隧道地址：`http://127.0.0.1:18000`。

探测时会访问每个候选 C1 的 `/openapi.json` 和 `/health`。第一个健康检查通过的地址会被选中，后续上传照片时会直接转发到这个 C1。

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

这样在校园网内打开软件时，C2 会先尝试直连 `10.4.167.122:8000`。如果服务器未开放直连，再回退到本机 SSH 隧道。

## 推荐方案 B：自动识别 SSH 隧道

如果 C1 仍绑定在服务器本机 `127.0.0.1:8000`，客户端需要先建立隧道：

```powershell
ssh -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

隧道建立后，GKGuard 会自动识别默认地址：

```text
http://127.0.0.1:18000
```

这种方案安全，但不算完全自动，因为 SSH 密码或密钥仍需要用户处理。不要把服务器密码写进软件。

## 可选方案 C：打开应用后输入 SSH 密码

当前桌面端支持这个模式：如果 C1 不可达，并且配置文件启用了 `sshTunnel`，应用启动时会弹出提示，选择后会打开一个 PowerShell SSH 窗口。你在该窗口输入服务器密码，GKGuard 不会保存或记录密码。

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

保存路径：

```text
%APPDATA%\GKGuard\c1-connection.json
```

启动后的行为：

1. GKGuard 先探测 `candidateUrls`。
2. 如果都不可达，弹出“连接 C1 服务器”提示。
3. 选择“输入密码连接 C1”后，打开 PowerShell 并执行 SSH 隧道命令。
4. 你在 PowerShell 中输入服务器密码。
5. 隧道建立后，C2 自动检测 `http://127.0.0.1:18000` 并用于真实检索。

这个方案接近“打开应用后输入服务器密码”，同时避免 GKGuard 直接接触密码。

## 可选方案 D：软件自动拉起免密 SSH 隧道

可以继续扩展 Electron，在启动时执行：

```powershell
ssh -N -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

这种完全无感方案只建议在配置好免密 SSH key 后使用。原因：

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
3. 当前前端会回退到本地 mock fallback，继续展示演示结果。
4. 结果不是服务器真实数据。

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

C2 reads and probes candidate URLs in this order:

1. Environment variable `C1_BASE_URL`.
2. Environment variable `C1_CANDIDATE_URLS`, separated by commas or semicolons.
3. Desktop-provided config file: `%APPDATA%\GKGuard\c1-connection.json`.
4. Default local tunnel URL: `http://127.0.0.1:18000`.

During probing, C2 calls `/openapi.json` and `/health` on each candidate. The first candidate with a healthy response is selected, and image uploads are forwarded to that C1 instance.

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

With this setup, GKGuard first tries `10.4.167.122:8000` on campus network. If direct access is unavailable, it falls back to the local SSH tunnel.

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

## Optional Option C: Enter SSH Password After Opening The App

The desktop app now supports this mode: if C1 is unavailable and `sshTunnel` is enabled in the config file, the app shows a prompt at startup. If confirmed, it opens a PowerShell SSH window. You type the server password in that window; GKGuard does not store or log the password.

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

Save it at:

```text
%APPDATA%\GKGuard\c1-connection.json
```

Startup behavior:

1. GKGuard probes `candidateUrls` first.
2. If all candidates are unavailable, it shows a “Connect C1 server” prompt.
3. Choosing the connection option opens PowerShell and runs the SSH tunnel command.
4. You type the server password in PowerShell.
5. Once the tunnel is up, C2 detects `http://127.0.0.1:18000` and uses it for real search.

This gives an “enter server password after opening the app” flow without letting GKGuard handle the password directly.

## Optional Option D: App-Started Passwordless SSH Tunnel

Electron can be extended to run this at startup:

```powershell
ssh -N -L 18000:127.0.0.1:8000 speng@10.4.167.122
```

Only use this after passwordless SSH keys are configured. Reasons:

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
3. The current frontend falls back to local mock data and continues the demo.
4. The result is not real server data.

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
