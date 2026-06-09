# GKGuard C2 AI Search Demo

This repository contains the C2 implementation starter for the GKGuard campus security AI search platform.

The first runnable milestone focuses on a standalone backend loop:

1. Load desensitized mock security data.
2. Search people, vehicles, snapshots, access records, and alerts.
3. Upload a query image and return mock image-search matches.
4. Generate a sorted appearance timeline and map-ready points.
5. Simulate a campusCar field-review dispatch.

## Project Structure

```text
backend/
  app/
    main.py
    routers/
    services/
  data/mock/
  tests/
  requirements.txt
docs/
  api_contract.md
  data_dictionary.md
  demo_script.md
```

## Run Locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/demo` for the visual demo dashboard.

Open `http://127.0.0.1:8000/docs` to test the API directly.

## Run Tests

```powershell
cd backend
python -m pytest
```

## Demo Path

Use `p001_target.jpg` or any uploaded file containing the text `p001` in the filename to trigger the main missing-person demo route.

The visual dashboard runs through the same route without requiring a real image file. If no image is selected, it sends a synthetic `p001_target.jpg` request so the core C2 flow can be shown quickly.
