<p align="right">
  <a href="#中文"><kbd>中文</kbd></a>
  <a href="#english"><kbd>English</kbd></a>
</p>

<a id="中文"></a>

# 数据字典

GKGuard C2 当前使用两类数据：

- `backend/data/mock/` 下的本地 mock 或脱敏 demo 数据，用于人员、车辆、快照、告警、审计和 CampusCar 占位流程。
- 通过 `/c1/...` 适配器从 CampusVision C1 获取的真实检索数据，包括关键帧、人脸裁剪图、候选人物和轨迹点。

不要提交 C1 运行数据，例如真实视频、查询图片、抽帧图片、SQLite 数据库、`.env` 或模型缓存。

## persons

- `person_id`：稳定内部 ID。
- `name`：demo 展示名称。
- `student_id`：demo 学生、教师、员工或访客编号。
- `phone`：mock 电话。
- `email`：mock 邮箱。
- `identity_type`：`student`、`faculty`、`staff` 或 `visitor`。
- `department`：demo 院系或部门。
- `avatar_url`：占位头像 URL。
- `risk_tags`：规则或 demo 标签。

真实部署中的敏感字段：姓名、学号/工号、电话、邮箱、头像。

## vehicles

- `vehicle_id`：稳定车辆 ID。
- `plate_number`：demo 车牌号。
- `vehicle_type`：`sedan`、`suv`、`van` 或 `campusCar`。
- `brand`：demo 品牌。
- `color`：车身颜色。
- `plate_color`：车牌颜色。
- `owner_person_id`：关联人员 ID。

真实部署中的敏感字段：车牌号和车主关联。

## cameras

- `camera_id`：摄像头 ID。
- `name`：展示名称。
- `location_name`：校园位置。
- `lat`：地图纬度。
- `lng`：地图经度。
- `type`：固定枪机、球机、厂商类型或其他来源。

## snapshots

- `snapshot_id`：稳定快照 ID。
- `person_id`：已知时关联人员。
- `vehicle_id`：已知时关联车辆。
- `camera_id`：来源摄像头。
- `time`：ISO 时间。
- `image_url`：占位快照 URL。
- `mock_similarity`：demo 相似度。
- `feature_tags`：人体、车辆或场景标签。

真实部署中的敏感字段：人脸图、人体图、车牌图、人员关联、车辆关联。

## c1_search_result

- `source`：当前为 `c1`。
- `baseUrl`：适配器当前使用或展示的 C1 地址。
- `selectedBaseUrl`：自动探测后选中的健康 C1 地址，可能为内置服务器地址 `http://10.4.167.122:8000`、本机隧道地址 `http://127.0.0.1:18000` 或自定义地址。
- `candidateUrls`：本次探测的 C1 候选地址列表。
- `searchId`：C1 search ID。
- `engine`：C1 引擎名，预期为 `insightface`。
- `warning`：低置信或歧义提示。
- `ambiguous`：候选集是否歧义。
- `person`：当前 UI 选中的候选人物。
- `records`：C2 结果页使用的关键帧记录。
- `routePoints`：C2 路线页使用的地图轨迹点。
- `appearanceEvents`：C1 连续出现事件，保留给后续更丰富时间线。
- `raw`：C1 原始 payload，用于调试和后续映射。

真实部署中的敏感字段：人脸图、帧图、人员关联、移动轨迹和相似度分数。

## c1_records

- `id`：本地展示序号。
- `title`：如 `记录1`。
- `time`：紧凑时间；C1 没有捕获时间时可能为 `--:--:--`。
- `fullTime`：完整时间；C1 没有捕获时间时可能为 `未知时间`。
- `location`：C1 位置或摄像头标签。
- `camera`：摄像头展示名。
- `cameraId`：C1 摄像头 ID。
- `similarity`：C1 归一化分数。
- `note`：C2 展示说明。
- `frameUrl`：C2 代理媒体 URL，通常为 `/c1/media/frame/{face_id}`。
- `faceId`：C1 face record ID。
- `videoId`：C1 video ID。
- `videoTimestampSec`：源视频内时间戳。

## c1_route_points

- `id`：本地展示序号。
- `time`：路线时间线展示时间。
- `location`：C1 位置或摄像头标签。
- `x`、`y`：当前 C2 地图展示坐标，由适配器生成。
- `kind`：可选 `start` 或 `end`。
- `cameraId`：C1 摄像头 ID。
- `score`：可用时的 C1 命中分数。

