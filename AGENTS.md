<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# AGENTS.md

本文档是 GKGuard 仓库的 AI agent 开发规范。Codex、Copilot、ChatGPT 或其他自动化开发助手在修改本仓库前必须先阅读本文件，并把这里的规则作为仓库级约束。

## 项目定位

- GKGuard C2 是校园安防 AI 搜索工作台，负责本地 FastAPI 后端、静态前端、Electron 桌面端、本地模拟回退、CampusVision C1 代理、结果展示、路线可视化、发布工程和文档体系。
- CampusVision C1 是独立视频检索服务，负责视频上传、抽帧、人脸向量、人物库、以图搜人、关键帧和轨迹输出。GKGuard C2 通过 `/c1/...` 代理访问它。
- CampusCar、ROS2、UE Bridge 目前只保留占位接口规范。不要把占位接口写成已经接入真实车辆、真实 ROS2 节点或真实 UE 运行时。
- A组负责机械结构，B组负责嵌入式控制，C组负责算法感知。文档中需要提到分组时使用这些明确名称，不要使用数字编号等含混表述。

## 必读文件

开始任务前至少阅读：

- `README.md`
- `CONTRIBUTING.md`
- `GOVERNANCE.md`
- `SECURITY.md`
- `docs/README.md`
- 与当前任务直接相关的源码、测试和文档

涉及发布或安装包时还要读：

- `.github/workflows/ci.yml`
- `.github/workflows/release-desktop.yml`
- `docs/releases/` 中最新版本说明

涉及 CampusVision C1 时还要读：

- `docs/api_contract.md`
- `docs/c1_c2_integration.md`
- `docs/c1_auto_connection.md`
- `docs/c1_remote_deploy.md`
- `services/campusvision-c1/README.md`

涉及 UI、前端重构或视觉方向时还要读：

- `PRODUCT.md`
- `DESIGN.md`
- `.github/skills/impeccable/SKILL.md`（如存在）

## 分支与提交

- `main` 是稳定基线，受保护。非琐碎改动必须从最新 `main` 新建短期分支。
- Codex 协助的分支默认使用 `codex/...`，例如 `codex/cross-platform-desktop`。
- 小范围错别字、README 或 GitHub Release 正文同步、紧急低风险修复可以由维护者直接提交 `main`，但必须保留清晰提交记录。
- 不要混入无关改动。提交前必须检查 `git status --short --branch` 和 diff。
- 不要重写 `main` 历史、force push `main`、删除 `main` 或回滚用户未要求回滚的改动。
- Commit message 使用简洁工程语义，例如 `feat(desktop): add cross-platform packaging`、`docs: update release guide`。

## Pull Request 规范

- PR 标题必须使用 `type(scope): summary`。
- 不要在 PR 标题或 commit 标题中使用 `[codex]`、`[copilot]`、`[ai]`、`AI:` 等工具来源前缀。
- 如果需要说明 AI agent 参与，写在 PR 正文或评论中。
- PR 正文必须保留并填写 `.github/PULL_REQUEST_TEMPLATE.md` 的中英双语结构。
- 使用 CLI 或脚本更新 PR 正文时必须保留 Markdown 换行。PowerShell 中不要把 `gh pr view --jq .body` 的多行输出直接赋值后写回；应使用 `(gh pr view <PR_NUMBER> --json body | ConvertFrom-Json).body` 取得单个多行字符串，或使用已确认格式正确的 Markdown 文件作为 `--body-file`。更新后必须重新读取 PR 正文，确认 `## 中文`、`## English`、列表和复选框仍按多行显示。
- 影响范围、验证项、安全与数据检查必须按实际情况勾选；未运行的验证必须说明原因。
- CI 未通过、审查未完成、对话未解决时不要合并。
- 合并前必须检查 PR 正文 reaction、Issue 评论、审查线程和审查状态。👀 / 👍 这类审查状态 reaction 只存在且只读取 PR 正文下方的 reaction，不存在于 review 后评论，也不以 review/comment 下方 reaction 作为审查状态。若暂时没有任何审查信号，AI agent 应持续轮询到出现明确状态再继续；只有在没有 PR 正文审查信号且需要主动启动审查时，才可评论 `@codex review`。PR 正文已有 👀 或等价“正在 review”信号时，说明审查已经在进行中，不得再次手动触发 review，只能继续轮询等待结果。三种标准状态是：PR 正文出现 👀 或等价信号表示仍在 review，不要合并；PR 正文出现 👍、明确 approval 或明确无阻断结论表示 review 完成且当前无阻断问题；Issue 评论、review 评论或未解决线程表示存在反馈，必须处理后再重新等待审查信号。新的提交后需要重新确认最后一次 review 已完成。
- 仓库使用 squash merge；合并后删除源分支。
- AI agent 对 PR、commit、branch diff 或工作区改动进行代码审查时，审查输出必须中英双语；包括总体结论、风险说明、修改建议和 inline review comment。中文在前、English 在后，中英文之间必须至少换行分隔，不要写在同一段内；两种语言内容应结构一致、语义一致。

