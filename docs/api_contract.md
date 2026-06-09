# API Contract

Base URL during local development: `http://127.0.0.1:8000`

## System

`GET /health`

Returns service status.

## Person Search

`GET /search/persons`

Query parameters:

- `keyword`
- `name`
- `student_id`
- `phone`
- `email`
- `identity_type`

Returns matching person records.

## Person Profile

`GET /search/persons/{person_id}/profile`

Returns person base info, linked vehicles, snapshots, access records, and alerts.

## Vehicle Search

`GET /search/vehicles`

Query parameters:

- `keyword`
- `plate_number`
- `color`
- `brand`
- `vehicle_type`
- `owner_person_id`

Returns matching vehicles.

## Snapshot Records

`GET /search/records`

Query parameters:

- `person_id`
- `vehicle_id`
- `camera_id`
- `location`
- `start_time`
- `end_time`
- `min_similarity`

Returns camera snapshot records enriched with camera name, location, and map coordinates.

## Image Search

`POST /search/image`

Multipart form field:

- `file`: query image

Query parameters:

- `top_k`: default `5`
- `min_similarity`: default `0.72`

Returns Top-K mock image-search matches. This endpoint is designed so the mock logic can later be replaced by CLIP, InsightFace, DeepFace, or another embedding service.

## Timeline

`GET /persons/{person_id}/timeline`

Query parameters:

- `start_time`
- `end_time`
- `min_similarity`

Returns sorted timeline points and a summary with first seen, last seen, last location, camera count, and related alert count.

## Event Records

`GET /events/{event_id}/related-records`

Returns alert detail, related snapshots, optional person timeline, and a text summary.

## Event Report

`GET /events/{event_id}/report`

Returns a structured case report with key findings, recommended actions, evidence IDs, and a disposition template.

## Mock campusCar Dispatch

`POST /car-tasks/mock-dispatch`

Body:

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "route_id": "ROUTE-DEMO-01",
  "reason": "field_review"
}
```

Returns a mock task with `task_id`, `car_id`, `status`, `start_time`, `end_time`, and `snapshot_url`.

## Lightweight AI Parser

`POST /ai/parse-query`

Body:

```json
{
  "query": "find red car near parking at night"
}
```

Returns rule-based filters that can be mapped into search parameters.
