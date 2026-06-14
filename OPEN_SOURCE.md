<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 开源与使用声明

GKGuard 当前采用 **source-available / 保留所有权利** 的仓库可见性策略。仓库可用于 GKGuard 项目协作、内容查看、演示运行和维护参考，但这不等同于开源授权。

## 授权状态

- 本仓库没有采用 MIT、Apache-2.0、GPL 等开源许可证。
- 除非仓库所有者另行书面授权，否则不得复制、再分发、转授权、商用、作为竞品服务托管，或将本代码用于其他产品。
- 允许在 GKGuard 项目协作、内容查看、演示运行和团队维护范围内查看、运行和讨论代码。
- 第三方依赖、模型、框架和工具保留其各自许可证；生产部署或再次分发前必须单独核查。

## 数据与隐私边界

不得提交以下内容：

- 真实校园视频、查询图片、抽帧图片、人脸裁剪图。
- SQLite 运行数据库、模型缓存、运行时日志。
- `.env`、服务器密码、SSH 私钥、token、API key。
- 真实姓名、学号/工号、手机号、邮箱、轨迹、车牌、案件详情等个人或敏感信息。

仓库中的 `backend/data/mock/` 仅用于脱敏演示。CampusVision C1 运行数据和真实媒体应保留在受控服务器或受控存储中。

## 发布与运行边界

- Windows 安装包用于 GKGuard C2 桌面演示和项目运行检查。
- 软件可离线使用 mock fallback 演示界面流程。
- 真实 CampusVision C1 检索依赖校园网、VPN、SSH 隧道或服务器直连策略。
- GKGuard 不保存服务器密码；安装版只在软件内 CampusVision C1 连接窗口中接收本次 SSH 连接所需密码，手动排障时也只应输入在系统 PowerShell/SSH 窗口中。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Open Source And Usage Statement

GKGuard currently uses a **source-available / all rights reserved** repository visibility policy. The repository may be used for GKGuard project collaboration, source viewing, demonstration runs, and maintenance reference, but this is not an open-source license grant.

## License Status

- This repository does not use an open-source license such as MIT, Apache-2.0, or GPL.
- Unless the repository owner grants separate written permission, you may not copy, redistribute, sublicense, commercialize, host as a competing service, or use this code in another product.
- You may view, run, and discuss the code within the GKGuard project collaboration, source viewing, demonstration, and team maintenance context.
- Third-party dependencies, models, frameworks, and tools keep their own licenses. Review them separately before production deployment or redistribution.

## Data And Privacy Boundary

Do not commit:

- Real campus videos, query images, extracted frames, or face crops.
- SQLite runtime databases, model caches, or runtime logs.
- `.env` files, server passwords, SSH private keys, tokens, or API keys.
- Real names, student or staff IDs, phone numbers, email addresses, trajectories, license plates, or case details.

Files under `backend/data/mock/` are for desensitized demonstration only. CampusVision C1 runtime data and real media should remain on controlled servers or controlled storage.

## Release And Runtime Boundary

- The Windows installer is intended for GKGuard C2 desktop demonstrations and project runtime checks.
- The app can demonstrate the UI flow offline through mock fallback.
- Real CampusVision C1 search depends on campus network, VPN, SSH tunnel, or direct server access policy.
- GKGuard does not store server passwords. The packaged app accepts the password only in its embedded CampusVision C1 connection window for the current SSH session; during manual troubleshooting, passwords should only be entered in the system PowerShell/SSH window.

<p align="right"><a href="#english">Back to English top</a></p>
