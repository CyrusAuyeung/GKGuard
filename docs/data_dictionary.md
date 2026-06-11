# Data Dictionary

All current data is mock or desensitized demo data.

## persons

- `person_id`: stable internal ID.
- `name`: demo display name.
- `student_id`: demo student, faculty, staff, or visitor identifier.
- `phone`: mock phone number.
- `email`: mock email.
- `identity_type`: `student`, `faculty`, `staff`, or `visitor`.
- `department`: demo department or office.
- `avatar_url`: placeholder image URL.
- `risk_tags`: rule or demo tags.

Sensitive in real deployment: name, student ID, phone, email, avatar.

## vehicles

- `vehicle_id`: stable internal ID.
- `plate_number`: demo plate number.
- `vehicle_type`: sedan, suv, van, or campusCar.
- `brand`: demo brand.
- `color`: body color.
- `plate_color`: plate color.
- `owner_person_id`: linked person ID.

Sensitive in real deployment: plate number and owner link.

## cameras

- `camera_id`: camera ID.
- `name`: display name.
- `location_name`: campus location.
- `lat`: latitude for map rendering.
- `lng`: longitude for map rendering.
- `type`: fixed box, smart dome, Dahua fixed, or other source type.

## snapshots

- `snapshot_id`: stable snapshot ID.
- `person_id`: linked person ID when known.
- `vehicle_id`: linked vehicle ID when known.
- `camera_id`: source camera.
- `time`: ISO timestamp.
- `image_url`: placeholder snapshot URL.
- `mock_similarity`: demo similarity score.
- `feature_tags`: simple body, vehicle, or scene tags.

Sensitive in real deployment: face image, body image, plate image, person link, vehicle link.

## access_records

- `record_id`: access record ID.
- `person_id`: linked person.
- `location`: door or gate.
- `time`: ISO timestamp.
- `direction`: in or out.

Sensitive in real deployment: person movement history.

## alerts

- `alert_id`: alert ID.
- `person_id`: linked person when relevant.
- `vehicle_id`: linked vehicle when relevant.
- `alert_type`: alert category.
- `time`: ISO timestamp.
- `location`: event location.
- `status`: open or closed.
- `severity`: low, medium, high.
- `description`: demo event text.

Sensitive in real deployment: event subjects, case description, handling status.

## audit logs

- `audit_id`: generated audit entry ID.
- `time`: ISO timestamp.
- `actor`: demo operator or handler.
- `action`: sensitive action name.
- `target`: event, report, disposition, or query target.
- `metadata`: non-sensitive action details.

Audit logs are written to `backend/runtime/audit.jsonl`, which is ignored by Git.

## campusCar review tasks

- `task_id`: generated field-review task ID.
- `car_id`: CampusCar vehicle ID used by the mock task.
- `event_id`: linked alert or case ID.
- `route_id`: planned patrol route or future navigation plan.
- `location`: target location label.
- `status`: current task status, currently `arrived_mock` in demo mode.
- `start_time`: mock task creation time.
- `end_time`: mock task completion time.
- `snapshot_url`: placeholder review image URL.
- `bridge_contract`: future CampusCar/UE mapping metadata.
- `video_hls_url`: future browser-playable review stream.
- `video_rtsp_url`: future raw camera stream.

## UE bridge contract

- `integration_id`: stable integration name, currently `ue-campuscar`.
- `mode`: `mock`, `external_ue_test_app`, or future `live`.
- `rosbridge_url`: expected rosbridge WebSocket endpoint.
- `command_topic`: UE Bridge command topic, `/U2RTopic_Command`.
- `position_topic`: UE Bridge pose feedback topic, `/R2UTopic_Pos`.
- `status_topic`: UE Bridge text/status feedback topic, `/R2UTopic_Text`.
- `video_hls_url`: future HLS stream URL for the C2 UI.
- `video_rtsp_url`: future RTSP stream URL for adapter or native clients.
- `notes`: human-readable integration handoff notes.
