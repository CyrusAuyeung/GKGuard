<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 项目管理

GKGuard 当前是项目演示仓库，管理目标是保持 GKGuard C2 工作台边界清晰、发布可复现、文档可维护、敏感数据不进入仓库。

## 角色与职责

- 项目整体：围绕 GKGuard 港科广校园安防 AI 智能分析检索平台展示闭环组织，按 A组机械结构、B组嵌入式控制、C组算法感知分工维护。
- A组：机械结构，负责 campusCar 安保感知上装、设备安装支架、线缆保护、状态灯/提示屏和结构安全测试。
- B组：嵌入式控制，负责 campusCar 与 GKGuard 平台之间的控制与状态接口、低速巡逻、任务开始/结束、到点反馈、位置回传、异常停止、人工接管和移动抓拍触发。
- C组：算法感知，负责 GKGuard 平台 AI 智能分析检索与系统闭环，包括 GKGuard C2 工作台、CampusVision C1 服务接入、多源数据、检索 API、图片线索检索、时间线、地图点位、风险标签、事件摘要、处置闭环和仓库文档。
- 文档维护：随对应模块维护，README、API 规范、数据字典、演示脚本、接口说明和发布说明由 C组牵头同步。

## 决策原则

1. 先保护敏感数据，再追求演示便利。
2. GKGuard C2 前端只访问 GKGuard C2 后端；跨服务访问通过 GKGuard C2 适配器或明确的接口规范完成。
3. 真实 CampusVision C1 服务、campusCar、UE 能力必须能离线降级或有清晰失败提示。
4. 发布前必须有可追溯版本号、发布说明、测试结果和安装包文件。
5. 历史发布说明保留发布时的语境；当前状态文档同步最新版本。
6. 每次发布后再次核对 README 和所有当前状态文档，确保版本号、功能边界、验证结果和安装包说明一致。

## 仓库协作规则

- `Protect main` 规则集保护默认分支 `main`，用于保持当前稳定基线可运行、可发布、可回退。
- 常规功能、配置、发布和文档协作改动应从 `codex/...` 或其他短期分支提交 Pull Request。
- Pull Request 合并前需要至少一次审查通过；新的提交会使旧审查失效，最后一次推送后仍需审查确认，并且所有对话必须解决。
- 必需状态检查为 `.github/workflows/ci.yml` 中的 `Verify`；该检查覆盖后端测试、前端脚本语法检查、Electron 语法检查、桌面后端入口编译、浏览器 E2E 回归和 npm 安全审计。
- `main` 禁止删除和强制推送；仓库合并策略使用 squash merge，并在合并后删除源分支。
- Issue 和 Pull Request 使用 `area:*`、`type:*`、`priority:*`、`blocked`、`needs-info` 标签归类，并放入 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project 跟踪 Backlog、Ready、In progress、Review、Done 状态。
- GKGuard Roadmap item 应补齐 `Status`、`Area`、`Type`、`Priority`、`Blocked`、`Start date`、`End date`、`Timeline order` 和必要的 `Target version`；日期字段用于 Roadmap 展示，`Timeline order` 用于同日内按真实先后排序。
- Project item 以 GKGuard Roadmap 视图或 Project 主列表可见为准；PR/Issue 页面显示关联但 Roadmap 不显示时，应重新查询并修复。
- Milestone 暂不强制使用；CODEOWNERS 暂不启用，后续明确发布节奏或审查归属后再补充。

## 合并与发布

- 普通协作变更通过 PR 进入 `main`，并由 `.github/workflows/ci.yml` 执行基础检查。
- 维护者可直接处理低风险文档勘误、Release 正文同步和紧急小修，但仍需保留可追溯提交记录。
- 影响安装包的变更需要更新版本号和 `docs/releases/vX.Y.Z.md`。
- 影响当前行为或仓库边界的变更需要同步 README、`docs/README.md`、API/集成/演示/支持/安全等相关文档。
- `v*` 版本标签会触发 `.github/workflows/release-desktop.yml` 构建 Windows 安装包。
- 发布后检查 GitHub Release 正文、`.exe`、`.blockmap` 和 `latest.yml`。

## 敏感数据管理

任何真实媒体、凭据、数据库、日志或个人信息一旦进入仓库，应立即：

