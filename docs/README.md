<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# GKGuard 文档索引

本文档用于维护时快速定位材料。当前文档以 `v0.1.23` 为最新状态，历史发布说明保留各版本发布时的语境。

## 推荐阅读顺序

1. [README.md](../README.md)：仓库内容、运行方式、发布流程和验证命令。
2. [c1_c2_integration.md](c1_c2_integration.md)：CampusVision C1 服务与 GKGuard C2 工作台的职责边界、字段映射和联调检查。
3. [c1_auto_connection.md](c1_auto_connection.md)：安装版自动连接 CampusVision C1、SSH 隧道和密码窗口行为。
4. [api_contract.md](api_contract.md)：GKGuard C2 API、CampusVision C1 代理接口和 CampusCar/UE 占位接口。
5. [demo_script.md](demo_script.md)：安装版和本地开发版演示流程。
6. [data_dictionary.md](data_dictionary.md)：模拟数据、CampusVision C1 检索数据和敏感字段边界。
7. [campuscar_ue_integration.md](campuscar_ue_integration.md)：CampusCar、ROS2、UE Bridge 的当前占位接口规范。

## 发布与版本

- [releases/v0.1.23.md](releases/v0.1.23.md)：当前最新版本说明，记录浏览器 E2E 回归、关键帧预览、路线联动和 Project 脚本。
- [releases/v0.1.22.md](releases/v0.1.22.md)：移动端 UI 精修、空 toast 修复和静态资源版本命名。
- [releases/](releases/)：历史版本发布记录。
- 每次发布新版本标签前，应同步更新 README、相关当前状态文档和对应 `docs/releases/vX.Y.Z.md`。
- 发布后需要核对 GitHub Release 正文、安装包、`.blockmap` 和 `latest.yml`。

## 仓库协作与管理

- [CONTRIBUTING.md](../CONTRIBUTING.md)：分支、Pull Request、验证命令和文档同步要求。
- [GOVERNANCE.md](../GOVERNANCE.md)：A组机械结构、B组嵌入式控制、C组算法感知的维护职责，以及 `main` 保护、审查、CI、标签和 Project 规则。
- [SUPPORT.md](../SUPPORT.md)：问题反馈入口、Issue 模板使用方式和支持边界。
- [SECURITY.md](../SECURITY.md)：敏感数据、真实媒体、凭据和 CampusVision C1 连接安全要求。
- [scripts/Update-RoadmapItem.ps1](../scripts/Update-RoadmapItem.ps1)：半自动添加 PR/Issue 到 GKGuard Roadmap 并填写 Project 字段。
- 当前协作配置以 `main` 保护、短期分支 Pull Request、`Verify` 必需检查、squash merge、合并后删除分支、标签归类和 [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project 跟踪为准；Project item 应补齐 `Status`、`Area`、`Type`、`Priority`、`Blocked`、`Start date`、`End date`、`Timeline order` 和必要的 `Target version`。
- Milestone 暂不强制使用；CODEOWNERS 暂不启用。

## 配置示例

- [examples/c1-connection.example.json](examples/c1-connection.example.json)：CampusVision C1 候选地址和 SSH 隧道覆盖配置示例。

## 文档维护要求

- 面向仓库用户的文档默认中文在前、English 在后。
- 当前状态文档描述最新版本行为；历史发布说明不回写成最新状态。
- 涉及真实 CampusVision C1、校园网、VPN、SSH 或服务器访问时，必须写明网络前提和密码处理方式。
- 不在文档示例中放入真实密码、token、SSH 私钥、真实人脸、真实视频或个人信息。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# GKGuard Documentation Index

Use this page to locate maintenance material quickly. The current-state documentation tracks `v0.1.23`; historical Release notes keep the context from each release.

## Recommended Reading Order

1. [README.md](../README.md): repository contents, run modes, release flow, and validation commands.
2. [c1_c2_integration.md](c1_c2_integration.md): CampusVision C1 service and GKGuard C2 workbench ownership boundary, field mapping, and integration checklist.
3. [c1_auto_connection.md](c1_auto_connection.md): packaged-app CampusVision C1 auto-connection, SSH tunnel, and password-window behavior.
4. [api_contract.md](api_contract.md): GKGuard C2 APIs, CampusVision C1 proxy endpoints, and CampusCar/UE placeholder endpoints.
5. [demo_script.md](demo_script.md): packaged-app and local-development demo flows.
6. [data_dictionary.md](data_dictionary.md): mock data, CampusVision C1 search data, and sensitive-field boundaries.
7. [campuscar_ue_integration.md](campuscar_ue_integration.md): current placeholder interface specification for CampusCar, ROS2, and UE Bridge.

## Releases And Versions

- [releases/v0.1.23.md](releases/v0.1.23.md): latest release notes covering browser E2E regression, keyframe preview, route selection sync, and the Project helper.
- [releases/v0.1.22.md](releases/v0.1.22.md): mobile UI polish, empty-toast cleanup, and static asset version naming.
- [releases/](releases/): historical release records.
- Before publishing a new tag, update README, relevant current-state docs, and the matching `docs/releases/vX.Y.Z.md`.
- After publishing, verify the GitHub Release body, installer, `.blockmap`, and `latest.yml`.

## Repository Collaboration And Management

- [CONTRIBUTING.md](../CONTRIBUTING.md): branch, Pull Request, validation command, and documentation synchronization requirements.
- [GOVERNANCE.md](../GOVERNANCE.md): Group A mechanical structure, Group B embedded control, and Group C algorithm perception ownership, plus `main` protection, review, CI, label, and Project rules.
- [SUPPORT.md](../SUPPORT.md): support paths, issue template usage, and support boundaries.
- [SECURITY.md](../SECURITY.md): sensitive data, real media, credentials, and CampusVision C1 connection security requirements.
- [scripts/Update-RoadmapItem.ps1](../scripts/Update-RoadmapItem.ps1): semi-automatically add PRs/Issues to GKGuard Roadmap and fill Project fields.
- The current collaboration setup is `main` protection, short-lived branch Pull Requests, required `Verify` checks, squash merge, merged-branch deletion, label triage, and tracking in the [GKGuard Roadmap](https://github.com/users/CyrusAuyeung/projects/2) Project. Project items should include `Status`, `Area`, `Type`, `Priority`, `Blocked`, `Start date`, `End date`, `Timeline order`, and required `Target version`.
- Milestones are not mandatory yet. CODEOWNERS is not enabled yet.

## Configuration Examples

- [examples/c1-connection.example.json](examples/c1-connection.example.json): example override config for CampusVision C1 candidate URLs and SSH tunnel settings.

## Documentation Maintenance Rules

- User-facing documentation should be Chinese first and English second.
- Current-state docs describe the latest behavior; historical Release notes should not be rewritten into the latest context.
- When documenting real CampusVision C1, campus network, VPN, SSH, or server access, state the network prerequisite and password-handling behavior.
- Do not put real passwords, tokens, SSH private keys, real faces, real videos, or personal information in documentation examples.

<p align="right"><a href="#english">Back to English top</a></p>
