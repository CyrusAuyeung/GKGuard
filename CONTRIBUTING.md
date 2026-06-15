<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 贡献指南

本文档面向所有参与 GKGuard 仓库协作的成员，同时尽量清晰，让不熟悉 GitHub、分支或 Pull Request 的成员也可以按步骤完成标准贡献。

GKGuard 的协作原则是：`main` 保持稳定；非琐碎改动先放在短期分支里；通过 Pull Request、CI 检查和审查后再合并。

## 先看哪些文档

开始前建议先按顺序阅读：

1. [README.md](README.md)：了解项目范围、运行方式、当前版本和发布方式。
2. [docs/README.md](docs/README.md)：了解各类文档放在哪里。
3. [SECURITY.md](SECURITY.md)：了解哪些数据不能提交。
4. [GOVERNANCE.md](GOVERNANCE.md)：了解 `main` 保护、审查、CI、标签和 Project 规则。

如果只是修一个很小的文档问题，读 README、SECURITY 和本文档通常就够了。

## 主要流程

标准协作流程如下：

1. 确认要做什么，必要时先创建 Issue。
2. 从最新 `main` 新建短期分支。
3. 在分支上修改代码或文档。
4. 本地运行必要检查。
5. 推送分支到 GitHub。
6. 创建 Pull Request，并按自动模板填写。
7. 等待 `Verify` CI 通过和审查意见。
8. 根据反馈继续修改同一个分支。
9. 无阻断问题后，由维护者 squash merge 到 `main`。

## 什么时候可以直接改 main

一般不要直接在 `main` 上开发。`main` 是当前稳定基线，应该始终保持可运行、可发布、可回退。

下面这些情况可以由维护者直接提交到 `main`：

- 明显错别字。
- README 或 GitHub Release 正文的小范围同步。
- 不影响功能的低风险文档勘误。
- 紧急小修，并且维护者确认风险很低。

其他情况都应该新建分支并走 Pull Request，例如：

- GKGuard C2 后端、前端或 Electron 桌面端改动。
- GitHub Actions、CI 或发布流程改动。
- CampusVision C1 / GKGuard C2 接入逻辑改动。
- UI 布局、交互、样式改动。
- 新功能。
- 真实数据接入。
- 影响多个文档的规则、流程、版本说明改动。

## 使用 GitHub 模板

仓库已经配置了 Issue 模板、架构与集成 Discussion 模板和 Pull Request 模板。协作者不需要从零设计格式，按模板填写即可。

### Issue 模板怎么选

创建 Issue 时，根据问题类型选择模板：

- `Bug report / 缺陷反馈`：安装包打不开、桌面端启动失败、接口报错、CampusVision C1 连接失败、页面行为异常。
- `Documentation update / 文档更新`：README、API 规范、集成说明、发布说明等内容过时、不清楚或用词错误。
- `Feature request / 功能建议`：新增功能、接口扩展、UI 改进、真实数据接入建议。
- `Release or installer issue / 发布或安装包问题`：GitHub Release 缺少安装包、`.blockmap`、`latest.yml`，版本号不一致，安装包无法启动，发布说明错误。
- `Architecture and integration discussion / 架构与集成讨论`：CampusVision C1 / GKGuard C2 边界、CampusCar/UE 对接方式、模块职责、接口方案等需要先讨论再实现的问题。

填写 Issue 时，按模板要求提供版本号、复现步骤、环境、日志或截图。所有截图和日志必须先脱敏。

如果不确定该选哪个模板，优先选择最接近的问题类型，并在正文里说明不确定的地方。

### Pull Request 模板怎么用

创建 Pull Request 时，GitHub 会自动加载 [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)。不要删除模板结构，按实际情况填写和勾选。

PR 模板主要包含四部分：

- 变更摘要：简要说明这次改了什么，为什么改。
- 影响范围：勾选实际涉及的模块，例如 GKGuard C2 后端、前端、Electron 桌面端、CampusVision C1 服务、CampusCar/UE 占位接口规范、文档、CI 或发布流程。
- 验证：勾选已经运行的检查。如果只改文档，可以勾选“文档-only，代码测试不适用”，但仍建议运行 `git diff --check`。
- 安全与数据检查：确认没有提交真实视频、真实图片、人脸裁剪图、抽帧图、`.env`、密码、token、私钥、真实姓名、学号、手机号、车牌、轨迹或案件材料。

如果某一项不适用，不要假装已经完成。可以在 PR 正文里写明“不适用”的原因。

