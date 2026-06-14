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
| v0.1.13 | 当前演示版本，接受安全修复 |
| v0.1.9 - v0.1.12 | 已被 v0.1.13 替代；建议升级到最新版 |
| v0.1.8 及更早 | 历史演示版本，仅按需要补充说明 |

## 如何报告安全问题

请不要在公开 Issue 中提交漏洞细节、真实图片、真实视频、密码、token、私钥或服务器敏感信息。

推荐方式：

1. 在 GitHub 上联系仓库所有者，说明“GKGuard security report”。
2. 提供最小必要信息：影响范围、复现步骤、受影响文件或接口、建议修复方向。
3. 如必须提供截图或日志，先脱敏并移除人脸、学号、手机号、token、IP 以外的敏感细节。

如果问题已经公开暴露，请先删除敏感内容，再通知维护者清理历史、Release 附件或日志。

## 高风险内容

以下内容不得提交或粘贴到公开位置：

- C1 服务器密码、SSH 私钥、token、API key。
- `.env`、数据库、模型缓存、真实运行日志。
- 真实校园视频、查询图片、抽帧图片、人脸裁剪图。
- 真实人员身份、联系方式、轨迹、车牌、案件材料。

## 连接安全

- GKGuard 不保存 SSH 密码；密码只应输入在系统 PowerShell/SSH 窗口中。
- 若 C1 监听 `0.0.0.0`，必须通过防火墙、校园网策略或反向代理限制访问范围。
- 优先使用受控校园网、VPN 或 SSH 隧道访问 C1。
- 不要把 C1 识别服务暴露到不可信公网。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Security Policy

GKGuard involves campus security demonstrations, face search, trajectory display, and server connection configuration. Protect personal privacy, server credentials, and real media data first.

## Supported Versions

Currently maintained versions:

| Version | Status |
|---|---|
| v0.1.13 | Current demo version, accepts security fixes |
| v0.1.9 - v0.1.12 | Superseded by v0.1.13; upgrade to the latest release |
| v0.1.8 and earlier | Historical demo versions, documentation updates only as needed |

## Reporting A Security Issue

Do not submit vulnerability details, real images, real videos, passwords, tokens, private keys, or sensitive server details in public issues.

Recommended process:

1. Contact the repository owner on GitHub and label the message as “GKGuard security report”.
2. Provide only necessary information: impact, reproduction steps, affected files or endpoints, and suggested remediation.
3. If screenshots or logs are necessary, redact faces, student IDs, phone numbers, tokens, and sensitive details beyond the minimum needed.

If sensitive content was already exposed publicly, remove it first, then notify maintainers to clean history, Release assets, or logs as needed.

## High-Risk Content

Do not commit or paste:

- C1 server passwords, SSH private keys, tokens, or API keys.
- `.env` files, databases, model caches, or real runtime logs.
- Real campus videos, query images, extracted frames, or face crops.
- Real identities, contact details, trajectories, license plates, or case material.

## Connection Security

- GKGuard does not store SSH passwords; passwords should only be entered in the system PowerShell/SSH window.
- If C1 listens on `0.0.0.0`, restrict access through firewall, campus network policy, or reverse proxy.
- Prefer controlled campus network, VPN, or SSH tunnel access to C1.
- Do not expose the C1 recognition service to untrusted public networks.

<p align="right"><a href="#english">Back to English top</a></p>
