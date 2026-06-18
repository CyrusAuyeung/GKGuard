<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 安全策略

GKGuard 涉及校园安防演示、人脸检索、轨迹展示和服务器连接配置。请优先保护人员隐私、服务器凭据和真实媒体数据。

## 支持范围

当前维护版本：

| 版本 | 状态 |
|---|---|
| v0.1.24 | 当前演示版本，接受安全修复 |
| v0.1.9 - v0.1.23 | 已被 v0.1.24 替代；建议升级到最新版 |
| v0.1.8 及更早 | 历史演示版本，仅按需要补充说明 |

## 如何报告安全问题

请不要在公开 Issue 中提交漏洞细节、真实图片、真实视频、密码、token、私钥或服务器敏感信息。

推荐方式：

1. 在 GitHub 上联系仓库所有者，说明“GKGuard security report”。
2. 提供最小必要信息：影响范围、复现步骤、受影响文件或接口、建议修复方向。
3. 如必须提供截图或日志，先脱敏并移除人脸、学号、手机号、token、IP 以外的敏感细节。

如果问题已经公开暴露，请先删除敏感内容，再通知维护者清理历史、GitHub Release 附件或日志。

## 高风险内容

以下内容不得提交或粘贴到公开位置：

- CampusVision C1 服务所在服务器密码、SSH 私钥、token、API key。
- `.env`、数据库、模型缓存、真实运行日志。
- 真实校园视频、查询图片、抽帧图片、人脸裁剪图。
- 真实人员身份、联系方式、轨迹、车牌、案件材料。

GitHub secret scanning 和 push protection 已启用，用于拦截常见凭据误提交；这不能替代人工检查。若凭据已经提交或公开暴露，仍需立即轮换凭据，并按本文件流程清理公开内容、历史记录或 Release 附件。

## 连接安全

- GKGuard 不保存 SSH 密码；安装版只在软件内密码窗口中接收本次 SSH 连接所需密码，不写入配置文件、日志或仓库。
- 若 CampusVision C1 服务监听 `0.0.0.0`，必须通过防火墙、校园网策略或反向代理限制访问范围。
- 优先使用受控校园网、VPN 或 SSH 隧道访问 CampusVision C1 服务。
- 不要把 CampusVision C1 识别服务暴露到不可信公网。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Security Policy

GKGuard involves campus security demonstrations, face search, trajectory display, and server connection configuration. Protect personal privacy, server credentials, and real media data first.

## Supported Versions

Currently maintained versions:

| Version | Status |
|---|---|
| v0.1.24 | Current demo version, accepts security fixes |
| v0.1.9 - v0.1.23 | Superseded by v0.1.24; upgrade to the latest release |
| v0.1.8 and earlier | Historical demo versions, documentation updates only as needed |

## Reporting A Security Issue

Do not submit vulnerability details, real images, real videos, passwords, tokens, private keys, or sensitive server details in public issues.

Recommended process:

1. Contact the repository owner on GitHub and label the message as “GKGuard security report”.
2. Provide only necessary information: impact, reproduction steps, affected files or endpoints, and suggested remediation.
3. If screenshots or logs are necessary, redact faces, student IDs, phone numbers, tokens, and sensitive details beyond the minimum needed.

If sensitive content was already exposed publicly, remove it first, then notify maintainers to clean history, Release files, or logs as needed.

## High-Risk Content

Do not commit or paste:

- CampusVision C1 server passwords, SSH private keys, tokens, or API keys.
- `.env` files, databases, model caches, or real runtime logs.
- Real campus videos, query images, extracted frames, or face crops.
- Real identities, contact details, trajectories, license plates, or case material.

GitHub secret scanning and push protection are enabled to block common accidental credential commits. They do not replace manual review. If a credential is committed or exposed publicly, rotate it immediately and use this process to clean public content, history, or Release assets.

## Connection Security

- GKGuard does not store SSH passwords; the packaged app accepts the password only in its embedded prompt for the current SSH session and does not write it to config files, logs, or the repository.
- If the CampusVision C1 service listens on `0.0.0.0`, restrict access through firewall, campus network policy, or reverse proxy.
- Prefer controlled campus network, VPN, or SSH tunnel access to the CampusVision C1 service.
- Do not expose the CampusVision C1 recognition service to untrusted public networks.

<p align="right"><a href="#english">Back to English top</a></p>