### 标签和 Project

Issue 或 PR 创建后，应按实际情况设置标签：

- `area: docs`
- `area: frontend`
- `area: backend`
- `area: desktop`
- `area: c1-integration`
- `area: release`
- `type: bug`
- `type: feature`
- `type: task`
- `type: polish`
- `priority: high`
- `priority: medium`
- `priority: low`
- `blocked`
- `needs-info`

同时应加入 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project，用 Backlog、Ready、In progress、Review、Done 跟踪状态。

Project item 需要补齐以下字段，避免 Roadmap 视图无法按时间展示：

- `Status`：按当前阶段设置为 Backlog、Ready、In progress、Review 或 Done。
- `Area`：对应 Backend、Frontend、Desktop、CampusVision C1、Docs 或 Release。
- `Type`：对应 Bug、Feature、Task 或 Polish。
- `Priority`：对应 High、Medium 或 Low。
- `Blocked`：默认 No；如果确实受阻，选择 Yes、Waiting for data、Waiting for server 或 Waiting for review。
- `Start date`：Issue/PR 通常填写开始处理或创建日期；版本阶段项填写阶段开始日期。
- `End date`：Issue/PR 完成后填写合并或关闭日期；版本阶段项填写阶段结束或发布日期。
- `Timeline order`：按真实先后顺序填写递增数字。同一天内按发布时间、PR 创建时间或合并时间排序。
- `Target version`：如果对应明确版本或版本区间，填写 `vX.Y.Z`、`vX.Y.Z-vX.Y.Z` 或 `post-vX.Y.Z`。

目前不把这些字段做成仓库 GitHub Actions 强制自动化。GitHub Projects 支持内置自动化和 GraphQL API，但 GKGuard Roadmap 是用户级 Project，仓库 workflow 稳定写入自定义字段通常需要额外 Project 写权限 token；日期、版本区间和 `Timeline order` 也需要维护者按真实进度确认。维护者或 AI agent 可以用 GitHub UI 或 `gh project item-edit` 半自动补齐，但最终必须核验 Project 字段。

如果没有权限设置标签或 Project，只需要在 Issue 或 PR 中说明缺少哪些字段，维护者会补充。

## 准备本地仓库

如果本地还没有仓库，先下载：

```powershell
git clone https://github.com/CyrusAuyeung/GKGuard.git
cd GKGuard
```

如果已经下载过仓库，每次开始新任务前先更新：

```powershell
git switch main
git pull origin main
```

确认当前在 `main` 且工作区干净：

```powershell
git status
```

如果 `git status` 显示已有未提交改动，先确认这些改动是不是当前任务的一部分。不要把不相关改动混进同一个 Pull Request。

## 新建分支

不要在 `main` 上直接开发。先从最新 `main` 新建分支：

```powershell
git switch main
git pull origin main
git switch -c docs/contributing-guide
```

分支名建议使用英文、短小、能说明目的：

- `docs/contributing-guide`
- `fix/result-image-layout`
- `feature/c1-real-data`
- `release/v0.1.21-prep`
- `codex/ui-polish`

如果是 Codex 协助完成的任务，优先使用 `codex/...` 分支。

## 修改前确认边界

开始写代码或文档前，先确认这次改动属于哪一类：

- GKGuard C2 后端。
- GKGuard C2 前端。
- Electron 桌面端。
- CampusVision C1 服务接入。
- CampusCar / UE 占位接口规范。
- 文档或发布说明。
- GitHub Actions、CI 或发布流程。

如果改动涉及 CampusVision C1、CampusCar、UE、A组机械结构、B组嵌入式控制或 C组算法感知，需要在 PR 里说明边界，避免把“占位接口”写成“真实接入已完成”。

## 敏感数据规则

不要提交以下内容：

- 真实视频。
- 真实人脸图片。
- 真实抽帧图、人脸裁剪图。
- `.env`。
- 数据库。
- 模型缓存。
- 服务器密码。
- SSH 私钥。
- token、API key。
- 真实姓名、学号、手机号、车牌、轨迹或案件材料。

如果不确定一个文件能不能提交，先不要提交，先问维护者。

提交前可以查看将要提交什么：

```powershell
git status
git diff
```

GitHub secret scanning 和 push protection 已启用，但它们不能替代人工检查。不要依赖工具替你发现所有敏感信息。

## 本地开发与检查

后端开发：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

开发环境默认 CampusVision C1 服务隧道地址为：

