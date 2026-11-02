"""Rule-based extraction of dates and times from email text.

The parser works on plain text (HTML already stripped) and returns a list of
:class:`~mail2reminders.models.Event` objects. It is deliberately
deterministic: every decision can be traced back to a regex match, which
makes it testable and easy to tune via configuration.
"""

from __future__ import annotations

import html as html_mod
import re
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from .models import Event

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

MONTH_RE = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)"
)

_QUOTE_MARKERS = [
    r"\n\s*On .{0,200}wrote:\s*\n",
    r"\n-{2,}\s*Original Message\s*-{2,}",
    r"\n\s*From:\s.+\n\s*Sent:\s",
    r"\n\s*-{5,}\s*Forwarded message\s*-{5,}",
]


def strip_quoted(text: str) -> str:
    """Drop quoted reply chains so older dates do not leak into results."""
    for pattern in _QUOTE_MARKERS:
        match = re.search(pattern, text, re.I)
        if match:
            text = text[: match.start()]
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(lines)


def clean_text(raw: str) -> str:
    """Strip HTML, entities and quoted history from a message body."""
    text = raw or ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = strip_quoted(text)
    text = (text.replace("\u00a0", " ")
                .replace("\u2013", "-")
                .replace("\u2014", "-")
                .replace("\u2026", "...")
                .replace("\u2019", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def flatten(text: str) -> str:
    """Collapse all whitespace so character offsets are stable."""
    return re.sub(r"\s+", " ", text).strip()


def parse_hhmm(value: str) -> Tuple[int, int]:
    try:
        hour, minute = value.split(":")
        return int(hour), int(minute)
    except (ValueError, AttributeError):
        return 9, 0


def find_times(text: str) -> List[Dict]:
    """Return every time-like span: 3pm, 3:30 pm, 15:00, noon, midnight."""
    found: List[Dict] = []
    spans: List[Tuple[int, int]] = []

    for match in re.finditer(
        r"(?<![\d:])(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![\w])",
        text,
        re.I,
    ):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if not 1 <= hour <= 12:
            continue
        suffix = match.group(3).lower().replace(".", "")
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        found.append({"h": hour, "m": minute, "start": match.start(),
                      "end": match.end(), "text": match.group(0)})
        spans.append((match.start(), match.end()))

    for match in re.finditer(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])", text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        found.append({"h": int(match.group(1)), "m": int(match.group(2)),
                      "start": match.start(), "end": match.end(),
                      "text": match.group(0)})

    for match in re.finditer(r"\b(noon|midnight)\b", text, re.I):
        hour = 12 if match.group(1).lower() == "noon" else 0
        found.append({"h": hour, "m": 0, "start": match.start(),
                      "end": match.end(), "text": match.group(0)})

    return found


