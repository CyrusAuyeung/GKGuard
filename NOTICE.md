# Notice

GKGuard combines original project code with third-party dependencies and frameworks. This file summarizes important notices for repository users.

## Project Code

GKGuard project code is source-available and all rights reserved unless a separate written license is granted by the repository owner. See [LICENSE](LICENSE) and [OPEN_SOURCE.md](OPEN_SOURCE.md).

## Third-Party Components

The project uses third-party tools and libraries including, but not limited to:

- FastAPI, Starlette, Uvicorn, Pydantic, HTTPX, pytest, PyInstaller.
- Electron and electron-builder.
- CampusVision C1 dependencies listed under `services/campusvision-c1/requirements.txt` and `environment-from-scratch.yml`.
- Model/runtime dependencies used by CampusVision C1, including InsightFace-related packages when installed in the CampusVision C1 environment.

Each third-party component keeps its own license. Before redistribution, production deployment, or public hosting, review dependency licenses and model terms separately.

## Data Notice

Repository data is intended to be mock or desensitized demo data. Real campus media, personal information, model caches, runtime databases, logs, and credentials must not be committed.
