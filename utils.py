import os
import json
import time
from pathlib import Path
from typing import Any

def ensure_dir(path: str) -> None:
    if not path:
        return
    p = Path(path)
    if p.suffix and not p.name == p.suffix:
        p = p.parent
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        try:
            os.makedirs(str(p), exist_ok=True)
        except Exception:
            pass

def write_json(path: str, payload: Any, ensure_ascii: bool = False, indent: int = 2) -> None:
    try:
        parent = Path(path).parent
        if parent:
            ensure_dir(str(parent))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=ensure_ascii, indent=indent)
    except Exception:
        raise

def now_ts() -> int:
    return int(time.time())