## access_records

- `record_id`：门禁记录 ID。
- `person_id`：关联人员。
- `location`：门或出入口。
- `time`：ISO 时间。
- `direction`：进或出。

真实部署中的敏感字段：人员行动历史。

## alerts

- `alert_id`：告警 ID。
- `person_id`：相关人员。
- `vehicle_id`：相关车辆。
- `alert_type`：告警类型。
- `time`：ISO 时间。
- `location`：事件位置。
- `status`：`open` 或 `closed`。
- `severity`：`low`、`medium`、`high`。
- `description`：demo 事件描述。

真实部署中的敏感字段：事件对象、案件描述、处置状态。

## audit logs

- `audit_id`：生成的审计 ID。
- `time`：ISO 时间。
- `actor`：demo 操作员或处理人。
- `action`：敏感操作名。
- `target`：事件、报告、处置或查询对象。
- `metadata`：非敏感操作细节。

审计日志写入 `backend/runtime/audit.jsonl`，该目录已被 Git 忽略。

## campusCar review tasks

- `task_id`：现场复核任务 ID。
- `car_id`：mock 任务使用的 CampusCar ID。
- `event_id`：关联告警或案件。
- `route_id`：巡逻路线或未来导航计划。
- `location`：目标位置标签。
- `status`：当前 mock 为 `arrived_mock`。
- `start_time`：mock 任务创建时间。
- `end_time`：mock 任务完成时间。
- `snapshot_url`：占位复核图片 URL。
- `bridge_contract`：未来 CampusCar/UE 映射元数据。
- `video_hls_url`：未来浏览器播放流。
- `video_rtsp_url`：未来原始相机流。

## UE bridge contract

- `integration_id`：稳定集成名，当前为 `ue-campuscar`。
- `mode`：`mock`、`external_ue_test_app` 或未来 `live`。
- `rosbridge_url`：预期 rosbridge WebSocket 地址。
- `command_topic`：UE Bridge 命令 topic，`/U2RTopic_Command`。
- `position_topic`：位姿反馈 topic，`/R2UTopic_Pos`。
- `status_topic`：文本/状态反馈 topic，`/R2UTopic_Text`。
- `video_hls_url`：未来 HLS 流地址。
- `video_rtsp_url`：未来 RTSP 流地址。
- `notes`：人工交接说明。

<p align="right"><a href="#中文">返回中文顶部</a></p>

---

<a id="english"></a>

# Data Dictionary

GKGuard C2 currently uses two classes of data:

- Local mock or desensitized demo data under `backend/data/mock/` for people, vehicles, snapshots, alerts, audit logs, and CampusCar placeholders.
- Real CampusVision C1 search data returned through `/c1/...` adapter endpoints, including keyframes, face crops, candidate persons, and route points.

Do not commit C1 runtime data such as real videos, query images, extracted frames, SQLite databases, `.env`, or model caches.

## persons

- `person_id`: stable internal ID.
- `name`: demo display name.
- `student_id`: demo student, faculty, staff, or visitor identifier.
- `phone`: mock phone number.
- `email`: mock email.
- `identity_type`: `student`, `faculty`, `staff`, or `visitor`.
- `department`: demo department or office.
- `avatar_url`: placeholder avatar URL.
- `risk_tags`: rule or demo tags.

Sensitive in real deployments: name, student or staff ID, phone, email, and avatar.

## vehicles

- `vehicle_id`: stable vehicle ID.
- `plate_number`: demo plate number.
- `vehicle_type`: `sedan`, `suv`, `van`, or `campusCar`.
- `brand`: demo brand.
- `color`: body color.
- `plate_color`: plate color.
- `owner_person_id`: linked person ID.

Sensitive in real deployments: plate number and owner link.

## cameras

- `camera_id`: camera ID.
- `name`: display name.
- `location_name`: campus location.
- `lat`: latitude for map rendering.
- `lng`: longitude for map rendering.
- `type`: fixed box, dome, vendor type, or other source type.

## snapshots

- `snapshot_id`: stable snapshot ID.
- `person_id`: linked person when known.
- `vehicle_id`: linked vehicle when known.
- `camera_id`: source camera.
- `time`: ISO timestamp.
- `image_url`: placeholder snapshot URL.
- `mock_similarity`: demo similarity score.
- `feature_tags`: body, vehicle, or scene tags.