```text
http://127.0.0.1:18000
```

安装版还内置服务器候选地址：

```text
http://10.4.167.122:8000
```

桌面端开发：

本地桌面开发和打包建议使用 Node.js `22.12.0` 或更高版本；当前 Electron 42 依赖链要求 Node 22+。

```powershell
npm install
npm run desktop
```

桌面端语法检查：

```powershell
node --check desktop/main.js
node --check desktop/preload.js
```

桌面后端入口检查：

```powershell
python -m py_compile backend/desktop_server.py
```

npm 安全检查：

```powershell
npm audit --audit-level=low
```

只修改文档时，至少运行：

```powershell
git diff --check
```

如果没有运行某项检查，需要在 PR 模板的验证部分说明原因。例如：只改 Markdown 文档时，可以说明代码测试不适用。

## 提交改动

先查看状态：

```powershell
git status
```

只添加本次任务相关文件：

```powershell
git add path/to/changed-file
```

不要随手 `git add .`，除非确认当前所有变动都属于本次任务。

提交：

```powershell
git commit -m "Update contributing guide"
```

提交信息建议简短说明做了什么，例如：

- `Fix result image layout`
- `Update collaboration documentation`
- `Add CampusVision C1 connection retry notes`
- `Prepare v0.1.21 release`

## 推送分支

```powershell
git push -u origin docs/contributing-guide
```

推送后，GitHub 通常会显示创建 Pull Request 的入口。

## 创建 Pull Request

打开 GitHub 上的提示链接，创建 Pull Request。

创建时确认：

- base branch 是 `main`。
- compare branch 是你的工作分支。
- PR 标题能说明目的。
- PR 正文保留并填写自动模板。
- 验证结果写清楚。
- 敏感数据检查已完成。

PR 创建后，根据实际情况设置标签并加入 GKGuard Roadmap Project。如果没有权限，通知维护者补充。

## CI 和审查

PR 创建后，GitHub Actions 会自动运行 `Verify` 检查。

`Verify` 通过前不要合并。如果失败，打开失败日志，按报错修复后继续提交到同一个分支：

```powershell
git add path/to/changed-file
git commit -m "Fix CI issue"
git push
```

同一个 PR 会自动更新，不需要重新开 PR。

PR 还需要审查通过。审查中如果有人留言：

- 能改就直接改。
- 不确定就回复说明原因。
- 修改后再次 push。
- 所有对话都解决后再合并。

## 合并规则

仓库使用 squash merge。

这意味着一个 PR 里可以有多个临时提交，但合并进 `main` 时会压缩成一个清晰提交。合并后源分支会删除。

不要强行改写 `main` 历史，不要 force push `main`，不要删除 `main`。

## 合并后更新本地 main

PR 合并后，本地同步最新 `main`：

```powershell
git switch main
git pull origin main
```

如果远端分支已经被删除，本地旧分支也可以删除：

```powershell
git branch -d docs/contributing-guide
```

## 文档同步规则

如果改动影响当前行为，需要同步相关文档。

| 改动类型 | 需要检查的文档 |
|---|---|
| 改 API | `docs/api_contract.md` |
| 改 CampusVision C1 / GKGuard C2 接入 | `docs/c1_c2_integration.md`、`docs/c1_auto_connection.md` |
| 改演示流程 | `docs/demo_script.md` |
| 改字段 | `docs/data_dictionary.md` |
| 改 CampusCar / UE 占位接口 | `docs/campuscar_ue_integration.md` |
| 改发布、安装包或更新行为 | `README.md`、`docs/README.md`、对应 Release note |
| 发新版本 | `package.json`、`package-lock.json`、`docs/releases/vX.Y.Z.md`、README、GitHub Release 正文 |

当前状态文档写最新行为；历史 Release notes 保留发布当时语境，除非是术语错误或明显表述问题。

## 发布相关改动

如果一个 PR 会影响安装包或新版本发布，需要额外确认：

- `package.json` 版本号是否更新。
- `package-lock.json` 是否同步。
- 是否新增或更新 `docs/releases/vX.Y.Z.md`。
- README 是否描述最新版本。
- GitHub Release 正文是否需要同步。
- 发布后是否核对安装包、`.blockmap`、`latest.yml`。

普通协作者不要随意推送 `v*` tag。发布标签由维护者确认后再推。

## 常见问题

### 我不小心在 main 上改了怎么办？

如果还没有提交，可以先新建分支保留当前改动：

