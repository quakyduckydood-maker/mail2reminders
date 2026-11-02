import email
from datetime import datetime
from email import policy
from pathlib import Path

from mail2reminders.config import DEFAULTS
from mail2reminders.parse import clean_text, extract_events, flatten

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 2, 12, 0)


def body_of(name):
    raw = (FIXTURES / name).read_bytes()
    message = email.message_from_bytes(raw, policy=policy.default)
    part = message.get_body(preferencelist=("plain",))
    return part.get_content() if part is not None else ""


def events_for(name, subject):
    text = flatten(clean_text(body_of(name)))
    return extract_events(text, subject, NOW, DEFAULTS["parsing"])


def test_seminar_fixture_extracts_event():
    events = events_for("seminar.eml", "Research seminar invitation")
    assert any(event.due == datetime(2026, 11, 12, 11, 0) for event in events)


def test_newsletter_fixture_has_no_events():
    assert events_for("newsletter.eml", "October newsletter") == []
