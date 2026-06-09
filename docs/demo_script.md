# Demo Script

## Goal

Demonstrate the C2 loop: upload image, find related camera snapshots, build a timeline, review alert context, and create a mock campusCar dispatch.

## Demo Steps

1. Start the backend.

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

1. Open the visual demo dashboard.

```text
http://127.0.0.1:8000/demo
```

1. Open API docs if direct endpoint testing is needed.

```text
http://127.0.0.1:8000/docs
```

1. Search the demo person.

```text
GET /search/persons?student_id=S2026001
```

Expected result: `P001`, the main missing-person demo subject.

1. Upload an image to image search.

```text
POST /search/image?top_k=5&min_similarity=0.8
file: p001_target.jpg
```

Expected result: Top-K matches for `P001`, including Main Gate North, Library West, Canteen Entrance, and Dorm East Gate records.

1. Generate the timeline.

```text
GET /persons/P001/timeline?min_similarity=0.9
```

Expected result: sorted appearance records and last location `Dorm East Gate`.

1. Review the alert.

```text
GET /events/ALT-001/related-records
```

Expected result: alert detail, related snapshots, timeline, and summary.

1. Create a mock campusCar review task.

```text
POST /car-tasks/mock-dispatch
```

Body:

```json
{
  "event_id": "ALT-001",
  "target_location": "Dorm East Gate",
  "reason": "field review"
}
```

Expected result: task status `arrived_mock` with a mock snapshot URL.

1. Generate a case report.

```text
GET /events/ALT-001/report
```

Expected result: a structured report with key findings, recommended actions, evidence IDs, and a disposition template.

## Handoff Notes

- Frontend can consume the timeline `points` list directly for map markers and route lines.
- B group can later replace `/car-tasks/mock-dispatch` with a real campusCar bridge while keeping the same field names.
- The image-search implementation is intentionally replaceable. Keep the endpoint contract stable when adding a real model.
