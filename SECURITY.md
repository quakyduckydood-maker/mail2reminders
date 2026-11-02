# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting:

1. Open the repository on GitHub.
2. Go to the **Security** tab.
3. Click **Report a vulnerability**.

Do not open a public issue for security problems.

Include:

- macOS version and Python version
- the command you ran
- steps to reproduce
- impact: what an attacker could read, change, or execute

You will get an acknowledgement as soon as possible. This is a hobby project,
so please allow a few days.

## Threat model

`mail2reminders` is a local tool that sits between two Apple applications.

- **No credentials.** It never asks for, stores, or transmits an email
  password. Mail.app holds the account session in the macOS Keychain.
- **No network calls of its own.** All work goes through `osascript` and Apple
  Events on the local machine.
- **No telemetry.**
- **Email content is untrusted input.** It is used for regex matching and is
  embedded into reminder notes. All values passed to JXA are JSON-encoded, and
  list names and titles are serialized with `JSON.stringify`, so a message
  cannot break out of a string literal into script code.
- **Local state.** `state.json` contains message IDs, subjects, and dates. It
  lives in `~/Library/Application Support/mail2reminders/` and should be
  treated as private. It is ignored by git.
- **Permissions.** Access is governed by the macOS Automation privacy
  permission. Revoke it in System Settings > Privacy & Security > Automation,
  or remove the account from Mail.

## Out of scope

- Wrong dates caused by ambiguous or unusual email phrasing (quality issue;
  please open a normal bug report)
- Permissions the user granted to unrelated applications
- Vulnerabilities in Apple Mail, Reminders, or macOS itself

## Handling reports

If a report is valid, the fix will be released as a patch version and the
report credited in `CHANGELOG.md`, unless you ask to stay anonymous.