```powershell
git switch -c docs/my-change
```

然后继续按分支流程提交。

### 我把不相关文件加入暂存区了怎么办？

取消暂存：

```powershell
git restore --staged path/to/file
```

这不会删除文件内容，只是把它从下一次提交中移除。

### 我提交后发现漏改了怎么办？

继续修改，然后再提交一次：

```powershell
git add path/to/changed-file
git commit -m "Address review feedback"
git push
```

同一个 PR 会自动更新。

### 我发现可能提交了密码或真实数据怎么办？

立刻停止继续 push，并联系维护者。若内容已经推送到 GitHub，按 [SECURITY.md](SECURITY.md) 处理，通常需要删除公开内容、轮换凭据，并评估是否清理历史或 Release 附件。

## PR 前检查清单

提交 Pull Request 前确认：

- 我不是直接在 `main` 上开发。
- 分支已经从最新 `main` 创建或同步。
- 只提交了本次任务相关文件。
- 没有提交真实数据或凭据。
- 已运行与改动相关的测试。
- 文档已经按需同步。
- PR 正文保留并填写了自动模板。
- 如果只改文档，已说明代码测试不适用。
- Issue 或 PR 已按需设置标签并加入 GKGuard Roadmap Project。
- Project item 已补齐 Status、Area、Type、Priority、Blocked、Start date、End date、Timeline order 和必要的 Target version；如果没有权限，已说明需要维护者补充哪些字段。

## 给 AI Agent 的协作提示词

如果使用 Codex、Copilot、ChatGPT 或其他 AI agent 协助修改仓库，可以把下面提示词放进任务说明中：

```text
你正在协助维护 GKGuard 仓库。请严格遵守以下协作规范：

项目与边界：
1. 开始前先阅读 README.md、CONTRIBUTING.md、GOVERNANCE.md、SECURITY.md 和 docs/README.md，确认项目边界、协作流程、敏感数据规则和文档索引。
2. GKGuard C2 是桌面工作台、本地后端、本地代理、UI、发布和文档所在边界；CampusVision C1 是独立的视频检索服务。涉及 CampusVision C1、CampusCar、UE、A组机械结构、B组嵌入式控制或 C组算法感知时，必须明确接口边界，不要把占位接口描述成真实接入已完成。
3. 不要提交真实视频、真实人脸图片、抽帧图、人脸裁剪图、.env、数据库、模型缓存、服务器密码、SSH 私钥、token、API key、真实身份信息、轨迹、车牌或案件材料。不要依赖 secret scanning 代替人工检查。

分支与 PR：
4. 不要直接在 main 上进行非琐碎改动。功能、配置、CI、发布、UI、CampusVision C1 / GKGuard C2 接入、真实数据接入或多文档同步改动，应新建短期分支并通过 Pull Request 合并。
5. main 是稳定基线，受保护规则约束。PR 合并前需要 Verify CI 通过、审查完成、对话解决，并使用 squash merge。
6. 小范围错别字、README 或 GitHub Release 正文同步、紧急低风险修复可以由维护者直接提交 main，但仍需保留清晰提交记录。
7. 创建 PR 时必须保留并填写 .github/PULL_REQUEST_TEMPLATE.md，不要删除模板结构；Issue 应使用仓库已有 Issue 模板，架构与集成类讨论应使用 .github/DISCUSSION_TEMPLATE/architecture-handoff.yml。
8. PR 或 Issue 应按需设置 area:*、type:*、priority:*、blocked、needs-info 标签，并加入 GKGuard Roadmap Project；Project item 必须补齐 Status、Area、Type、Priority、Blocked、Start date、End date、Timeline order 和必要的 Target version。Timeline order 按真实先后顺序递增；同一天内按发布时间、PR 创建时间或合并时间排序。如果没有权限，应在回复中明确提醒维护者补充缺失字段。

实现与验证：
9. 先阅读现有代码和文档，沿用仓库已有模式，不要无关重构，不要把不相关改动混入同一个 PR。
10. 提交前只暂存本次任务相关文件，避免混入无关改动。不要使用破坏性 Git 命令重置用户改动。
11. 根据改动运行必要检查。文档-only 至少运行 git diff --check；代码或桌面相关改动按 PR 模板运行相应测试，并在 PR 中写明验证结果。
12. 如果改动涉及 UI，除静态语法检查外，还应尽可能实际打开页面或桌面端验证布局、图片显示、交互状态和不同窗口尺寸。

文档同步：
13. 如果改动影响当前行为，必须同步相关文档：API 改动同步 docs/api_contract.md；CampusVision C1 / GKGuard C2 接入改动同步 docs/c1_c2_integration.md 或 docs/c1_auto_connection.md；演示流程改动同步 docs/demo_script.md；字段改动同步 docs/data_dictionary.md；CampusCar / UE 占位接口改动同步 docs/campuscar_ue_integration.md；发布或安装包行为改动同步 README.md、docs/README.md 和对应 Release note。
14. 当前状态文档描述最新行为；历史 Release notes 保留发布时语境，除非修复术语错误或明显表述问题。
15. 修改面向仓库用户的 Markdown 时，保持中文在前、English 在后。中文术语优先使用“API 规范”“接口规范”“管理”等仓库当前口径。

发布与收尾：
16. 不要擅自推送 v* tag 或创建 Release。只有在用户明确要求发布，或当前任务就是发布准备并已完成验证时，才进入发布流程。
17. 文档-only、协作流程或模板说明改动通常不需要发布新版本；除非用户明确要求，不要为这类改动创建 Release。
18. 完成后汇报改动内容、验证结果、是否已更新相关文档、是否存在未解决风险，以及 PR/CI/合并状态。
19. 如果用户要求“按标准流程完成”，在确认无阻断问题后应推送分支、创建 PR、等待 CI、合并，并把 Project 状态和 Roadmap 日期/顺序字段推进到合适阶段；如果规则或权限阻塞，应明确说明阻塞点。
```

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Contributing Guide

