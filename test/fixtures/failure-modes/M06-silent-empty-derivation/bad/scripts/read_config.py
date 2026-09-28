import json
from pathlib import Path


def read_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
