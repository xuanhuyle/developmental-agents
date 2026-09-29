"""Append-only event log (JSONL). Every metric in evals/metrics.py is derived from these events."""

from __future__ import annotations

import json
import time
from pathlib import Path

EVENT_TYPES = {
    "RUN_STARTED", "AGENT_CREATED", "ACTION_STARTED", "ACTION_COMPLETED", "INFORMATION_QUERIED",
    "MESSAGE_SENT", "AGENT_SPAWNED", "RESOURCE_ALLOCATED", "RESOURCE_CONSUMED", "AGENT_TERMINATED",
    "RUN_COMPLETED",
}


class EventLog:
    def __init__(self, run_id: str, path: Path | None = None):
        self.run_id = run_id
        self.events: list[dict] = []
        self._fh = None
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(path, "a", encoding="utf-8")

    def emit(self, type: str, t: float, **fields) -> dict:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type}")
        event = {"seq": len(self.events), "run_id": self.run_id, "type": type, "t": round(t, 6),
                 "wall": time.time(), **fields}
        self.events.append(event)
        if self._fh is not None:
            self._fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        return event

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def read_events(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
