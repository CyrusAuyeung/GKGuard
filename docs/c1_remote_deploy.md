<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusVision C1 远端部署说明

本文记录 GKGuard 仓库内的半自动远端部署流程，用于把已合并到 `main` 的 CampusVision C1 服务更新到团队服务器。该流程只管理源码更新、依赖安装、uvicorn 重启和健康检查；真实视频、人脸图片、数据库、`.env`、SSH 私钥和服务器密码不进入仓库。

## 前提

- Windows 本机已能通过 SSH alias 访问远端服务器：

```powershell
ssh gkguard-c1 "echo ok"
```

- 远端仓库路径为：

```text
/home/speng/projects/GKGuard
```

- CampusVision C1 服务目录为：

```text
/home/speng/projects/GKGuard/services/campusvision-c1
```

- 远端 conda 环境为 `campusvision-c1`，并可加载：

```text
/home/speng/miniforge3/etc/profile.d/conda.sh
```

- 远端服务绑定 `127.0.0.1:8000`，GKGuard C2 通过本地 SSH 隧道 `127.0.0.1:18000` 访问。

## 部署命令

从仓库根目录运行：

```powershell
.\scripts\deploy_c1_remote.ps1
```

常用参数：

```powershell
.\scripts\deploy_c1_remote.ps1 -HostAlias gkguard-c1 -Branch main
.\scripts\deploy_c1_remote.ps1 -SkipInstall
```

脚本会执行：

1. 检查 SSH alias 是否可用。
2. 在远端仓库执行 `git fetch --tags`、`git checkout <Branch>` 和 `git pull --ff-only`。
3. 默认安装 `services/campusvision-c1/requirements.txt`；传入 `-SkipInstall` 时跳过。
4. 停止旧的 `uvicorn app.main:app` 进程。
5. 使用 `nohup` 启动新的 CampusVision C1 服务。
6. 检查 `http://127.0.0.1:8000/health`。
7. 检查 `/openapi.json` 是否包含 `query-faces`。

脚本在 Windows PowerShell 中会先把发送给远端 bash 的脚本内容归一化为 LF，再通过 SSH 标准输入执行，避免 CRLF 换行导致远端 `set -euo pipefail` 解析失败。

## 部署后检查

部署完成后建议继续执行：

```powershell
ssh gkguard-c1 "cd /home/speng/projects/GKGuard/services/campusvision-c1 && source /home/speng/miniforge3/etc/profile.d/conda.sh && conda activate campusvision-c1 && python -m pytest tests"
```

本地如需验证 GKGuard C2 连接 CampusVision C1，先建立隧道：

```powershell
ssh -N -L 18000:127.0.0.1:8000 gkguard-c1
```

然后检查：

```text
http://127.0.0.1:18000/health
http://127.0.0.1:8002/c1/status
```

## 失败处理

- 如果 SSH alias 不可用，先修复 `%USERPROFILE%\.ssh\config` 或直接使用 `-HostAlias speng@10.4.167.122`。
- 如果 `git pull --ff-only` 失败，说明远端仓库有未合并改动或分支分叉，应先在远端查看 `git status`，不要强制覆盖真实运行状态。
- 如果 `/health` 不通，查看远端日志：

```powershell
ssh gkguard-c1 "tail -n 120 /home/speng/projects/GKGuard/services/campusvision-c1/logs/campusvision-c1.log"
```

- 如果查询图人脸检测不稳定，先确认远端已经部署最新 `main`，再检查 `/api/v1/search/query-faces` 返回的 `diagnostics`。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusVision C1 Remote Deployment Guide

This document records the semi-automatic remote deployment flow for updating the CampusVision C1 service on the team server after changes are merged into `main`. The flow only manages source updates, dependency installation, uvicorn restart, and health checks. Real videos, face images, databases, `.env`, SSH private keys, and server passwords must not enter the repository.

## Prerequisites

- The Windows machine can reach the remote server through an SSH alias:

```powershell
ssh gkguard-c1 "echo ok"
```

- Remote repository path:

```text
/home/speng/projects/GKGuard
```

- CampusVision C1 service path:

```text
/home/speng/projects/GKGuard/services/campusvision-c1
```

- Remote conda environment: `campusvision-c1`, loaded through:

```text
/home/speng/miniforge3/etc/profile.d/conda.sh
```

- The remote service binds to `127.0.0.1:8000`, and GKGuard C2 reaches it through the local SSH tunnel `127.0.0.1:18000`.

## Deploy Command

Run from the repository root:

```powershell
.\scripts\deploy_c1_remote.ps1
```

Common parameters:

```powershell
.\scripts\deploy_c1_remote.ps1 -HostAlias gkguard-c1 -Branch main
.\scripts\deploy_c1_remote.ps1 -SkipInstall
```

The script:

1. Checks that the SSH alias works.
2. Runs `git fetch --tags`, `git checkout <Branch>`, and `git pull --ff-only` in the remote repository.
3. Installs `services/campusvision-c1/requirements.txt` by default; `-SkipInstall` skips this step.
4. Stops the old `uvicorn app.main:app` process.
5. Starts the new CampusVision C1 service with `nohup`.
6. Checks `http://127.0.0.1:8000/health`.
7. Checks that `/openapi.json` contains `query-faces`.

In Windows PowerShell, the script normalizes the remote bash script content to LF before writing it to SSH standard input, avoiding remote `set -euo pipefail` parsing failures caused by CRLF line endings.

## Post-Deploy Checks

After deployment, run:

```powershell
ssh gkguard-c1 "cd /home/speng/projects/GKGuard/services/campusvision-c1 && source /home/speng/miniforge3/etc/profile.d/conda.sh && conda activate campusvision-c1 && python -m pytest tests"
```

For local GKGuard C2 verification, create the tunnel first:

```powershell
ssh -N -L 18000:127.0.0.1:8000 gkguard-c1
```

Then check:

```text
http://127.0.0.1:18000/health
http://127.0.0.1:8002/c1/status
```

## Failure Handling

- If the SSH alias is unavailable, fix `%USERPROFILE%\.ssh\config` first or pass `-HostAlias speng@10.4.167.122`.
- If `git pull --ff-only` fails, the remote repository has local changes or branch divergence. Inspect `git status` on the server instead of force-overwriting the running environment.
- If `/health` fails, inspect the remote log:

```powershell
ssh gkguard-c1 "tail -n 120 /home/speng/projects/GKGuard/services/campusvision-c1/logs/campusvision-c1.log"
```

- If query-face detection is unstable, first confirm that the latest `main` is deployed, then inspect the `diagnostics` returned by `/api/v1/search/query-faces`.

<p align="right"><a href="#english">Back to English top</a></p>
