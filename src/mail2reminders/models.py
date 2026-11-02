"""Data models shared across the package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Message:
    """A single email message read from Apple Mail."""

    id: str
    subject: str
    sender: str
    date_received: Optional[datetime]
    content: str


@dataclass
class Event:
    """A date/time mention extracted from a message."""

    due: datetime
    score: int
    phrase: str
    snippet: str
    has_time: bool
    has_keyword: bool