This document is for all GKGuard repository contributors. It is intentionally explicit so contributors who are less familiar with GitHub, branches, or Pull Requests can still follow the standard workflow.

The core rule is simple: keep `main` stable; make non-trivial changes on a short-lived branch; merge only after Pull Request review and CI checks.

## What To Read First

Recommended reading order:

1. [README.md](README.md): project scope, run modes, current version, and release flow.
2. [docs/README.md](docs/README.md): documentation map.
3. [SECURITY.md](SECURITY.md): sensitive-data rules.
4. [GOVERNANCE.md](GOVERNANCE.md): `main` protection, review, CI, labels, and Project rules.

For a small documentation correction, README, SECURITY, and this guide are usually enough.

## Standard Workflow

1. Confirm the task, and open an Issue first when needed.
2. Create a short-lived branch from the latest `main`.
3. Make code or documentation changes on that branch.
4. Run the relevant local checks.
5. Push the branch to GitHub.
6. Open a Pull Request and fill in the automatic template.
7. Wait for the `Verify` CI check and review feedback.
8. Push follow-up fixes to the same branch.
9. Maintainers squash merge the PR into `main` when there are no blockers.

## When Direct main Changes Are Allowed

Do not normally develop directly on `main`. `main` is the stable baseline and should remain runnable, releasable, and rollback-safe.

Maintainers may commit directly to `main` only for low-risk cases such as:

- Clear typos.
- Small README or GitHub Release body synchronization.
- Low-risk documentation corrections.
- Urgent small fixes confirmed by a maintainer.

Use a branch and Pull Request for everything else, including backend, frontend, Electron, GitHub Actions, CampusVision C1 / GKGuard C2 integration, UI changes, new features, real-data integration, and broad documentation updates.

## GitHub Templates

The repository provides Issue templates, an architecture/integration Discussion template, and a Pull Request template. Contributors should use the templates instead of inventing their own format.

### Issue Templates

Choose the closest template:

- `Bug report / 缺陷反馈`: installer, startup, API, CampusVision C1 connection, or UI behavior problems.
- `Documentation update / 文档更新`: outdated, unclear, or incorrectly worded documentation.
- `Feature request / 功能建议`: new features, API extensions, UI improvements, or real-data integration ideas.
- `Release or installer issue / 发布或安装包问题`: missing Release assets, version mismatch, installer startup problems, or Release note errors.
- `Architecture and integration discussion / 架构与集成讨论`: CampusVision C1 / GKGuard C2 boundaries, CampusCar/UE integration, module ownership, or interface design questions.

Provide the version, reproduction steps, environment, logs, or screenshots requested by the template. Redact all screenshots and logs first.

If you are not sure which template to choose, choose the closest one and explain the uncertainty in the body.

### Pull Request Template

When opening a Pull Request, GitHub loads [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) automatically. Keep the template structure and fill it in.

The template covers:

