<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 项目治理

GKGuard 当前是课程/项目演示仓库，治理目标是保持 C2 边界清晰、Release 可复现、文档可维护、敏感数据不进入仓库。

## 角色与职责

- C2 维护者：负责 `backend/`、`desktop/`、`backend/app/static/`、Release workflow 和仓库文档。
- C1 维护者：负责 `services/campusvision-c1/` 的算法服务、视频索引、人物库、以图搜人和 C1 运行数据。
- CampusCar/UE/控制组：负责真实车辆、ROS2、UE Bridge、底盘控制和外部消息 schema。
- 文档维护者：负责 README、API 合同、数据字典、演示脚本、接口说明和 Release notes。

## 决策原则

1. 先保护敏感数据，再追求演示便利。
2. C2 前端只访问 C2 后端；跨服务访问通过 C2 adapter 或明确合同。
3. 真实 C1、CampusCar、UE 能力必须能离线降级或有清晰失败提示。
4. Release 前必须有可追溯版本号、Release notes、测试结果和安装包资产。
5. 历史 Release notes 保持历史语境；当前状态文档同步最新版本。
6. 每次发布后再次核对 README 和所有当前状态文档，确保版本号、功能边界、验证结果和安装包说明一致。

## 合并与发布

- 普通变更通过 PR 或直接维护者提交进入 `main`。
- 影响安装包的变更需要更新版本号和 `docs/releases/vX.Y.Z.md`。
- 影响当前行为或仓库边界的变更需要同步 README、`docs/README.md`、API/集成/演示/支持/安全等相关文档。
- tag `v*` 会触发 `.github/workflows/release-desktop.yml` 构建 Windows 安装包。
- 发布后检查 Release 正文、`.exe`、`.blockmap` 和 `latest.yml`。

## 敏感数据治理

任何真实媒体、凭据、数据库、日志或个人信息一旦进入仓库，应立即：

1. 删除公开内容或撤下附件。
2. 轮换受影响凭据。
3. 评估是否需要清理 Git 历史或 Release 资产。
4. 按 [SECURITY.md](SECURITY.md) 记录和处理。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Governance

GKGuard is currently a coursework/project demo repository. Governance focuses on keeping the C2 boundary clear, Releases reproducible, documentation maintainable, and sensitive data out of the repository.

## Roles And Responsibilities

- C2 maintainers: own `backend/`, `desktop/`, `backend/app/static/`, the Release workflow, and repository documentation.
- C1 maintainers: own `services/campusvision-c1/`, algorithm service, video indexing, person index, image search, and C1 runtime data.
- CampusCar/UE/control teams: own real vehicles, ROS2, UE Bridge, low-level chassis control, and external message schemas.
- Documentation maintainers: own README, API contracts, data dictionary, demo script, interface notes, and Release notes.

## Decision Principles

1. Protect sensitive data before optimizing demo convenience.
2. The C2 frontend calls only the C2 backend; cross-service access goes through a C2 adapter or explicit contract.
3. Real C1, CampusCar, and UE capabilities must degrade offline or provide a clear failure message.
4. A Release requires traceable version, Release notes, validation results, and installer assets.
5. Historical Release notes keep their historical context; current-state documents track the latest version.
6. After every release, re-check README and all current-state docs so version numbers, capability boundaries, validation results, and installer instructions stay consistent.

## Merge And Release

- Normal changes enter `main` through PRs or maintainer commits.
- Installer-impacting changes must update the version and `docs/releases/vX.Y.Z.md`.
- Changes that affect current behavior or repository boundaries must also update README, `docs/README.md`, and relevant API/integration/demo/support/security docs.
- Tags matching `v*` trigger `.github/workflows/release-desktop.yml` to build the Windows installer.
- After publishing, check the Release body, `.exe`, `.blockmap`, and `latest.yml`.

## Sensitive Data Governance

If real media, credentials, databases, logs, or personal information enter the repository:

1. Remove public content or take down attachments.
2. Rotate affected credentials.
3. Evaluate whether Git history or Release assets need cleanup.
4. Record and handle the incident through [SECURITY.md](SECURITY.md).

<p align="right"><a href="#english">Back to English top</a></p>
