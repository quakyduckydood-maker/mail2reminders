---
name: mail2reminders
description: Extract dates and times from Apple Mail messages and create Apple Reminders with alarms. Use when the user asks to scan their email for meetings, deadlines, appointments, or events, to turn email dates into reminders or notifications, or to set up a daily email-to-reminders job on macOS. Triggers on "email reminders", "remind me from my email", "scan my inbox for dates", "check my mail for deadlines", "mail2reminders".
---

# mail2reminders

Turn date and time mentions in Apple Mail into Apple Reminders automatically.
Works on macOS only, using Apple Mail and Apple Reminders through JXA.

## When to use

Use this skill when the user wants to:

- Find meetings, deadlines, or appointments mentioned in email
- Create reminders from their inbox
- Schedule a recurring email-to-reminders scan
- Diagnose why the scan is not finding events or not creating reminders

## Instructions

1. Check the tool is installed:

   ```bash
   mail2reminders --version
   ```

   If it is missing, install from the project directory:

   ```bash
   python3 -m pip install -e .
   ```

2. Always start with a dry run and show the user what would be created:

   ```bash
   mail2reminders run --dry-run --since-days 2
   ```

3. Ask the user to confirm before creating real reminders. Then run:

   ```bash
   mail2reminders run
   ```

4. If the user reports missing or wrong reminders, run diagnostics:

   ```bash
   mail2reminders doctor
   ```

5. To schedule twice-daily runs:

   ```bash
   mail2reminders install-launchd --times 08:00,20:00
   ```

   To remove the schedule:

   ```bash
   mail2reminders uninstall-launchd
   ```

## Configuration

The config file is created at
`~/Library/Application Support/mail2reminders/config.json` on first run.

Common changes:

- `mail.account`: the account name shown in Mail (default `iCloud`)
- `mail.lookback_days`: how far back each run scans
- `reminders.list`: which Reminders list to use
- `parsing.date_order`: `DMY` or `MDY`
- `parsing.keywords`: words that make a date mention count as an event

## Rules

- Never run without `--dry-run` first when the user has not seen the output.
- Never ask for an email password. The tool uses the account already signed in
  to Mail.app; if access fails, tell the user to grant Automation permission
  in System Settings > Privacy & Security > Automation.
- Do not edit `state.json` by hand; it is the duplicate-prevention store.
- macOS only. Do not suggest it for Linux or Windows.

## Troubleshooting

- Error `-1743` or "not authorized": Automation permission is missing.
- `NO_ACCOUNT`: add the email account in Mail > Settings > Accounts.
- No events found: widen `--since-days`, or add domain words to
  `parsing.keywords`.
- Wrong time: ambiguous bare times like `3:30` are read as 03:30; the email
  should say `3:30 pm`.
