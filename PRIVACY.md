<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 隐私与数据处理说明

GKGuard 当前用于校园安防 AI 检索演示和项目交接。仓库默认只包含 mock 或脱敏数据，不应包含真实个人信息或真实媒体。

## 数据类型

当前仓库可能涉及：

- mock 人员、车辆、摄像头、快照、告警和审计记录。
- C1 返回的人脸检索结果、关键帧、人脸裁剪图、轨迹点和相似度。
- 桌面端连接 C1 所需的服务器地址、端口和 SSH 隧道配置。

## 仓库内允许的数据

- 脱敏 mock 数据。
- 不包含真实身份的接口示例。
- `.env.example` 和示例配置。
- 不含凭据的文档和脚本。

## 仓库内禁止的数据

- 真实姓名、学号/工号、手机号、邮箱、车牌号。
- 真实人脸图、视频、抽帧图片、人脸裁剪图。
- 真实轨迹、案件材料、门禁历史和处置记录。
- 密码、token、SSH 私钥、API key、真实 `.env`。
- C1 SQLite 数据库、模型缓存和运行日志。

## 运行时处理

- C2 桌面端默认启动本地后端，并可通过 C1 自动连接策略访问服务器服务。
- 用户输入的 SSH 密码只进入系统 PowerShell/SSH 窗口，GKGuard 不保存、不读取、不记录。
- C1 真实数据应保存在受控服务器或受控存储中，不进入 Git 仓库。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Privacy And Data Handling

GKGuard is currently used for campus security AI search demonstrations and project handoff. The repository should contain only mock or desensitized data by default, not real personal information or real media.

## Data Types

The project may involve:

- Mock people, vehicles, cameras, snapshots, alerts, and audit records.
- C1 face-search results, keyframes, face crops, route points, and similarity scores.
- Server address, port, and SSH tunnel configuration needed by the desktop app to reach C1.

## Allowed In The Repository

- Desensitized mock data.
- API examples without real identities.
- `.env.example` and example configuration.
- Documentation and scripts without credentials.

## Not Allowed In The Repository

- Real names, student/staff IDs, phone numbers, email addresses, or license plates.
- Real face images, videos, extracted frames, or face crops.
- Real trajectories, case material, access history, or disposition records.
- Passwords, tokens, SSH private keys, API keys, or real `.env` files.
- C1 SQLite databases, model caches, or runtime logs.

## Runtime Handling

- The C2 desktop app starts a local backend and can reach the server-side C1 through the auto-connection strategy.
- SSH passwords are entered only in the system PowerShell/SSH window. GKGuard does not store, read, or log them.
- Real C1 data should stay on controlled servers or controlled storage and must not enter the Git repository.

<p align="right"><a href="#english">Back to English top</a></p>
