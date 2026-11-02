import pytest

from mail2reminders.cli import _parse_times, build_parser


def test_parse_times_single():
    assert _parse_times("08:00") == [(8, 0)]


def test_parse_times_multiple():
    assert _parse_times("08:00, 20:30") == [(8, 0), (20, 30)]


def test_parse_times_rejects_invalid_hour():
    with pytest.raises(SystemExit):
        _parse_times("25:00")


def test_parse_times_rejects_garbage():
    with pytest.raises(SystemExit):
        _parse_times("eight")


def test_parser_lists_commands():
    help_text = build_parser().format_help()
    for command in ("run", "check", "doctor", "install-launchd",
                    "uninstall-launchd"):
        assert command in help_text
