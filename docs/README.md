<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# GKGuard 文档索引

本文档用于交接和维护时快速定位材料。当前文档以 `v0.1.17` 为最新状态，历史 Release notes 保持各版本发布时的语境。

## 推荐阅读顺序

1. [README.md](../README.md)：项目定位、交付范围、运行方式、发布流程和验收清单。
2. [c1_c2_integration.md](c1_c2_integration.md)：C1/C2 职责边界、字段映射和联调检查。
3. [c1_auto_connection.md](c1_auto_connection.md)：安装版自动连接 C1、SSH 隧道和密码窗口行为。
4. [api_contract.md](api_contract.md)：C2 API、C1 代理接口和 CampusCar/UE 占位接口。
5. [demo_script.md](demo_script.md)：安装版和本地开发版演示流程。
6. [data_dictionary.md](data_dictionary.md)：mock 数据、C1 检索数据和敏感字段边界。
7. [campuscar_ue_integration.md](campuscar_ue_integration.md)：CampusCar、ROS2、UE Bridge 的当前占位合同。

## 发布与版本

- [releases/v0.1.17.md](releases/v0.1.17.md)：当前最新版本说明。
- [releases/](releases/)：历史版本发布记录。
- 每次发布新 tag 前，应同步更新 README、相关当前状态文档和对应 `docs/releases/vX.Y.Z.md`。
- 发布后需要核对 GitHub Release 正文、安装包、`.blockmap` 和 `latest.yml`。

## 配置示例

- [examples/c1-connection.example.json](examples/c1-connection.example.json)：C1 候选地址和 SSH 隧道覆盖配置示例。

## 文档维护要求

- 面向仓库用户的文档默认中文在前、English 在后。
- 当前状态文档描述最新版本行为；历史 Release notes 不回写成最新状态。
- 涉及真实 C1、校园网、VPN、SSH 或服务器访问时，必须写明网络前提和密码处理方式。
- 不在文档示例中放入真实密码、token、SSH 私钥、真实人脸、真实视频或个人信息。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# GKGuard Documentation Index

Use this page to locate handoff and maintenance material quickly. The current-state documentation tracks `v0.1.17`; historical Release notes keep the context from each release.

## Recommended Reading Order

1. [README.md](../README.md): project positioning, delivery scope, run modes, release flow, and acceptance checklist.
2. [c1_c2_integration.md](c1_c2_integration.md): C1/C2 ownership boundary, field mapping, and integration checklist.
3. [c1_auto_connection.md](c1_auto_connection.md): packaged-app C1 auto-connection, SSH tunnel, and password-window behavior.
4. [api_contract.md](api_contract.md): C2 APIs, C1 proxy endpoints, and CampusCar/UE placeholder endpoints.
5. [demo_script.md](demo_script.md): packaged-app and local-development demo flows.
6. [data_dictionary.md](data_dictionary.md): mock data, C1 search data, and sensitive-field boundaries.
7. [campuscar_ue_integration.md](campuscar_ue_integration.md): current placeholder contract for CampusCar, ROS2, and UE Bridge.

## Releases And Versions

- [releases/v0.1.17.md](releases/v0.1.17.md): latest release notes.
- [releases/](releases/): historical release records.
- Before publishing a new tag, update README, relevant current-state docs, and the matching `docs/releases/vX.Y.Z.md`.
- After publishing, verify the GitHub Release body, installer, `.blockmap`, and `latest.yml`.

## Configuration Examples

- [examples/c1-connection.example.json](examples/c1-connection.example.json): example override config for C1 candidate URLs and SSH tunnel settings.

## Documentation Maintenance Rules

- User-facing documentation should be Chinese first and English second.
- Current-state docs describe the latest behavior; historical Release notes should not be rewritten into the latest context.
- When documenting real C1, campus network, VPN, SSH, or server access, state the network prerequisite and password-handling behavior.
- Do not put real passwords, tokens, SSH private keys, real faces, real videos, or personal information in documentation examples.

<p align="right"><a href="#english">Back to English top</a></p>