import os

import uvicorn

from app.main import app


DESKTOP_BACKEND_HOST = "127.0.0.1"


def main() -> None:
    uvicorn.run(
        app,
        host=DESKTOP_BACKEND_HOST,
        port=int(os.environ.get("GKGUARD_PORT", "8000")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
