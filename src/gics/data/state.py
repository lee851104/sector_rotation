"""Atomic local checkpoints. Workflows serialize writers and persist this directory."""

import json
import os
from datetime import timezone
from pathlib import Path


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(data, encoding="utf-8")
    os.replace(temporary, path)


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, path: Path, limit=800, reserve=20):
        self.path, self.limit, self.buffer = path, limit, reserve

    def reserve(self, now):
        day = now.astimezone(timezone.utc).date().isoformat()
        state = read_json(self.path)
        if state.get("day") != day:
            state = {"day": day, "used": 0}
        if state["used"] >= self.limit - self.buffer:
            raise BudgetExceeded("Daily API budget exhausted; retry after UTC reset")
        state["used"] += 1
        write_json(self.path, state)

    def available(self, now):
        state = read_json(self.path)
        used = (
            state.get("used", 0)
            if state.get("day") == now.astimezone(timezone.utc).date().isoformat()
            else 0
        )
        return max(0, self.limit - self.buffer - used)
