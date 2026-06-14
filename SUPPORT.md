<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 支持说明

本仓库主要用于 GKGuard C2 桌面工作台开发、发布和维护。请根据问题类型选择合适入口。

当前建议版本：`v0.1.18`。报告问题时请优先注明使用的 Release tag、安装包来源和 CampusVision C1 服务连接方式。

## 常见问题入口

- 安装包无法打开、Release 下载、桌面端启动问题：提交 Bug Report。
- CampusVision C1 服务连接、SSH 隧道、校园网/VPN 可达性问题：提交 Bug Report，并附 `/c1/status` 脱敏结果。
- 文档错误、接口说明不清楚：提交 Documentation Update。
- 新功能、接口扩展、CampusCar/UE 真实接入建议：提交 Feature Request。
- 安全、隐私、凭据、真实媒体泄露：不要公开提交，按 [SECURITY.md](SECURITY.md) 处理。

## 提交问题前请准备

- 使用的版本号或 Release 链接。
- Windows 版本、是否校园网/VPN、是否使用 SSH 隧道。
- CampusVision C1 服务连接方式：直连 `10.4.167.122:8000`、本机隧道 `127.0.0.1:18000`，或自定义配置。
- 复现步骤、截图、日志或接口响应。
- 确认已经移除密码、token、真实人脸、真实视频和个人信息。

## 演示支持边界

- 离线 mock fallback 属于 GKGuard C2 工作台演示能力。
- 真实 CampusVision C1 检索依赖服务器、网络和 CampusVision C1 数据索引状态。
- CampusCar/UE 当前为占位合同，不代表已接入真实车辆或 UE 运行时。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Support

This repository is primarily for GKGuard C2 desktop workbench development, releases, and maintenance. Choose the right path based on issue type.

Recommended current version: `v0.1.18`. When filing an issue, include the Release tag, installer source, and CampusVision C1 service connection path.

## Where To Ask

- Installer, Release download, or desktop startup problems: open a Bug Report.
- CampusVision C1 service connection, SSH tunnel, campus network, or VPN reachability: open a Bug Report and attach a redacted `/c1/status` result.
- Documentation errors or unclear interface notes: open a Documentation Update.
- New features, API extensions, or real CampusCar/UE integration ideas: open a Feature Request.
- Security, privacy, credentials, or real media exposure: do not open a public issue; follow [SECURITY.md](SECURITY.md).

## Prepare Before Filing

- Version number or Release link.
- Windows version, campus network/VPN status, and whether an SSH tunnel is used.
- CampusVision C1 service connection path: direct `10.4.167.122:8000`, local tunnel `127.0.0.1:18000`, or custom config.
- Reproduction steps, screenshots, logs, or API responses.
- Confirm passwords, tokens, real faces, real videos, and personal information are removed.

## Demo Support Boundary

- Offline mock fallback is part of the GKGuard C2 workbench demo capability.
- Real CampusVision C1 search depends on the server, network, and CampusVision C1 data indexing state.
- CampusCar/UE is currently a placeholder contract and does not mean real vehicle or UE runtime integration is complete.

<p align="right"><a href="#english">Back to English top</a></p>