Sensitive in real deployments: face image, body image, plate image, person link, and vehicle link.

## c1_search_result

- `source`: currently `c1`.
- `baseUrl`: C1 URL currently used or displayed by the adapter.
- `selectedBaseUrl`: healthy C1 URL selected by auto-probing. It may be the built-in server URL `http://10.4.167.122:8000`, the local tunnel URL `http://127.0.0.1:18000`, or a custom URL.
- `candidateUrls`: C1 candidate URL list checked during the probe.
- `searchId`: C1 search ID.
- `engine`: C1 engine name, expected to be `insightface`.
- `warning`: low-confidence or ambiguity warning.
- `ambiguous`: whether the candidate set is ambiguous.
- `person`: selected candidate person for the current UI.
- `records`: keyframe records used by the C2 result screen.
- `routePoints`: map-ready route points used by the C2 route screen.
- `appearanceEvents`: C1 appearance events retained for a richer future timeline.
- `raw`: original C1 payload for debugging and future mapping.

Sensitive in real deployments: face images, frame images, person links, movement trajectory, and similarity scores.

## c1_records

- `id`: local display sequence.
- `title`: for example `记录1`.
- `time`: compact display time; may be `--:--:--` if C1 has no captured timestamp.
- `fullTime`: full display time; may be `未知时间` if C1 has no captured timestamp.
- `location`: C1 location or camera label.
- `camera`: camera display name.
- `cameraId`: C1 camera ID.
- `similarity`: normalized C1 score.
- `note`: C2 display note.
- `frameUrl`: C2 proxy media URL, usually `/c1/media/frame/{face_id}`.
- `faceId`: C1 face record ID.
- `videoId`: C1 video ID.
- `videoTimestampSec`: timestamp within the source video.

## c1_route_points

- `id`: local display sequence.
- `time`: display time used by the route timeline.
- `location`: C1 location or camera label.
- `x`, `y`: current C2 map display coordinates generated by the adapter.
- `kind`: optional `start` or `end`.
- `cameraId`: C1 camera ID.
- `score`: C1 match score when available.

## access_records

- `record_id`: access record ID.
- `person_id`: linked person.
- `location`: door or gate.
- `time`: ISO timestamp.
- `direction`: in or out.

Sensitive in real deployments: movement history.

## alerts

- `alert_id`: alert ID.
- `person_id`: linked person.
- `vehicle_id`: linked vehicle.
- `alert_type`: alert category.
- `time`: ISO timestamp.
- `location`: event location.
- `status`: `open` or `closed`.
- `severity`: `low`, `medium`, or `high`.
- `description`: demo event text.

Sensitive in real deployments: event subjects, case description, and handling status.

## audit logs

- `audit_id`: generated audit entry ID.
- `time`: ISO timestamp.
- `actor`: demo operator or handler.
- `action`: sensitive action name.
- `target`: event, report, disposition, or query target.
- `metadata`: non-sensitive action details.

Audit logs are written to `backend/runtime/audit.jsonl`, which is ignored by Git.

## campusCar review tasks

- `task_id`: field-review task ID.
- `car_id`: CampusCar ID used by the mock task.
- `event_id`: linked alert or case.
- `route_id`: patrol route or future navigation plan.
- `location`: target location label.
- `status`: currently `arrived_mock` in demo mode.
- `start_time`: mock task creation time.
- `end_time`: mock task completion time.
- `snapshot_url`: placeholder review image URL.
- `bridge_contract`: future CampusCar/UE mapping metadata.
- `video_hls_url`: future browser-playable stream.
- `video_rtsp_url`: future raw camera stream.

## UE bridge contract

- `integration_id`: stable integration name, currently `ue-campuscar`.
- `mode`: `mock`, `external_ue_test_app`, or future `live`.
- `rosbridge_url`: expected rosbridge WebSocket endpoint.
- `command_topic`: UE Bridge command topic, `/U2RTopic_Command`.
- `position_topic`: pose feedback topic, `/R2UTopic_Pos`.
- `status_topic`: text/status feedback topic, `/R2UTopic_Text`.
- `video_hls_url`: future HLS stream URL.
- `video_rtsp_url`: future RTSP stream URL.
- `notes`: human-readable handoff notes.

<p align="right"><a href="#english">Back to English top</a></p>
