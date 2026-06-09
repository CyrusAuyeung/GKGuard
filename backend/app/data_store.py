from functools import lru_cache
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


def _load_json(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def load_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "persons": _load_json("persons.json"),
        "vehicles": _load_json("vehicles.json"),
        "cameras": _load_json("cameras.json"),
        "snapshots": _load_json("snapshots.json"),
        "access_records": _load_json("access_records.json"),
        "alerts": _load_json("alerts.json"),
    }


def refresh_data_cache() -> None:
    load_data.cache_clear()
