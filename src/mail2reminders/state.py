"""Idempotency state: remember which reminders have already been created."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from .config import default_state_path


class State:
    """A small JSON store keyed by a stable event hash."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_state_path()
        self.data: Dict[str, Any] = {"created": {}, "last_run": None}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except (OSError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, dict):
                self.data = loaded
        self.data.setdefault("created", {})
        self.data.setdefault("last_run", None)

    def is_done(self, key: str) -> bool:
        return key in self.data["created"]

    def mark(self, key: str, meta: Dict[str, Any]) -> None:
        self.data["created"][key] = meta

    def prune(self, days: int = 60) -> None:
        cutoff = datetime.now() - timedelta(days=days)
        kept: Dict[str, Any] = {}
        for key, meta in self.data["created"].items():
            try:
                created = datetime.fromisoformat(meta.get("created_at", ""))
            except (TypeError, ValueError):
                kept[key] = meta
                continue
            if created >= cutoff:
                kept[key] = meta
        self.data["created"] = kept

    def save(self) -> None:
        self.prune()
        self.data["last_run"] = datetime.now().isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