def find_dates(text: str, now: datetime, order: str = "DMY",
               max_future_days: int = 180) -> List[Dict]:
    """Return every date-like span, with a weight for confidence scoring."""
    today = now.date()
    found: List[Dict] = []
    taken: List[Tuple[int, int]] = []

    def roll_forward(day: date, year: int) -> Optional[date]:
        """Move a past month/day into next year only if it stays plausible."""
        if day >= today - timedelta(days=1):
            return day
        try:
            candidate = day.replace(year=year + 1)
        except ValueError:
            return None
        if candidate <= today + timedelta(days=max_future_days):
            return candidate
        return None

    def add(day: date, start: int, end: int, phrase: str, weight: int,
            has_year: bool) -> None:
        if any(start < other_end and end > other_start
               for other_start, other_end in taken):
            return
        taken.append((start, end))
        found.append({"d": day, "start": start, "end": end, "phrase": phrase,
                      "weight": weight, "has_year": has_year})

    # ISO dates: 2026-11-05
    for match in re.finditer(
        r"(?<![\w/.-])(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?![\w/.-])", text
    ):
        try:
            day = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        add(day, match.start(), match.end(), match.group(0), 3, True)

    # Month-first: "November 5", "Nov 5, 2026"
    for match in re.finditer(
        rf"\b{MONTH_RE}\.?\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:\s*,?\s*(20\d{{2}}))?",
        text,
        re.I,
    ):
        month = MONTHS.get(match.group(1).lower()[:3])
        if not month:
            continue
        day_num = int(match.group(2))
        has_year = bool(match.group(3))
        year = int(match.group(3)) if has_year else today.year
        try:
            day = date(year, month, day_num)
        except ValueError:
            continue
        if not has_year:
            rolled = roll_forward(day, year)
            if rolled is None:
                continue
            day = rolled
        add(day, match.start(), match.end(), match.group(0),
            3 if has_year else 2, has_year)

    # Day-first: "5 November", "12 Nov 2026"
    for match in re.finditer(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{MONTH_RE}\.?(?:\s*,?\s*(20\d{{2}}))?",
        text,
        re.I,
    ):
        month = MONTHS.get(match.group(2).lower()[:3])
        if not month:
            continue
        day_num = int(match.group(1))
        has_year = bool(match.group(3))
        year = int(match.group(3)) if has_year else today.year
        try:
            day = date(year, month, day_num)
        except ValueError:
            continue
        if not has_year:
            rolled = roll_forward(day, year)
            if rolled is None:
                continue
            day = rolled
        add(day, match.start(), match.end(), match.group(0),
            3 if has_year else 2, has_year)

    # Numeric dates: 05/11/2026, 5/11, 11-05-2026
    for match in re.finditer(
        r"(?<![\w/.-])(\d{1,2})\s*([/.-])\s*(\d{1,2})(?:\s*[/.-]\s*(\d{2,4}))?(?![\w/.-])",
        text,
    ):
        first, second = int(match.group(1)), int(match.group(3))
        separator = match.group(2)
        year_raw = match.group(4)
        if first > 31 or second > 31:
            continue
        if text[max(0, match.start() - 1): match.start()] in "$€£¥":
            continue
        after = text[match.end(): match.end() + 10].lower()
        if re.match(r"\s*(hour|hr|%|x\b|k\b|m\b|gb|mb|kb)", after):
            continue
        has_year = bool(year_raw)
        if not has_year and separator == "." and max(first, second) > 12:
            continue
        year = today.year
        if has_year:
            year = int(year_raw)
            if year < 100:
                year += 2000
        if order.upper() == "MDY":
            month, day_num = first, second
        else:
            day_num, month = first, second
        if month > 12 and day_num <= 12:
            day_num, month = month, day_num
        try:
            day = date(year, month, day_num)
        except ValueError:
            continue
        if not has_year:
            rolled = roll_forward(day, year)
            if rolled is None:
                continue
            day = rolled
        add(day, match.start(), match.end(), match.group(0),
            3 if has_year else 2, has_year)

    # Relative days
    for pattern, delta in [
        (r"\bday after tomorrow\b", 2),
        (r"\btomorrow\b", 1),
        (r"\btonight\b", 0),
        (r"\btoday\b", 0),
    ]:
        for match in re.finditer(pattern, text, re.I):
            add(today + timedelta(days=delta), match.start(), match.end(),
                match.group(0), 1, False)

    # Relative weekdays: "next Monday", "this Friday", "coming Sunday"
    for match in re.finditer(
        r"\b(next|this|coming)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
        re.I,
    ):
        qualifier = match.group(1).lower()
        target = WEEKDAYS[match.group(2).lower()]
        delta = (target - today.weekday()) % 7
        if qualifier == "next" and delta == 0:
            delta = 7
        elif qualifier == "coming" and delta == 0:
            delta = 7
        add(today + timedelta(days=delta), match.start(), match.end(),
            match.group(0), 2, False)

    # Deadlines: "by Friday", "before Monday"
    for match in re.finditer(
        r"\b(?:by|on|before|until)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
        re.I,
    ):
        target = WEEKDAYS[match.group(1).lower()]
        delta = (target - today.weekday()) % 7
        add(today + timedelta(days=delta), match.start(), match.end(),
            match.group(0), 2, False)

    # Relative offsets: "in 3 days", "in 2 weeks"
    for match in re.finditer(r"\bin\s+(\d{1,2})\s+(day|days|week|weeks)\b", text, re.I):
        count = int(match.group(1))
        unit = match.group(2).lower()
        delta = count * (7 if unit.startswith("week") else 1)
        add(today + timedelta(days=delta), match.start(), match.end(),
            match.group(0), 2, False)

    for match in re.finditer(r"\bnext\s+week\b", text, re.I):
        add(today + timedelta(days=7), match.start(), match.end(),
            match.group(0), 1, False)

    for match in re.finditer(r"\bend of (?:the )?month\b", text, re.I):
        if today.month == 12:
            last = date(today.year, 12, 31)
        else:
            last = date(today.year, today.month + 1, 1) - timedelta(days=1)
        add(last, match.start(), match.end(), match.group(0), 1, False)

    return found