## GitHub Project 规范

- Issue 和 PR 应加入 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2)。
- Project item 必须补齐：
  - `Status`
  - `Area`
  - `Type`
  - `Priority`
  - `Blocked`
  - `Start date`
  - `End date`
  - `Timeline order`
  - 必要的 `Target version`
- `Timeline order` 按真实时间和同日内先后顺序递增。
- 不要只依赖 PR/Issue 页面显示的 Project 关联。必须确认 item 在 GKGuard Roadmap 或 Project 主列表可见。
- 可使用：

```powershell
gh project item-list 2 --owner CyrusAuyeung --limit 200 --format json
```

- 如果 PR/Issue 侧显示已关联 Project，但 Roadmap 或 `item-list` 不显示，等待后重查；仍不显示时重建 Project item，必要时创建可见 Draft item 并在正文链接原 PR/Issue。
- 可使用 `scripts/Update-RoadmapItem.ps1` 半自动添加 PR/Issue 并填写字段，但仍要人工确认日期、版本和顺序。

## 文档同步

任何影响当前行为的改动都必须同步相关文档：

| 改动类型 | 必查文档 |
|---|---|
| API 或字段变化 | `docs/api_contract.md`、`docs/data_dictionary.md` |
| CampusVision C1 / GKGuard C2 接入 | `docs/c1_c2_integration.md`、`docs/c1_auto_connection.md` |
| CampusVision C1 远端部署 | `docs/c1_remote_deploy.md` |
| 演示流程 | `docs/demo_script.md` |
| CampusCar / UE 占位接口 | `docs/campuscar_ue_integration.md` |
| 桌面端、安装包或更新行为 | `README.md`、`docs/README.md`、对应 Release note |
| 协作流程、PR、Project 或 AI agent 规则 | `CONTRIBUTING.md`、`GOVERNANCE.md`、`AGENTS.md`、`.github/PULL_REQUEST_TEMPLATE.md` |
| 新版本发布 | `package.json`、`package-lock.json`、`docs/releases/vX.Y.Z.md`、根目录 Markdown 文档、`docs/` 下所有 Markdown 文档、GitHub Release 正文 |

文档维护规则：

- 面向仓库用户的文档默认中文在前、English 在后。
- 修改任何中英双语文档时必须保持中文与 English 章节结构一致、语义一致；新增或删除规则、步骤、限制或验证项时要同步两种语言版本。
- 当前状态文档描述最新版本行为。
- 每次版本更新或发布准备都必须逐份阅读根目录和 `docs/` 下所有 Markdown 文档的全文，包括 `SECURITY.md`、`SUPPORT.md`、`GOVERNANCE.md`、`CONTRIBUTING.md`、`AGENTS.md`、文档索引、API 规范、集成说明、演示脚本、数据字典和当前版本 Release note，确认每句话仍符合最新功能、安全边界、发布产物、验证结果和协作流程；不能只搜索替换版本号或只抽查部分文档。
- 历史 Release notes 保留发布时语境，除非修复术语错误、明显事实错误或翻译问题。
- 使用“API 规范”和“接口规范”，保持术语一致。
- 使用“管理”表达项目管理、协作管理和发布管理等语境。
- 不要单独写孤立的 `C1` 或 `C2`，除非同段近处已经出现过 `CampusVision C1` 或 `GKGuard C2`。优先写完整名称。

## 测试与验证