1. 删除公开内容或撤下附件。
2. 轮换受影响凭据。
3. 评估是否需要清理 Git 历史或发布文件。
4. 按 [SECURITY.md](SECURITY.md) 记录和处理。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Project Management

GKGuard is currently a project demo repository. Management focuses on keeping the GKGuard C2 workbench boundary clear, Releases reproducible, documentation maintainable, and sensitive data out of the repository.

## Roles And Responsibilities

- Overall project: organized around the GKGuard campus-security AI search platform demo loop, with ownership split across Group A mechanical structure, Group B embedded control, and Group C algorithm perception.
- Group A, mechanical structure: owns the campusCar security-sensing upper structure, equipment mounts, cable protection, status light/display mounting, and structure safety checks.
- Group B, embedded control: owns the control and status interface between campusCar and GKGuard, low-speed patrol, task start/end, arrival feedback, position reporting, emergency/exception stop, manual takeover, and mobile capture triggers.
- Group C, algorithm perception: owns the GKGuard AI search platform and system loop, including the GKGuard C2 workbench, CampusVision C1 integration, multi-source data, search APIs, image clue search, timelines, map points, risk tags, event summaries, disposition loop, and repository documentation.
- Documentation ownership follows module ownership; Group C leads synchronization for README, API specification, data dictionary, demo script, interface notes, and Release notes.

## Decision Principles

1. Protect sensitive data before optimizing demo convenience.
2. The GKGuard C2 frontend calls only the GKGuard C2 backend; cross-service access goes through a GKGuard C2 adapter or explicit API specification.
3. Real CampusVision C1 service, CampusCar, and UE capabilities must degrade offline or provide a clear failure message.
4. A Release requires traceable version, Release notes, validation results, and installer files.
5. Historical Release notes keep their historical context; current-state documents track the latest version.
6. After every release, re-check README and all current-state docs so version numbers, capability boundaries, validation results, and installer instructions stay consistent.

## Repository Collaboration Rules

- The `Protect main` ruleset protects the default branch `main` so the current stable baseline remains runnable, releasable, and rollback-safe.
- Normal feature, configuration, release, and documentation collaboration changes should open a Pull Request from `codex/...` or another short-lived branch.
- Pull Requests require at least one approval before merge. New commits dismiss stale approvals, the last push still needs review confirmation, and all conversations must be resolved.
- The required status check is `Verify` from `.github/workflows/ci.yml`; it covers backend tests, frontend script syntax checks, Electron syntax checks, desktop backend entrypoint compilation, browser E2E regression, and npm security audit.
- Deleting or force-pushing `main` is blocked. The repository merge policy uses squash merge and deletes merged head branches.
- Issues and Pull Requests use `area:*`, `type:*`, `priority:*`, `blocked`, and `needs-info` labels, and are tracked in the [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project through Backlog, Ready, In progress, Review, and Done.
- GKGuard Roadmap items should include `Status`, `Area`, `Type`, `Priority`, `Blocked`, `Start date`, `End date`, `Timeline order`, and required `Target version`; date fields power the Roadmap view, and `Timeline order` preserves the real order for same-day items.
- A Project item is considered complete only when it is visible in the GKGuard Roadmap view or Project main item list; if the PR/Issue page shows an association but Roadmap does not, query again and fix the item.
- Milestones are not mandatory yet. CODEOWNERS is not enabled yet and should be added only after the release cadence or review ownership is clearer.

## Merge And Release

- Normal collaborative changes enter `main` through PRs, with `.github/workflows/ci.yml` running the baseline checks.
- Maintainers may commit low-risk documentation corrections, Release-body synchronization, and urgent small fixes directly, while keeping traceable commits.
- Installer-impacting changes must update the version and `docs/releases/vX.Y.Z.md`.
- Changes that affect current behavior or repository boundaries must also update README, `docs/README.md`, and relevant API/integration/demo/support/security docs.
- Tags matching `v*` trigger `.github/workflows/release-desktop.yml` to build the Windows installer.
- After publishing, check the Release body, `.exe`, `.blockmap`, and `latest.yml`.

## Sensitive Data Management

If real media, credentials, databases, logs, or personal information enter the repository:

1. Remove public content or take down attachments.
2. Rotate affected credentials.
3. Evaluate whether Git history or Release files need cleanup.
4. Record and handle the incident through [SECURITY.md](SECURITY.md).

<p align="right"><a href="#english">Back to English top</a></p>