def _gap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    if a_end < b_start:
        return b_start - a_end
    if b_end < a_start:
        return a_start - b_end
    return 0


def extract_events(text: str, subject: str, now: datetime,
                   parsing: Dict) -> List[Event]:
    """Extract candidate events from a message body and subject."""
    order = parsing.get("date_order", "DMY")
    keywords = [word.lower() for word in parsing.get("keywords", [])]
    default_hh, default_mm = parse_hhmm(parsing.get("default_time", "09:00"))
    max_future_days = int(parsing.get("max_future_days", 180))
    same_day_hours = float(parsing.get("same_day_window_hours", 4))
    require_keyword = bool(parsing.get("require_event_keyword", True))

    dates = find_dates(text, now, order, max_future_days)
    times = find_times(text)
    subject_lc = subject.lower()
    events: List[Event] = []
    used_times = set()

    def keyword_near(start: int, end: int) -> bool:
        window = text[max(0, start - 150): end + 150].lower()
        return (any(word in window for word in keywords)
                or any(word in subject_lc for word in keywords))

    for date_item in dates:
        best = None
        best_gap = 10 ** 9
        for time_item in times:
            distance = _gap(date_item["start"], date_item["end"],
                            time_item["start"], time_item["end"])
            if distance <= 120 and distance < best_gap:
                best, best_gap = time_item, distance

        if best is not None:
            used_times.add(id(best))
            hour, minute = best["h"], best["m"]
        else:
            hour, minute = default_hh, default_mm
            if "tonight" in date_item["phrase"].lower():
                hour, minute = 19, 0

        due = datetime.combine(date_item["d"], time(hour, minute))
        score = date_item["weight"] + (2 if best is not None else 0)
        has_keyword = keyword_near(date_item["start"], date_item["end"])
        if has_keyword:
            score += 1

        snippet_start = max(0, min(date_item["start"],
                                   best["start"] if best else date_item["start"]) - 80)
        snippet_end = max(date_item["end"],
                          best["end"] if best else date_item["end"]) + 80
        events.append(Event(
            due=due,
            score=score,
            phrase=date_item["phrase"],
            snippet=text[snippet_start:snippet_end].strip(),
            has_time=best is not None,
            has_keyword=has_keyword,
        ))

    today = now.date()
    for time_item in times:
        if id(time_item) in used_times:
            continue
        if any(_gap(time_item["start"], time_item["end"],
                    item["start"], item["end"]) <= 120 for item in dates):
            continue
        due_date = today
        if (time_item["h"], time_item["m"]) <= (now.hour, now.minute):
            due_date = today + timedelta(days=1)
        due = datetime.combine(due_date, time(time_item["h"], time_item["m"]))
        has_keyword = keyword_near(time_item["start"], time_item["end"])
        events.append(Event(
            due=due,
            score=2 + (1 if has_keyword else 0),
            phrase=time_item["text"],
            snippet=text[max(0, time_item["start"] - 80): time_item["end"] + 80].strip(),
            has_time=True,
            has_keyword=has_keyword,
        ))

    threshold = 2 if require_keyword else 1
    fresh: List[Event] = []
    seen = set()
    for event in events:
        if event.score < threshold:
            continue
        if not event.has_time and not event.has_keyword:
            continue
        if event.due < now - timedelta(minutes=30):
            continue
        if event.due > now + timedelta(days=max_future_days):
            continue
        key = (event.due.date(), event.due.hour, event.due.minute)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(event)

    fresh.sort(key=lambda item: (-item.score, item.due))

    window = timedelta(hours=same_day_hours)
    deduped: List[Event] = []
    for event in fresh:
        if any(previous.due.date() == event.due.date()
               and abs(previous.due - event.due) <= window for previous in deduped):
            continue
        deduped.append(event)

    limit = int(parsing.get("max_per_email", 3))
    return deduped[:limit]
