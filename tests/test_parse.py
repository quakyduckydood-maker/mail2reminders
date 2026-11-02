from datetime import datetime

from mail2reminders.config import DEFAULTS
from mail2reminders.parse import clean_text, extract_events, flatten

NOW = datetime(2026, 11, 2, 12, 0)  # Monday, noon


def parse_body(body, subject=None, order="DMY", **overrides):
    parsing = dict(DEFAULTS["parsing"])
    parsing.update(overrides)
    parsing["date_order"] = order
    text = flatten(clean_text(body))
    subject = subject if subject is not None else body
    return extract_events(text, subject, NOW, parsing)


def test_dd_mm_with_time():
    events = parse_body("Project kickoff meeting on 05/11/2026 at 3:30 pm via Zoom")
    assert len(events) == 1
    assert events[0].due == datetime(2026, 11, 5, 15, 30)


def test_relative_day_with_time():
    events = parse_body("Reminder: dentist appointment tomorrow at 10am")
    assert events[0].due == datetime(2026, 11, 3, 10, 0)


def test_day_month_year_with_time():
    body = "Your flight departs 12 Nov 2026, 08:45. Check-in opens 2 hours before."
    events = parse_body(body)
    assert events[0].due == datetime(2026, 11, 12, 8, 45)


def test_month_name_year_is_not_read_as_day():
    events = parse_body("Seminar on 12 November 2026 at 11:00")
    assert events[0].due == datetime(2026, 11, 12, 11, 0)
    assert events[0].phrase == "12 November 2026"


def test_weekday_deadline_defaults_to_nine():
    events = parse_body("Deadline: submit assignment by Friday")
    assert events[0].due == datetime(2026, 11, 6, 9, 0)


def test_next_weekday_with_time():
    events = parse_body("Team meeting next Monday at 14:00")
    assert events[0].due == datetime(2026, 11, 9, 14, 0)


def test_time_only_event():
    events = parse_body("Call at 3pm to discuss the contract")
    assert events[0].due == datetime(2026, 11, 2, 15, 0)


def test_month_name_and_noon():
    events = parse_body("Webinar on November 5 at noon")
    assert events[0].due == datetime(2026, 11, 5, 12, 0)


def test_dmy_ambiguous_date():
    events = parse_body("Review on 05/11/2026 at 09:00")
    assert events[0].due == datetime(2026, 11, 5, 9, 0)


def test_mdy_ambiguous_date():
    events = parse_body("Review on 11/05/2026 at 09:00", order="MDY")
    assert events[0].due == datetime(2026, 11, 5, 9, 0)


def test_noise_is_ignored():
    body = "Big sale! 50% off, read in 1.5 hours, Copyright 2026"
    assert parse_body(body) == []


def test_past_date_is_dropped():
    assert parse_body("Meeting on 12/03/2025 at 10:00") == []


def test_far_future_date_is_dropped():
    assert parse_body("Meeting on 12/03/2028 at 10:00") == []


def test_duplicate_same_day_is_collapsed():
    body = "Workshop on 05/11 from 10:30 to 12:00. Registration at 10:30."
    events = parse_body(body)
    assert len(events) == 1


def test_quoted_reply_is_ignored():
    body = (
        "Thanks, see you then.\n\n"
        "On Mon, 2 Nov 2026, someone wrote:\n"
        "> The meeting was on 01/10/2026 at 09:00.\n"
    )
    assert parse_body(body) == []