按改动范围选择验证。常用命令：

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check backend/app/static/app.js
node --check desktop/main.js
node --check desktop/preload.js
node --check tests/e2e/gkguard-ui.spec.js
npm run test:e2e
npm audit --audit-level=low
git diff --check
```

桌面打包相关：

```powershell
npm run dist:win
npm run dist:mac
npm run dist:linux
```

注意：macOS/Linux 安装包通常需要对应系统 runner 才能完整验证。Windows 本地环境不能替代 macOS/Linux runner 的最终打包验证。

## 发布流程

- 普通协作者和 AI agent 不要自行推送 `v*` tag 或创建 GitHub Release，除非用户明确要求，或当前任务就是发布准备且验证已完成。
- 发布版本按变更规模递增推进；补丁修复可从 `v0.2.0` 递增到 `v0.2.1`，功能级或集成级更新可推进到新的 minor 版本，例如 `v0.3.0`。
- 发布前必须：
  - 更新 `package.json` 和 `package-lock.json`。
  - 新增或更新 `docs/releases/vX.Y.Z.md`。
  - 同步 README、docs index、SECURITY、演示脚本和相关当前状态文档，并逐份阅读根目录和 `docs/` 下所有 Markdown 文档全文，确认当前表述仍准确。
  - 跑完相关本地验证。
  - 推送 PR 并等待 CI。
  - 合并后推送 tag。
- 发布后必须核对：
  - GitHub Release 正文是否使用对应 release note。
  - Windows 是否仍有 `GKGuard-Setup-*.exe`，保证旧 Windows 客户端可以继续检查更新。
  - macOS 是否有 `GKGuard-macOS-*.dmg` 或 `GKGuard-macOS-*.zip`。
  - Linux 是否有 `GKGuard-Linux-*.AppImage` 或 `GKGuard-Linux-*.deb`。
  - `.blockmap` 和 `latest*.yml` 是否齐全。
  - Project item 是否进入 `Done`，日期和 `Timeline order` 是否正确。

## 安全与隐私

禁止提交或公开：

- 真实监控视频、真实查询图片、抽帧图、人脸裁剪图。
- 真实姓名、学号/工号、手机号、车牌、轨迹、案件材料。
- `.env`、数据库、模型缓存、运行日志中的敏感内容。
- CampusVision C1 服务器密码、SSH 私钥、token、API key。
- 其他真实运行环境访问凭据。
- 真实运行环境的原始 SSH 公钥、`known_hosts` 行或 `authorized_keys` 行；用于 SSH 主机校验的受信主机密钥指纹值仅可作为代码默认值或受控运行配置维护，面向用户的示例使用占位符。

如果疑似提交了敏感内容：

1. 立刻停止继续 push。
2. 通知维护者。
3. 按 `SECURITY.md` 处理公开内容、历史、Release 附件和凭据轮换。

不要依赖 secret scanning 替代人工检查。

## UI 与前端约束

- 保持 `v0.3.x` GKGuard C2 工作台 / Evidence Desk 视觉方向：固定左侧导航承载 `人脸以图搜人` 与 `人物特征搜索`，结果页以左侧目标人物与检索记录、右侧证据详情为主，候选人物使用右侧抽屉按人物身份复核并筛选记录，具体事件证据信息在主结果详情区呈现。
- 使用 Impeccable 设计约束时，应以 `PRODUCT.md`、`DESIGN.md` 和 `.github/skills/impeccable/` 中的产品定位、设计系统和反模式为准；不要引入营销首页、装饰性仪表盘、霓虹监控风、过度渐变或暗色指挥中心风格。
- 优先修复可用性、状态反馈、文案一致性、真实数据适配和响应式布局。
- 结果页记录列表在桌面端位于左侧；移动端可使用横向滑动提示。
- 关键帧、人脸框、人物照片和缩略图必须按实际图片内容区域定位，避免落到黑边、左上角或错误裁切区域。
- 按钮、弹窗、toast、加载态和错误态都要可恢复，不允许长时间卡在“检索中”。
- 修改 UI 后要用 Playwright 或浏览器实际检查桌面、紧凑窗口和移动视口。

## CampusVision C1 规则

- 当前真实环境默认仍以 `speng@10.4.167.122`、远端 `127.0.0.1:8000`、本地隧道 `127.0.0.1:18000` 为准，除非用户提供新环境。
- GKGuard C2 只能通过代理接口接入 CampusVision C1，不要让前端直接依赖多个外部服务。
- CampusVision C1 远端服务、查询图预处理、真实数据索引和 SSH 部署脚本的改动必须同步相关文档。
- 不要把本地 mock 命中写成真实 CampusVision C1 命中。

## 回复用户时

- 用中文回答，直接说明事实、风险、验证和下一步。
- 不要只给建议而不执行，除非用户明确要求先给计划或需要确认。
- 如果用户要求“先给方案”，不要改文件；等确认后再执行。
- 如果用户要求标准流程，完成实现后应继续检查文档、Project、PR、CI、合并和 Release，不要等待用户重复提醒。
- 如果存在权限、外部服务、签名证书、macOS 公证、移动端应用商店账号等无法自行完成的事项，明确说明阻塞点和替代方案。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# AGENTS.md

This file is the repository-level development guide for AI agents working on GKGuard. Codex, Copilot, ChatGPT, or any other automated development assistant must read this file before modifying this repository, and must treat these rules as repository-level constraints.

## Project Positioning

- GKGuard C2 is the campus-security AI search workbench. It owns the local FastAPI backend, static frontend, Electron desktop app, local mock fallback, CampusVision C1 proxy, result presentation, route visualization, release engineering, and documentation system.
- CampusVision C1 is the separate video-search service. It owns video upload, frame sampling, face embeddings, the person index, image-based person search, keyframes, and trajectory output. GKGuard C2 accesses it through the `/c1/...` proxy.
- CampusCar, ROS2, and UE Bridge currently remain placeholder interface specifications only. Do not describe placeholder interfaces as completed integrations with real vehicles, real ROS2 nodes, or a real UE runtime.
- Group A owns mechanical structure, Group B owns embedded control, and Group C owns algorithm perception. When documents need to reference team groups, use these explicit names instead of ambiguous numeric-only labels.

## Required Reading

Before starting a task, read at least:

- `README.md`
- `CONTRIBUTING.md`
- `GOVERNANCE.md`
- `SECURITY.md`
- `docs/README.md`
- Source code, tests, and documents directly related to the current task

For release or installer work, also read:

- `.github/workflows/ci.yml`
- `.github/workflows/release-desktop.yml`
- The latest release note under `docs/releases/`

For CampusVision C1 work, also read:

- `docs/api_contract.md`
- `docs/c1_c2_integration.md`
- `docs/c1_auto_connection.md`
- `docs/c1_remote_deploy.md`
- `services/campusvision-c1/README.md`

For UI, frontend redesign, or visual-direction work, also read:

- `PRODUCT.md`
- `DESIGN.md`
- `.github/skills/impeccable/SKILL.md` when present

## Branches And Commits

- `main` is the protected stable baseline. Non-trivial changes must start from the latest `main` on a short-lived branch.
- Codex-assisted branches should use `codex/...` by default, for example `codex/cross-platform-desktop`.
- Maintainers may commit small typo fixes, README or GitHub Release body synchronization, and urgent low-risk fixes directly to `main`, but the commit history must remain clear.
- Do not mix unrelated changes. Before committing, check `git status --short --branch` and the diff.
- Do not rewrite `main` history, force push `main`, delete `main`, or revert changes the user did not ask to revert.
- Commit messages should use concise engineering wording, for example `feat(desktop): add cross-platform packaging` or `docs: update release guide`.

## Pull Request Rules

- PR titles must use `type(scope): summary`.
- Do not use tool-source prefixes such as `[codex]`, `[copilot]`, `[ai]`, or `AI:` in PR titles or commit titles.
- If AI agent participation needs to be disclosed, put it in the PR body or a comment.
- PR bodies must keep and fill the bilingual structure from `.github/PULL_REQUEST_TEMPLATE.md`.
- When updating a PR body through the CLI or scripts, preserve Markdown line breaks. In PowerShell, do not assign multiline output from `gh pr view --jq .body` and write it back directly; use `(gh pr view <PR_NUMBER> --json body | ConvertFrom-Json).body` to get a single multiline string, or use a verified Markdown file with `--body-file`. After editing, read the PR body again and confirm `## 中文`, `## English`, lists, and checkboxes still appear on separate lines.
- Scope, validation, security, and data-check boxes must be checked according to the actual change. Any skipped validation must be explained.
- Do not merge while CI is failing, review is incomplete, or conversations remain unresolved.
- Before merging, check PR-body reactions, issue comments, review threads, and review state. Review-status reactions such as 👀 / 👍 exist only below the PR body and only PR-body reactions count; reactions below review comments or other comments are not review-status signals. If no review signal is present yet, the AI agent should keep polling until a clear state appears. Only comment `@codex review` when there is no PR-body review signal and a review needs to be started actively. If the PR body already has 👀 or an equivalent review-in-progress signal, review is already running; do not manually retrigger review, and only keep polling for the result. The three standard states are: 👀 or an equivalent PR-body reaction means review is still in progress and the PR must not be merged; 👍 on the PR body, explicit approval, or an explicit no-blocker conclusion means review is complete with no current blocker; issue comments, review comments, or unresolved threads mean feedback exists and must be addressed before waiting for the next review signal. After new commits, reconfirm that the latest review is complete.
- The repository uses squash merge. Delete the source branch after merge.
- When an AI agent reviews a PR, commit, branch diff, or working-tree change, the review output must be bilingual Chinese/English, including the overall conclusion, risk notes, change suggestions, and inline review comments. Chinese must come first, English second, and the two language sections must be separated by at least a line break instead of being written in the same paragraph. The Chinese and English content should stay structurally and semantically aligned.

