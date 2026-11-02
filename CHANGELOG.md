# Changelog

All notable changes to this project are documented here.
The format is based on Keep a Changelog, and this project follows
Semantic Versioning.

## [0.1.0] - 2026-11-02

### Added

- Initial public release.
- Reads recent messages from Apple Mail through Apple Events (JXA).
- Extracts dates and times from message bodies with a rule-based parser.
- Creates reminders with due dates and alarms in Apple Reminders.
- Date formats: DD/MM (default), MM/DD, ISO, month names, relative dates
  (today, tomorrow, next Monday, in 3 days, end of month), times with
  am/pm, 24-hour times, noon and midnight.
- Noise filters: past dates, dates beyond a horizon, duplicates on the same
  day, newsletter-style false positives.
- Idempotent runs backed by a local state file.
- Commands: `run`, `check`, `doctor`, `install-launchd`,
  `uninstall-launchd`.
- `install-launchd` generates and loads a LaunchAgent for twice-daily runs.
- Agent Skill wrapper under `skills/mail2reminders`.
