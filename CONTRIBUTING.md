# Contributing to mail2reminders

Thanks for helping. This is a small, focused tool: read mail locally, extract
dates, create reminders. Please keep changes in that spirit.

## Development setup

```bash
git clone https://github.com/quakyduckydood-maker/mail2reminders.git
cd mail2reminders
python3 -m pip install -e ".[test]"
```

Requirements: macOS for end-to-end testing, Python 3.9+ for development.
The parser tests run on any platform.

## Running the tests

```bash
python3 -m pytest
```

The suite is deterministic: parser tests use a fixed clock (`2026-11-02
12:00`) so results do not depend on when CI runs.

## Adding a date format

1. Add a regex block in `src/mail2reminders/parse.py` (inside `find_dates` or
   `find_times`).
2. Give the new pattern a sensible weight:
   - `3` explicit date with a year
   - `2` explicit date without a year
   - `1` relative expression ("tomorrow", "next week")
3. Add at least two cases to `tests/test_parse.py`, one positive and one that
   should stay silent.
4. Run the suite. If a new pattern creates false positives in the newsletter
   fixture, tighten it or extend the noise filters.

Keep `parse.py` pure: no `osascript`, no file access, no clock reads other than
the `now` argument. That is what lets CI run on Linux.

## Reporting a parsing bug

Open an issue with:

- macOS version and Python version
- the command you ran
- a redacted sample: sender domain, subject, and the exact date phrase
- what you expected and what was created

Do not paste real email addresses, message IDs, or full message bodies.

## Commit style

Use a short prefix, one logical change per commit:

- `fix:` bug fix
- `feat:` new capability
- `docs:` documentation only
- `test:` tests only
- `refactor:` no behaviour change

Examples:

```
fix: do not read the year as a day in "12 Nov 2026"
feat: collapse same-day duplicate times
docs: explain launchd sleep behaviour
```

## Pull requests

1. Branch from `main`.
2. Keep the diff focused; do not reformat unrelated code.
3. Add or update tests for behaviour changes.
4. Update `CHANGELOG.md` under an "Unreleased" heading if the change is
   user-visible.
5. Make sure `python3 -m pytest` passes.

The PR template lists the checks; fill it in honestly.

## Code style

- Python 3.9+ compatible (no `match`, no `X | Y` at runtime).
- Type hints on public functions.
- No new runtime dependencies. The tool intentionally ships with none.
- Prefer clear names over clever one-liners.
- Keep user-facing errors actionable: say what failed and what to do next.

## Scope

In scope: date extraction, Mail access, Reminders output, scheduling,
diagnostics, documentation.

Out of scope for now: IMAP mode, Calendar events, non-macOS platforms,
LLM-based parsing. Open an issue to discuss before building any of these.
