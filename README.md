# mail2reminders

Turn date and time mentions in your Apple Mail inbox into Apple Reminders —
automatically, locally, and without handing your password to anyone.

[![CI](https://github.com/quakyduckydood-maker/mail2reminders/actions/workflows/ci.yml/badge.svg)](https://github.com/quakyduckydood-maker/mail2reminders/actions/workflows/ci.yml)

```
Mail.app (iCloud)  ──Apple Events──▶  mail2reminders  ──JXA──▶  Reminders.app
```

## What it does

- Scans recent messages in Apple Mail (any account already added to Mail)
- Extracts dates and times from subjects and bodies
- Creates reminders with a due date and an alarm in a dedicated list
- Runs on demand or twice a day via launchd
- Never asks for, stores, or transmits an email password

## Why I built this

My university account (Microsoft 365) blocks third-party access, so I could not
point an AI assistant at it. Auto-forwarding that mail to my personal iCloud
address solved the access problem — but reading a dozen PolyU notices every day
to find the two dates that matter was still tedious.

macOS already has the pieces: Mail holds the account, Reminders holds the
notifications. This tool connects them locally:

```
school inbox ──auto-forward──▶ iCloud ──Mail.app──▶ mail2reminders ──▶ Reminders
```

> **Check your institution's policy first.** Many universities restrict or
> forbid forwarding institutional mail to personal accounts. If yours does,
> forward only the categories you are allowed to, or use a rule that copies
> rather than forwards. You are responsible for where your mail goes.

## How it works

1. **Read** — asks Mail.app for messages received after a cutoff date, through
   Apple Events (JXA).
2. **Clean** — strips HTML, entities, and quoted reply chains.
3. **Extract** — regex-based parser finds dates and times and scores each
   candidate by confidence.
4. **Filter** — drops past dates, dates beyond a horizon, duplicate same-day
   mentions, and date-like noise from newsletters.
5. **Create** — writes reminders with `dueDate` and `remindMeDate` set.
6. **Remember** — a local state file keyed by message id + event hash prevents
   duplicates on re-runs.

## Requirements

- macOS with Apple Mail and Apple Reminders (both ship with macOS)
- Python 3.9 or newer
- An email account already configured in Mail (iCloud, Exchange, Gmail, IMAP)
- No API keys, no subscription, no cloud service

## Install

```bash
git clone https://github.com/quakyduckydood-maker/mail2reminders.git
cd mail2reminders
python3 -m pip install --user -e .
```

Or with pipx:

```bash
pipx install .
```

Verify:

```bash
mail2reminders --version
```

## Setup

1. **Add the account to Mail** — Mail > Settings > Accounts. Wait for the
   inbox to sync.
2. **Grant Automation permission** — run the doctor and approve any dialogs:

   ```bash
   mail2reminders doctor
   ```

   You should see `[ok] Mail readable` and `[ok] Reminders list`.
3. **Preview before writing** — a dry run shows exactly what would be created:

   ```bash
   mail2reminders run --dry-run
   ```

4. **Create for real**:

   ```bash
   mail2reminders run
   ```

## Usage

| Command | What it does |
|---|---|
| `mail2reminders run` | Scan and create reminders |
| `mail2reminders run --dry-run` | Show what would be created |
| `mail2reminders run --since-days 7` | Scan a wider window |
| `mail2reminders check` | Verify Mail connectivity and list recent messages |
| `mail2reminders doctor` | Diagnose apps, permissions, config, and list |
| `mail2reminders install-launchd --times 08:00,20:00` | Schedule twice-daily runs |
| `mail2reminders uninstall-launchd` | Remove the schedule |

## Schedule it

```bash
mail2reminders install-launchd --times 08:00,20:00
```

This writes `~/Library/LaunchAgents/com.mail2reminders.plist` and loads it.

Behaviour to know:

- If the Mac is **asleep** at a scheduled time, launchd runs the job once when
  the Mac wakes. Multiple missed runs are coalesced into one.
- If the Mac is **powered off**, missed runs are not replayed at boot. The next
  run happens at the next scheduled time, and the lookback window covers the
  gap.
- If you often close the laptop for days, raise `mail.lookback_days` to `7`.

## Configuration

Created on first run at:

```
~/Library/Application Support/mail2reminders/config.json
```

| Key | Default | Meaning |
|---|---|---|
| `mail.account` | `iCloud` | Account name shown in Mail |
| `mail.mailbox` | `INBOX` | Mailbox to scan |
| `mail.lookback_days` | `2` | Days scanned per run |
| `mail.max_messages` | `200` | Safety cap per run |
| `reminders.list` | `Email Reminders` | Target list (created if missing) |
| `reminders.max_per_email` | `3` | Max events taken from one message |
| `reminders.notify_on_run` | `true` | Show a summary notification |
| `parsing.date_order` | `DMY` | `DMY` or `MDY` for ambiguous dates |
| `parsing.default_time` | `09:00` | Time used when only a date is found |
| `parsing.max_future_days` | `180` | Ignore events further out |
| `parsing.same_day_window_hours` | `4` | Collapse same-day duplicates |
| `parsing.keywords` | list | Words that make a date an event |

## What it can parse

| In the email | Reminder |
|---|---|
| `05/11/2026` + `3:30 pm` | 5 Nov 2026, 15:30 |
| `12 Nov 2026, 08:45` | 12 Nov 2026, 08:45 |
| `tomorrow at 10am` | next day, 10:00 |
| `next Monday at 14:00` | following Monday, 14:00 |
| `by Friday` | Friday, 09:00 (default time) |
| `November 5 at noon` | 5 Nov, 12:00 |
| `19:00-23:30` | 19:00 (start time) |

Ambiguous bare times such as `3:30` are read as **03:30** (24-hour
convention). Write `3:30 pm` if you mean the afternoon.

## Troubleshooting

**`-1743` or "not authorized"**

Automation permission is missing. Open System Settings > Privacy & Security >
Automation and allow your terminal (or Python) to control Mail and Reminders.
Then rerun `mail2reminders doctor`.

**`NO_ACCOUNT: no account configured in Mail`**

Mail has no account, or the account name differs. Run
`mail2reminders check` after adding the account, or set `mail.account` in the
config to the exact name shown in Mail.

**No events found**

Widen the window (`--since-days 7`). If the messages are event-like but the
parser stays quiet, add the domain words (for example `seminar`, `office
hours`, `defense`) to `parsing.keywords`.

**Reminders are created but no notification appears**

System Settings > Notifications > Reminders: enable notifications and allow
banners or alerts.

**Wrong time**

The email probably used a bare time. Edit the reminder, and prefer `3:30 pm`
in future messages.

## Privacy and security

- **No credentials.** The tool never sees your password. Mail.app is already
  signed in; macOS grants access through the Automation permission.
- **No network calls of its own.** Everything runs locally through
  `osascript`.
- **No telemetry.**
- **Local data.** `config.json`, `state.json`, and `run.log` live under
  `~/Library/Application Support/mail2reminders/`. `state.json` stores message
  IDs, subjects, and dates; treat it as private.
- **Revoke access** by removing the Automation permission, or delete the
  account from Mail.

## Limitations

- macOS only; it depends on Mail.app and Reminders.app.
- The parser is rule-based, not a language model. It is predictable, but it
  will not understand every phrasing.
- Newsletter-style mail can still produce an occasional extra reminder.
- Mail.app's AppleScript interface gets slower on very large inboxes; keep
  `lookback_days` modest.
- Reminders due dates use local time.

## Development

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest
```

Layout:

```
src/mail2reminders/
├── apple.py    JXA bridge (Mail + Reminders)
├── cli.py      commands, launchd install, logging
├── config.py   defaults and file locations
├── models.py   Message and Event dataclasses
├── parse.py    date/time extraction (pure, testable)
└── state.py    duplicate prevention
tests/          parser, state, config, and .eml fixtures
skills/         optional Agent Skill wrapper
```

Adding a date format: add a regex block in `parse.py`, then add a case to
`tests/test_parse.py`. Keep the parser pure so CI can run it on Linux.

## Contributing

Issues and pull requests are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, commit style, and
how to add a date format. Please include a redacted sample (subject and the
date phrase) when reporting a parsing bug. Do not paste real email addresses.

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

`mail2reminders` never handles your email password and makes no network calls
of its own. If you find a security problem, please report it privately as
described in [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Built to make a daily pile of university notices readable in ten seconds.
