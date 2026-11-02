"""Configuration loading, defaults and file locations."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "mail": {
        "mode": "mailapp",
        "account": "iCloud",
        "mailbox": "INBOX",
        "lookback_days": 2,
        "max_messages": 200,
        "max_chars": 20000,
    },
    "reminders": {
        "list": "Email Reminders",
        "max_per_email": 3,
        "notify_on_run": True,
    },
    "parsing": {
        "date_order": "DMY",
        "default_time": "09:00",
        "require_event_keyword": True,
        "max_future_days": 180,
        "same_day_window_hours": 4,
        "keywords": [
            "meeting", "call", "appointment", "deadline", "due", "rsvp",
            "interview", "webinar", "event", "session", "class", "exam",
            "flight", "booking", "reservation", "reminder", "schedule",
            "demo", "presentation", "zoom", "teams", "google meet", "submit",
            "submission", "assignment", "departure", "arrival", "check-in",
            "check in", "party", "dinner", "lunch", "concert", "ticket",
            "registration", "orientation", "lecture", "tutorial", "seminar",
        ],
    },
}


def app_dir() -> Path:
    """Return the per-user data directory for config, state and logs."""
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "mail2reminders"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "mail2reminders"
    return Path.home() / ".config" / "mail2reminders"


def default_config_path() -> Path:
    return app_dir() / "config.json"


def default_state_path() -> Path:
    return app_dir() / "state.json"


def default_log_path() -> Path:
    return app_dir() / "run.log"


def merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Optional[Path] = None, create: bool = True) -> Dict[str, Any]:
    """Load configuration, falling back to defaults for missing keys."""
    config_path = Path(path) if path else default_config_path()
    data: Dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    config = merge(DEFAULTS, data)
    if create and not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return config


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> Path:
    config_path = Path(path) if path else default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return config_path
