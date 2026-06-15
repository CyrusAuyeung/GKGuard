import os

import uvicorn

from app.main import app


def main() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("GKGUARD_HOST", "127.0.0.1"),
        port=int(os.environ.get("GKGUARD_PORT", "8000")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