## GitHub Project Rules

- Issues and PRs should be added to [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2).
- Each Project item must include:
  - `Status`
  - `Area`
  - `Type`
  - `Priority`
  - `Blocked`
  - `Start date`
  - `End date`
  - `Timeline order`
  - Required `Target version` where applicable
- `Timeline order` increases by real chronological order and same-day sequence.
- Do not rely only on the PR/Issue page showing a Project association. Confirm the item is visible in GKGuard Roadmap or the Project main item list.
- You may use:

```powershell
gh project item-list 2 --owner CyrusAuyeung --limit 200 --format json
```

- If the PR/Issue side shows a Project association but Roadmap or `item-list` does not show it, wait and query again. If it still does not appear, recreate the Project item. If needed, create a visible Draft item and link the original PR/Issue in its body.
- You may use `scripts/Update-RoadmapItem.ps1` to add a PR/Issue and fill fields semi-automatically, but dates, versions, and order still require human confirmation.

## Documentation Synchronization

Any change that affects current behavior must synchronize the related documents:

| Change Type | Documents To Check |
|---|---|
| API or field changes | `docs/api_contract.md`, `docs/data_dictionary.md` |
| CampusVision C1 / GKGuard C2 integration | `docs/c1_c2_integration.md`, `docs/c1_auto_connection.md` |
| CampusVision C1 remote deployment | `docs/c1_remote_deploy.md` |
| Demo flow | `docs/demo_script.md` |
| CampusCar / UE placeholder interface | `docs/campuscar_ue_integration.md` |
| Desktop app, installer, or update behavior | `README.md`, `docs/README.md`, matching Release note |
| Collaboration flow, PR, Project, or AI agent rules | `CONTRIBUTING.md`, `GOVERNANCE.md`, `AGENTS.md`, `.github/PULL_REQUEST_TEMPLATE.md` |
| New release | `package.json`, `package-lock.json`, `docs/releases/vX.Y.Z.md`, root Markdown documents, all Markdown documents under `docs/`, GitHub Release body |

