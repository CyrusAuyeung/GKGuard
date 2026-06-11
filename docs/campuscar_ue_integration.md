# CampusCar / UE Integration Contract

This document records the integration boundary discovered from the initial materials, the UE test module, and the control group slides.

## Scope

GKGuard remains the C2 workbench for AI search, timeline analysis, event disposition, evidence export, and operator handoff. CampusCar, ROS2, UE, and the low-level chassis stack stay outside the GKGuard desktop package.

GKGuard should provide:

- A stable field-review task contract.
- A clear mapping from event disposition to CampusCar command intent.
- Status placeholders for UE/ROS bridge readiness.
- HLS/RTSP/video URL placeholders for future review evidence.

GKGuard should not provide:

- STM32 serial control.
- ROS2 node ownership inside the desktop app.
- Unreal Engine runtime packaging.
- Direct dependency on `GKD_Station_Qiyi.exe`.

## External Signals

The control group material identifies the UE Bridge workflow as:

- Command publish topic: `/U2RTopic_Command`
- Position feedback topic: `/R2UTopic_Pos`
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

The adapter service can be a separate Python/ROS2 process later. It should translate GKGuard review tasks into ROS messages and translate vehicle/UE feedback back into task status.

## Contract Mapping

| GKGuard concept | Future integration target |
| --- | --- |
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

`POST /car-tasks/mock-dispatch` stays mock-only. It now echoes the integration fields and returns a `bridge_contract` block so the frontend and other groups can see exactly where real services will plug in.

`GET /car-tasks/ue-bridge-status` returns a deterministic mock readiness object for UI and demos. It does not check a real rosbridge process yet.

## Future Replacement Plan

1. Keep `/car-tasks/mock-dispatch` for offline demos.
2. Add a real adapter endpoint only after control/UE teams provide stable message schemas.
3. Map event task creation to `/U2RTopic_Command` in the adapter.
4. Subscribe to `/R2UTopic_Pos` and `/R2UTopic_Text` in the adapter.
5. Store returned pose/status snapshots as evidence linked to the original `event_id`.
6. Surface HLS/RTSP/MJPEG links in the CampusCar panel when the video service is available.