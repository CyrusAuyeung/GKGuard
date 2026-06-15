<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 贡献指南

感谢参与 GKGuard。当前仓库以 GKGuard C2 桌面工作台、CampusVision C1 服务接入、演示文档和接口说明为主，请保持改动小而清晰，并优先保护敏感数据。

## 开始之前

1. 阅读 [README.md](README.md)、[OPEN_SOURCE.md](OPEN_SOURCE.md) 和 [SECURITY.md](SECURITY.md)。
2. 确认改动属于当前 GKGuard C2 边界，或在文档中明确说明与 CampusVision C1 服务、campusCar、UE、A组机械结构、B组嵌入式控制或 C组算法感知的接口边界。
3. 不要提交真实视频、真实图片、`.env`、数据库、模型缓存、密码、token 或私钥。
4. 如果改动会影响发布，请同步更新 README、相关当前状态文档，以及 `docs/releases/` 中对应版本说明。

## 分支与 Pull Request 流程

- 非琐碎改动使用短期分支，例如 `codex/fix-actions-runtime`、`codex/c1-real-data`、`codex/ui-polish`；`main` 保持为可运行、可发布、可回退的稳定基线。
- 小范围文档勘误、GitHub Release 正文同步或紧急低风险修复可由维护者直接提交到 `main`，但应保留清晰提交记录。
- Pull Request 标题和正文应写清目的、范围、验证结果、敏感数据检查，以及是否影响 CampusVision C1 服务、GKGuard C2 工作台、CampusCar/UE、发布流程或安装包。
- `main` 受 `Protect main` 规则集保护；合并前需要 `Verify` 检查通过、完成审查、解决所有对话，并使用 squash merge。
- Issue 和 Pull Request 应按需设置 `area:*`、`type:*`、`priority:*`、`blocked`、`needs-info` 标签，并放入 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project 跟踪。
- Milestone 暂不强制使用；CODEOWNERS 暂不启用，后续明确审查归属后再补充。

## 本地开发

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

桌面端：

本地桌面开发和打包建议使用 Node.js `22.12.0` 或更高版本；当前 Electron 42 依赖链要求 Node 22+。

```powershell
npm install
npm run desktop
```

开发环境默认 CampusVision C1 服务隧道地址为：

```text
http://127.0.0.1:18000
```

安装版还内置服务器候选地址：

```text
http://10.4.167.122:8000
```

## 文档规范

- 面向仓库用户的 Markdown 默认使用中文在前、English 在后。
- 顶部保留中文/English 跳转按钮。
- 当前状态文档应写最新版本和当前行为；历史发布说明保留发布时的语境。
- 每次发布新版本后，必须核对 README、`docs/README.md`、API 规范、CampusVision C1 / GKGuard C2 集成说明、演示脚本、安全/支持/管理文档和发布说明是否仍一致。
- 涉及真实 CampusVision C1 服务、SSH、校园网或服务器访问时，明确说明网络前提和密码不进入 GKGuard。

## Pull Request 要求

PR 应包含：

- 变更目的和影响范围。
- 测试或验证结果。
- 是否影响 CampusVision C1 服务、GKGuard C2 工作台、CampusCar/UE、发布流程或安装包。
- 是否涉及敏感数据、凭据或真实媒体。

在合并前请确认：

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check desktop/main.js
node --check desktop/preload.js
npm audit --audit-level=low
```

Pull Request 会自动运行 `.github/workflows/ci.yml`。本地验证结果仍应写进 PR，方便审查者判断风险和复现方式。

如只改文档，可以说明未运行代码测试的原因。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Contributing Guide

Thank you for contributing to GKGuard. This repository currently focuses on the GKGuard C2 desktop workbench, CampusVision C1 service integration, demo documentation, and interface notes. Keep changes small and clear, and protect sensitive data first.

## Before You Start

1. Read [README.md](README.md), [OPEN_SOURCE.md](OPEN_SOURCE.md), and [SECURITY.md](SECURITY.md).
2. Confirm the change belongs to the current GKGuard C2 boundary, or document its boundary with the CampusVision C1 service, campusCar, UE, Group A mechanical structure, Group B embedded control, or Group C algorithm perception.
3. Do not commit real videos, real images, `.env` files, databases, model caches, passwords, tokens, or private keys.
4. If the change affects a Release, update README, relevant current-state docs, and the matching note under `docs/releases/`.

## Branch And Pull Request Flow

- Use short-lived branches for non-trivial changes, for example `codex/fix-actions-runtime`, `codex/c1-real-data`, or `codex/ui-polish`; keep `main` as the runnable, releasable, rollback-safe baseline.
- Maintainers may commit small documentation corrections, GitHub Release body synchronization, or urgent low-risk fixes directly to `main`, while keeping clear commit history.
- Pull Request titles and bodies should state purpose, scope, validation results, sensitive-data checks, and whether the change affects the CampusVision C1 service, GKGuard C2 workbench, CampusCar/UE, release flow, or installer.
- `main` is protected by the `Protect main` ruleset; before merge, the `Verify` check must pass, review must be complete, all conversations must be resolved, and squash merge is used.
- Issues and Pull Requests should use `area:*`, `type:*`, `priority:*`, `blocked`, and `needs-info` labels as needed, and should be tracked in the [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project.
- Milestones are not mandatory yet. CODEOWNERS is not enabled yet and should be added only after review ownership is clearer.

## Local Development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

Desktop app:

Use Node.js `22.12.0` or later for local desktop development and packaging. The current Electron 42 dependency chain requires Node 22+.

```powershell
npm install
npm run desktop
```

The default development CampusVision C1 service tunnel URL is:

```text
http://127.0.0.1:18000
```

The packaged app also has this built-in server candidate:

```text
http://10.4.167.122:8000
```

## Documentation Rules

- User-facing Markdown should be Chinese first and English second.
- Keep the Chinese/English jump buttons at the top.
- Current-state documents should describe the latest version and behavior; historical Release notes should keep their historical context.
- After every new release, verify that README, `docs/README.md`, API specification, CampusVision C1 / GKGuard C2 integration notes, demo script, security/support/management docs, and Release notes remain consistent.
- When documenting the real CampusVision C1 service, SSH, campus network, or server access, state the network prerequisite and that passwords do not enter GKGuard.

## Pull Request Requirements

A PR should include:

- Purpose and scope.
- Test or validation results.
- Whether it affects the CampusVision C1 service, GKGuard C2 workbench, CampusCar/UE, Release, or the installer.
- Whether it touches sensitive data, credentials, or real media.

Before merge, confirm:

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check desktop/main.js
node --check desktop/preload.js
npm audit --audit-level=low
```

Pull requests automatically run `.github/workflows/ci.yml`. Still include local validation results in the PR so reviewers can assess risk and reproduce checks.

For documentation-only changes, state why code tests were not run.

<p align="right"><a href="#english">Back to English top</a></p>
