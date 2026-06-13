# C1 / C2 Integration Notes

GKGuard keeps the C2 command-and-control shell in the root backend and desktop app, while the C1 video retrieval service is imported under `services/campusvision-c1/`.

## Ownership

- C1 (`services/campusvision-c1/`): video upload, frame sampling, face embedding, person indexing, image search, timeline output, and frame media access.
- C2 (`backend/`, `desktop/`): search console, investigation workflow, event handling, evidence packaging, audit trail, and CampusCar / UE bridge placeholders.

## Current C1 Source

The imported C1 snapshot came from the team server project path:

```text
/home/<c1-user>/projects/campusvision-c1
```

Only source, documentation, scripts, examples, dependency files, and `.env.example` are intended to be tracked. Runtime data, real videos, query images, extracted frames, SQLite files, model caches, `.env`, and Python caches must remain untracked.

## Expected C1 API

C2 should treat C1 as an external service with this base URL during local development:

```text
http://127.0.0.1:8000
```

If C1 runs on a remote server bound to `127.0.0.1`, use an SSH tunnel from the C2 machine:

```powershell
ssh -L 8000:127.0.0.1:8000 <user>@<c1-server>
```

Then C2 can call `http://127.0.0.1:8000` without exposing the C1 service on the network.

## Data Mapping

| C1 field | C2 target |
|---|---|
| `matches[]` | snapshot / capture records |
| `trajectory[]` | map-ready trajectory points |
| `appearance_events[]` | timeline event segments |
| `frame_url` / `best_frame_url` | evidence image URL |
| `camera_id`, `camera_name` | camera identity |
| `location`, `lat`, `lng` | place and map position |
| `score`, `best_score` | search confidence |
| `captured_at`, `time_display` | event time display |

## Adapter Plan

The C2 backend should keep its current mock fallback and introduce a C1 adapter boundary later:

```text
C1_BASE_URL -> health check -> image search -> normalize result -> existing C2 view model
```

Recommended adapter behavior:

- Return mock data when C1 is not configured or `/health` is unavailable.
- Normalize C1 `matches`, `trajectory`, and `appearance_events` into the current GKGuard response shape.
- Prefix relative C1 media URLs with `C1_BASE_URL` before showing frames in the C2 UI.
- Surface a frontend status state: `Mock`, `C1 reachable`, or `C1 error`.

## Handoff Checklist

- C1 confirms the official service port and whether it is bound to `127.0.0.1` or `0.0.0.0`.
- C1 `/health` returns HTTP 200 with InsightFace loaded.
- C1 completes one full flow: create camera, upload video, index video, search by image.
- C1 provides a safe demo video and query image policy before any media enters this repository.
- C2 verifies that returned `frame_url` images can be opened through the chosen base URL or SSH tunnel.