- Summary: what changed and why.
- Scope: affected modules, such as GKGuard C2 backend, frontend, Electron desktop app, CampusVision C1 service, CampusCar/UE placeholder interface specification, documentation, CI, or release flow.
- Validation: checks you ran. For documentation-only changes, mark code tests as not applicable and run at least `git diff --check`.
- Security and data check: confirm that no real media, credentials, private keys, personal data, trajectories, or case material are committed.

If an item does not apply, say so. Do not mark unfinished checks as completed.

### Labels And Project

Use labels as appropriate:

- `area: docs`
- `area: frontend`
- `area: backend`
- `area: desktop`
- `area: c1-integration`
- `area: release`
- `type: bug`
- `type: feature`
- `type: task`
- `type: polish`
- `priority: high`
- `priority: medium`
- `priority: low`
- `blocked`
- `needs-info`

Issues and Pull Requests should also be tracked in the [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project with Backlog, Ready, In progress, Review, and Done status.

Each Project item should include these fields so the Roadmap view can render and sort the timeline correctly:

- `Status`: Backlog, Ready, In progress, Review, or Done.
- `Area`: Backend, Frontend, Desktop, CampusVision C1, Docs, or Release.
- `Type`: Bug, Feature, Task, or Polish.
- `Priority`: High, Medium, or Low.
- `Blocked`: No by default; use Yes, Waiting for data, Waiting for server, or Waiting for review only when applicable.
- `Start date`: for Issues/PRs, usually the start or creation date; for version-stage items, the stage start date.
- `End date`: for completed Issues/PRs, the merge or close date; for version-stage items, the stage end or release date.
- `Timeline order`: an increasing number that reflects the real chronological order. For items on the same date, use release time, PR creation time, or merge time.
- `Target version`: when there is a clear version or version range, use `vX.Y.Z`, `vX.Y.Z-vX.Y.Z`, or `post-vX.Y.Z`.

These fields are not currently enforced through repository GitHub Actions. GitHub Projects supports built-in automation and GraphQL API updates, but GKGuard Roadmap is a user-level Project; reliably writing custom fields from repository workflows usually requires an extra token with Project write permission. Dates, version ranges, and `Timeline order` also need maintainer confirmation from the real project history. Maintainers or AI agents may use GitHub UI or `gh project item-edit` to fill fields semi-automatically, but the final Project fields must be checked.

If you do not have permission to set labels or Project fields, note which fields are missing in the Issue or PR and a maintainer will do it.

## Prepare Your Local Repository

If the repository is not available locally yet:

```powershell
git clone https://github.com/CyrusAuyeung/GKGuard.git
cd GKGuard
```

Before each new task:

```powershell
git switch main
git pull origin main
git status
```

If `git status` shows existing changes, make sure they belong to the current task before continuing.

## Create A Branch

Do not develop directly on `main`.

```powershell
git switch main
git pull origin main
git switch -c docs/contributing-guide
```

Use short branch names that describe the purpose:

- `docs/contributing-guide`
- `fix/result-image-layout`
- `feature/c1-real-data`
- `release/v0.1.21-prep`
- `codex/ui-polish`

Use `codex/...` branches for Codex-assisted work.

## Check The Scope Before Editing

Identify the affected area before editing:

- GKGuard C2 backend.
- GKGuard C2 frontend.
- Electron desktop app.
- CampusVision C1 service integration.
- CampusCar / UE placeholder interface specification.
- Documentation or Release notes.
- GitHub Actions, CI, or release flow.

If a change touches CampusVision C1, CampusCar, UE, Group A mechanical structure, Group B embedded control, or Group C algorithm perception, explain the boundary in the PR. Do not describe placeholder interfaces as completed real integrations.

## Sensitive Data Rules

Do not commit:

- Real videos.
- Real face images.
- Real extracted frames or face crops.
- `.env` files.
- Databases.
- Model caches.
- Server passwords.
- SSH private keys.
- Tokens or API keys.
- Real names, student or staff IDs, phone numbers, license plates, trajectories, or case material.

When unsure, do not commit the file. Ask a maintainer first.

Before committing, inspect the diff:

```powershell
git status
git diff
```

GitHub secret scanning and push protection are enabled, but they do not replace manual review.

## Local Development And Checks

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

The default development CampusVision C1 service tunnel URL is:

```text
http://127.0.0.1:18000
```

The packaged app also has this built-in server candidate:

```text
http://10.4.167.122:8000
```

Desktop app:

Use Node.js `22.12.0` or later for local desktop development and packaging. The current Electron 42 dependency chain requires Node 22+.

```powershell
npm install
npm run desktop
```

Electron syntax checks:

```powershell
node --check desktop/main.js
node --check desktop/preload.js
```

Desktop backend entrypoint check:

```powershell
python -m py_compile backend/desktop_server.py
```

npm security audit:

```powershell
npm audit --audit-level=low
```

Documentation-only changes:

```powershell
git diff --check
```

If a check was not run, explain why in the Pull Request template.

## Commit Changes

Check status:

```powershell
git status
```

Stage only files related to the current task:

```powershell
git add path/to/changed-file
```

Avoid `git add .` unless every current change belongs to this task.

Commit:

```powershell
git commit -m "Update contributing guide"
```

Good commit messages are short and specific:

- `Fix result image layout`
- `Update collaboration documentation`
- `Add CampusVision C1 connection retry notes`
- `Prepare v0.1.21 release`

## Push The Branch

```powershell
git push -u origin docs/contributing-guide
```

GitHub usually shows a link for creating a Pull Request after the push.

## Open A Pull Request

Confirm:

- Base branch is `main`.
- Compare branch is your work branch.
- The PR title explains the purpose.
- The automatic PR template is kept and filled in.
- Validation results are included.
- Sensitive-data checks are completed.

Then set labels and add the PR to the GKGuard Roadmap Project when you have permission. If not, ask a maintainer to do it.

## CI And Review

The `Verify` GitHub Actions check runs automatically after the PR is opened.

Do not merge before `Verify` passes. If it fails, inspect the log, fix the problem on the same branch, and push again:

```powershell
git add path/to/changed-file
git commit -m "Fix CI issue"
git push
```

The existing PR updates automatically.

Review comments should be addressed in the same PR. Push fixes to the same branch and resolve conversations after the discussion is complete.

## Merge Rules

The repository uses squash merge. A PR may contain multiple temporary commits, but it becomes one clear commit on `main`. The source branch is deleted after merge.

Do not rewrite `main` history, force push `main`, or delete `main`.

## Update Local main After Merge

```powershell
git switch main
git pull origin main
```

Delete the old local branch if it is no longer needed:

```powershell
git branch -d docs/contributing-guide
```

## Documentation Synchronization

If your change affects current behavior, update the related documentation.

| Change Type | Documents To Check |
|---|---|
| API changes | `docs/api_contract.md` |
| CampusVision C1 / GKGuard C2 integration changes | `docs/c1_c2_integration.md`, `docs/c1_auto_connection.md` |
| Demo flow changes | `docs/demo_script.md` |
| Field changes | `docs/data_dictionary.md` |
| CampusCar / UE placeholder interface changes | `docs/campuscar_ue_integration.md` |
| Release, installer, or update behavior changes | `README.md`, `docs/README.md`, matching Release note |
| New release | `package.json`, `package-lock.json`, `docs/releases/vX.Y.Z.md`, README, GitHub Release body |

Current-state documents describe the latest behavior. Historical Release notes keep their release-time context unless fixing terminology or a clear wording problem.

## Release-Related Changes

If a PR affects a release or installer, confirm:

- `package.json` version is updated.
- `package-lock.json` is synchronized.
- `docs/releases/vX.Y.Z.md` is added or updated.
- README describes the latest version.
- GitHub Release body synchronization is planned when needed.
- Installer, `.blockmap`, and `latest.yml` will be checked after release.

Regular contributors should not push `v*` tags without maintainer approval.

## Common Problems

### I accidentally changed files on main

If you have not committed yet, create a branch from the current state:

```powershell
git switch -c docs/my-change
```

Then continue with the branch workflow.

### I staged an unrelated file

```powershell
git restore --staged path/to/file
```

This removes the file from the next commit without deleting its content.

### I need to fix something after committing

```powershell
git add path/to/changed-file
git commit -m "Address review feedback"
git push
```

The same PR updates automatically.

### I may have committed a password or real data

Stop pushing and contact a maintainer. If the content is already on GitHub, follow [SECURITY.md](SECURITY.md): remove public content, rotate affected credentials, and assess whether history or Release assets need cleanup.

## Pre-PR Checklist

Before opening a Pull Request:

- I am not developing directly on `main`.
- My branch is based on the latest `main`.
- Only files related to this task are included.
- No real data or credentials are committed.
- Relevant tests or checks have been run.
- Documentation is synchronized where needed.
- The automatic PR template is kept and filled in.
- Documentation-only changes explain why code tests are not applicable.
- Labels and the GKGuard Roadmap Project item are set where possible.
- The Project item has Status, Area, Type, Priority, Blocked, Start date, End date, Timeline order, and required Target version fields; if I lack permission, I have listed the missing fields for a maintainer.

## Prompt For AI Agents

When using Codex, Copilot, ChatGPT, or another AI agent to help modify the repository, include this prompt in the task:

```text
You are helping maintain the GKGuard repository. Follow these collaboration rules:

Project and boundaries:
1. Read README.md, CONTRIBUTING.md, GOVERNANCE.md, SECURITY.md, and docs/README.md first so you understand the project boundary, collaboration workflow, sensitive-data rules, and documentation map.
2. GKGuard C2 is the desktop workbench, local backend, local proxy, UI, release, and documentation boundary. CampusVision C1 is the separate video-search service. If a change touches CampusVision C1, CampusCar, UE, Group A mechanical structure, Group B embedded control, or Group C algorithm perception, explain the interface boundary clearly. Do not describe placeholder interfaces as completed real integrations.
3. Never commit real videos, real face images, extracted frames, face crops, .env files, databases, model caches, server passwords, SSH private keys, tokens, API keys, real identities, trajectories, license plates, or case material. Do not rely on secret scanning as a substitute for manual review.

Branches and PRs:
4. Do not make non-trivial changes directly on main. Feature, configuration, CI, release, UI, CampusVision C1 / GKGuard C2 integration, real-data integration, or multi-document synchronization changes should use a short-lived branch and Pull Request.
5. main is the stable protected baseline. Before merge, a PR needs the Verify CI check to pass, review completion, resolved conversations, and squash merge.
6. Maintainers may commit small typo fixes, README or GitHub Release body synchronization, and urgent low-risk fixes directly to main, while keeping clear commit history.
7. When opening a PR, keep and fill in .github/PULL_REQUEST_TEMPLATE.md. Do not delete the template structure. Issues should use the repository Issue templates, and architecture/integration discussions should use .github/DISCUSSION_TEMPLATE/architecture-handoff.yml.
8. PRs and Issues should use area:*, type:*, priority:*, blocked, and needs-info labels as needed, and should be added to the GKGuard Roadmap Project. The Project item must include Status, Area, Type, Priority, Blocked, Start date, End date, Timeline order, and required Target version. Timeline order increases by real chronological order; for same-day items, use release time, PR creation time, or merge time. If you lack permission, tell the maintainer exactly which fields need to be added.

Implementation and validation:
9. Read existing code and docs first, follow repository patterns, avoid unrelated refactors, and do not mix unrelated changes into one PR.
10. Stage only files related to the current task. Avoid mixing unrelated changes. Do not use destructive Git commands to reset user work.
11. Run the checks relevant to the change. Documentation-only changes should at least run git diff --check. Code or desktop changes should run the checks listed in the PR template and report validation results in the PR.
12. If a change affects UI, verify the rendered page or desktop app when possible, including layout, image display, interaction states, and different window sizes.

Documentation synchronization:
13. If a change affects current behavior, synchronize related docs: API changes update docs/api_contract.md; CampusVision C1 / GKGuard C2 integration changes update docs/c1_c2_integration.md or docs/c1_auto_connection.md; demo flow changes update docs/demo_script.md; field changes update docs/data_dictionary.md; CampusCar / UE placeholder interface changes update docs/campuscar_ue_integration.md; release or installer behavior changes update README.md, docs/README.md, and the matching Release note.
14. Current-state docs describe the latest behavior. Historical Release notes keep their release-time context unless fixing terminology or a clear wording problem.
15. For repository-facing Markdown, keep Chinese first and English second. Use the repository's current Chinese wording, including API 规范, 接口规范, and 管理.

Release and closeout:
16. Do not push v* tags or create Releases unless the user explicitly requests a release, or the current task is release preparation and validation is complete.
17. Documentation-only, collaboration workflow, or template guidance changes usually do not need a new Release. Do not create a Release for them unless the user explicitly asks.
18. At the end, report what changed, validation results, whether related docs were updated, any remaining risk, and the PR/CI/merge status.
19. If the user asks to complete the standard workflow, push the branch, open a PR, wait for CI, merge when unblocked, and update the Project status plus Roadmap date/order fields. If permissions or rules block that flow, state the exact blocker.
```

<p align="right"><a href="#english">Back to English top</a></p>
