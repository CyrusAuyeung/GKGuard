<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# CampusCar / UE 集成规范

本文记录从初期材料、UE 测试模块和 B组嵌入式控制材料中整理出的集成边界。当前 GKGuard 只实现 C组算法感知侧的 GKGuard C2 占位接口规范，不打包 UE 运行时，也不直接接管 ROS2 或底盘控制。

## 范围

GKGuard 仍是 GKGuard C2 工作台，负责 AI 检索、轨迹分析、事件处置、证据导出和操作员处理流程。CampusCar、ROS2、UE 和底盘控制栈保持在 GKGuard 桌面包之外。

GKGuard 应提供：

- 稳定的现场复核任务接口规范。
- 从事件处置到 CampusCar 命令意图的字段映射。
- UE/ROS 桥接准备状态占位。
- 后续复核证据使用的 HLS/RTSP/video URL 占位。

GKGuard 不应提供：

- STM32 串口控制。
- 桌面应用内的 ROS2 节点所有权。
- Unreal Engine 运行时打包。
- 对 `GKD_Station_Qiyi.exe` 的直接依赖。

## 外部信号

B组嵌入式控制材料给出的 UE Bridge 流程包括：

- 命令发布话题：`/U2RTopic_Command`
- 位姿反馈话题：`/R2UTopic_Pos`
- 文本/状态反馈话题：`/R2UTopic_Text`
- 目标：命令下发、位姿返回、状态通知，以及真实车辆到数字校园的闭环。

UE 测试模块是一个 Windows UE5 打包应用，包含 `ROSIntegration` 插件和 `TestRos`、`BP_RosTopic` 等测试资产。其 `Bridge.ini` 为空，因此当前包没有可直接编辑的运行连接参数。

## 运行边界

推荐部署形态：

```text
GKGuard C2 UI
  -> FastAPI /car-tasks/mock-dispatch 或未来 /car-tasks/dispatch
  -> CampusCar adapter service
  -> rosbridge / ROS2 Humble
  -> UE Bridge 话题与真实车辆栈
```

未来适配服务可以是独立 Python/ROS2 进程。它负责把 GKGuard 复核任务转换为 ROS 消息，并把车辆/UE 反馈转换回 GKGuard C2 任务状态。

## 字段映射

| GKGuard 概念 | 未来集成目标 |
|---|---|
| `event_id` | 案件或告警关联 ID |
| `target_location` | 目的地标签或 waypoint 查询键 |
| `route_id` | 巡逻路线或导航计划 ID |
| `reason` | 操作员意图，例如现场复核 |
| `robot_id` | CampusCar 车辆 ID |
| `robot_type` | `campusCar` |
| `speed_mps` | 建议导航速度 |
| `command_topic` | `/U2RTopic_Command` |
| `position_topic` | `/R2UTopic_Pos` |
| `status_topic` | `/R2UTopic_Text` |
| `video_hls_url` | 未来实时复核视频流 |
| `video_rtsp_url` | 未来原始相机流 |

## 当前模拟行为

`POST /car-tasks/mock-dispatch` 保持仅模拟行为。它会回显集成字段，并返回 `bridge_contract`，方便 C组算法感知前端和 B组嵌入式控制明确真实服务未来接入点。

`GET /car-tasks/ue-bridge-status` 返回确定性的模拟就绪状态对象，用于 UI 和演示。它当前不检查真实 rosbridge 进程。

## 后续替换计划

1. 保留 `/car-tasks/mock-dispatch` 用于离线演示。
2. B组嵌入式控制提供稳定消息格式后，再新增真实适配接口。
3. 在适配器中把事件任务创建映射到 `/U2RTopic_Command`。
4. 在适配器中订阅 `/R2UTopic_Pos` 和 `/R2UTopic_Text`。
5. 将返回的位姿和状态快照作为证据关联到原始 `event_id`。
6. 视频服务可用后，在 CampusCar 面板展示 HLS/RTSP/MJPEG 链接。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# CampusCar / UE Integration Specification

This document records the integration boundary discovered from the initial materials, the UE test module, and Group B embedded-control materials. GKGuard currently implements only the Group C algorithm-perception side of the GKGuard C2 placeholder API specification. It does not package the UE runtime and does not directly own ROS2 or chassis control.

## Scope

GKGuard remains the GKGuard C2 workbench for AI search, trajectory analysis, event disposition, evidence export, and operator review workflows. CampusCar, ROS2, UE, and the low-level chassis stack remain outside the GKGuard desktop package.

GKGuard should provide:

- A stable field-review task interface specification.
- A field mapping from event disposition to CampusCar command intent.
- Placeholder readiness status for UE/ROS bridge.
- Placeholder HLS/RTSP/video URLs for future review evidence.

GKGuard should not provide:

- STM32 serial control.
- ROS2 node ownership inside the desktop app.
- Unreal Engine runtime packaging.
- Direct dependency on `GKD_Station_Qiyi.exe`.

## External Signals

The Group B embedded-control material identifies the UE Bridge workflow as:

- Command publish topic: `/U2RTopic_Command`
- Pose feedback topic: `/R2UTopic_Pos`
- Text/status feedback topic: `/R2UTopic_Text`
- Goal: command dispatch, pose return, status notification, and a real vehicle to digital campus loop.

The UE test module is a packaged Windows UE5 application with the `ROSIntegration` plugin and test assets such as `TestRos` and `BP_RosTopic`. Its `Bridge.ini` is empty, so runtime connection parameters are not currently exposed as editable configuration in the package.

## Runtime Boundary

Recommended deployment shape:

```text
GKGuard C2 UI
  -> FastAPI /car-tasks/mock-dispatch or future /car-tasks/dispatch
  -> CampusCar adapter service
  -> rosbridge / ROS2 Humble
  -> UE Bridge topics and real vehicle stack
```

The future adapter service can be a separate Python/ROS2 process. It should translate GKGuard review tasks into ROS messages and translate vehicle/UE feedback back into GKGuard C2 task status.

## Specification Mapping

| GKGuard concept | Future integration target |
|---|---|
| `event_id` | Case or alert correlation ID |
| `target_location` | Destination label or waypoint lookup key |
| `route_id` | Patrol route or navigation plan ID |
| `reason` | Operator intent, e.g. field review |
| `robot_id` | CampusCar vehicle ID |
| `robot_type` | `campusCar` |
| `speed_mps` | Suggested navigation speed |
| `command_topic` | `/U2RTopic_Command` |
| `position_topic` | `/R2UTopic_Pos` |
| `status_topic` | `/R2UTopic_Text` |
| `video_hls_url` | Future live review stream URL |
| `video_rtsp_url` | Future raw camera stream URL |

## Current Mock Behavior

`POST /car-tasks/mock-dispatch` stays mock-only. It echoes integration fields and returns a `bridge_contract` block so the Group C algorithm-perception frontend and Group B embedded-control integration can see exactly where real services will plug in.

`GET /car-tasks/ue-bridge-status` returns a deterministic mock readiness object for UI and demos. It does not check a real rosbridge process yet.

## Future Replacement Plan

1. Keep `/car-tasks/mock-dispatch` for offline demos.
2. Add a real adapter endpoint only after Group B embedded control provides stable message schemas.
3. Map event task creation to `/U2RTopic_Command` in the adapter.
4. Subscribe to `/R2UTopic_Pos` and `/R2UTopic_Text` in the adapter.
5. Store returned pose/status snapshots as evidence linked to the original `event_id`.
6. Surface HLS/RTSP/MJPEG links in the CampusCar panel when the video service is available.

<p align="right"><a href="#english">Back to English top</a></p>