Documentation maintenance rules:

- User-facing documents should be Chinese first and English second.
- When changing any Chinese/English bilingual document, keep the Chinese and English sections structurally and semantically aligned. Any added or removed rule, step, constraint, or validation item must be synchronized in both languages.
- Current-state documents describe the latest release behavior.
- Every version update or release-preparation change must read the full text of every root Markdown document and every Markdown document under `docs/`, including `SECURITY.md`, `SUPPORT.md`, `GOVERNANCE.md`, `CONTRIBUTING.md`, `AGENTS.md`, documentation indexes, API specifications, integration guides, demo scripts, data dictionaries, and the current release note. Confirm that each sentence still matches the latest features, security boundaries, release assets, validation results, and collaboration flow. Do not only search-and-replace version numbers or sample only part of the documentation.
- Historical Release notes keep release-time context unless fixing terminology, clear factual errors, or translation problems.
- Use "API 规范" and "接口规范" consistently in Chinese terminology.
- Use "管理" for Chinese project, collaboration, and release management wording.
- Do not write isolated `C1` or `C2` unless `CampusVision C1` or `GKGuard C2` appears nearby in the same section. Prefer the full names.

## Validation

Choose validation according to the change scope. Common commands:

```powershell
python -m pytest backend
python -m py_compile backend/desktop_server.py
node --check backend/app/static/app.js
node --check desktop/main.js
node --check desktop/preload.js
node --check tests/e2e/gkguard-ui.spec.js
npm run test:e2e
npm audit --audit-level=low
git diff --check
```

Packaging checks:

```powershell
npm run dist:win
npm run dist:mac
npm run dist:linux
```

Note: macOS/Linux packages usually require matching system runners for full verification. A local Windows environment does not replace final macOS/Linux runner verification.

## Release Flow

- Regular contributors and AI agents must not push `v*` tags or create GitHub Releases unless the user explicitly asks, or the current task is release preparation and validation is complete.
- Release versions advance according to change size. Patch fixes may move from `v0.2.0` to `v0.2.1`, while feature-level or integration-level updates may move to a new minor version such as `v0.3.0`.
- Before release:
  - Update `package.json` and `package-lock.json`.
  - Add or update `docs/releases/vX.Y.Z.md`.
  - Synchronize README, docs index, SECURITY, demo script, and relevant current-state docs, and read the full text of every root Markdown document and every Markdown document under `docs/` for current accuracy.
  - Run the relevant local validation.
  - Push the PR and wait for CI.
  - Push the tag after merge.
- After release, verify:
  - The GitHub Release body uses the matching release note.
  - Windows still has `GKGuard-Setup-*.exe`, so old Windows clients can continue checking updates.
  - macOS has `GKGuard-macOS-*.dmg` or `GKGuard-macOS-*.zip`.
  - Linux has `GKGuard-Linux-*.AppImage` or `GKGuard-Linux-*.deb`.
  - `.blockmap` and `latest*.yml` are present.
  - The Project item is `Done`, with correct dates and `Timeline order`.

## Security And Privacy

Do not commit or disclose:

- Real surveillance videos, real query images, extracted frames, or face crops.
- Real names, student/staff IDs, phone numbers, license plates, trajectories, or case material.
- `.env`, databases, model caches, or sensitive runtime logs.
- CampusVision C1 server passwords, SSH private keys, tokens, or API keys.
- Other access credentials for real runtime environments.
- Raw SSH public keys, `known_hosts` lines, or `authorized_keys` lines for real runtime environments. Trusted host-key fingerprint values used for SSH host verification may be maintained only as code defaults or controlled runtime config, while user-facing examples use placeholders.

If sensitive content may have been committed:

1. Stop pushing immediately.
2. Notify the maintainer.
3. Follow `SECURITY.md` for public content cleanup, history/Release asset handling, and credential rotation.

Do not rely on secret scanning as a substitute for manual review.

## UI And Frontend Constraints

- Keep the `v0.3.x` GKGuard C2 Workbench / Evidence Desk visual direction: fixed left navigation for `人脸以图搜人` and `人物特征搜索`, result pages led by left-side target person plus result records and right-side evidence detail, and a right-side candidate-person drawer for identity review and record filtering, while concrete event evidence remains in the main result detail area.
- When using Impeccable design constraints, treat `PRODUCT.md`, `DESIGN.md`, and `.github/skills/impeccable/` as the source for product positioning, design-system rules, and anti-patterns. Do not introduce marketing homepages, decorative dashboards, neon surveillance styling, excessive gradients, or dark command-center aesthetics.
- Prioritize usability, state feedback, copy consistency, real-data adaptation, and responsive layout.
- On desktop result pages, the record list stays on the left. Mobile views may use horizontal-scroll hints.
- Keyframes, face boxes, person portraits, and thumbnails must be positioned against the actual rendered image content area, not black bars, the top-left corner, or an incorrect crop region.
- Buttons, dialogs, toasts, loading states, and error states must be recoverable. The UI must not stay indefinitely in `检索中`.
- After UI changes, inspect desktop, compact-window, and mobile viewports with Playwright or a real browser.

## CampusVision C1 Rules

- Unless the user provides a new environment, the current real environment remains `speng@10.4.167.122`, remote `127.0.0.1:8000`, and local tunnel `127.0.0.1:18000`.
- GKGuard C2 must integrate CampusVision C1 through proxy endpoints. Do not make the frontend directly depend on multiple external services.
- Changes to the CampusVision C1 remote service, query-image preprocessing, real data indexing, or SSH deployment scripts must synchronize the related documents.
- Do not describe local mock hits as real CampusVision C1 hits.

## Responding To The User

- Reply in Chinese. State facts, risks, validation, and next steps directly.
- Do not stop at suggestions when the user expects execution, unless the user explicitly asks for a plan first or confirmation is required.
- If the user asks for a plan first, do not edit files until the user confirms.
- If the user asks for the standard workflow, after implementation continue through docs, Project, PR, CI, merge, and Release checks instead of waiting for repeated reminders.
- If permissions, external services, signing certificates, macOS notarization, or mobile app-store accounts block completion, state the blocker and the practical alternative.

<p align="right"><a href="#english">Back to English top</a></p>
