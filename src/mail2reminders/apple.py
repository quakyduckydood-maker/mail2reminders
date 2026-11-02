"""JXA bridge to Apple Mail and Apple Reminders.

Everything here goes through ``osascript`` and Apple Events, which means the
tool never handles your account password: Mail.app is already signed in, and
macOS gates access through the Automation privacy permission.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Message


class AppleScriptError(RuntimeError):
    """Raised when osascript fails, carrying the AppleScript error number."""

    def __init__(self, message: str, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


def is_macos() -> bool:
    return sys.platform == "darwin"


def app_path(name: str) -> Optional[Path]:
    for base in ("/System/Applications", "/Applications"):
        candidate = Path(base) / f"{name}.app"
        if candidate.exists():
            return candidate
    return None


def run_jxa(script: str, timeout: int = 300) -> str:
    if not is_macos():
        raise AppleScriptError("Apple Mail automation requires macOS")
    process = subprocess.run(
        ["/usr/bin/osascript", "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if process.returncode != 0:
        raw = (process.stderr or process.stdout or "osascript failed").strip()
        match = re.search(r"\((-?\d+)\)", raw)
        raise AppleScriptError(raw, int(match.group(1)) if match else None)
    return process.stdout.strip()


def permission_denied(error: Exception) -> bool:
    text = str(error).lower()
    return ("-1743" in text or "not authorized" in text
            or "not allowed" in text or "operation not permitted" in text)


def _parse_received(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def account_names() -> List[str]:
    script = """
const Mail = Application('Mail');
const out = [];
const accounts = Mail.accounts();
for (let i = 0; i < accounts.length; i++) {
  try { out.push(String(accounts[i].name())); } catch (e) {}
}
JSON.stringify(out);
"""
    return list(json.loads(run_jxa(script)))


def fetch_messages(config: Dict[str, Any]) -> Dict[str, Any]:
    """Read recent messages from the configured Mail account and mailbox."""
    mail_cfg = config["mail"]
    cutoff = datetime.now() - timedelta(days=float(mail_cfg["lookback_days"]))
    params = {
        "account": mail_cfg.get("account", ""),
        "mailbox": mail_cfg.get("mailbox", "INBOX"),
        "cutoff": cutoff.isoformat(),
        "limit": int(mail_cfg.get("max_messages", 200)),
        "maxChars": int(mail_cfg.get("max_chars", 20000)),
    }
    script = f"""
const p = {json.dumps(params)};
const Mail = Application('Mail');
const cutoff = new Date(p.cutoff);
const accounts = Mail.accounts();
let account = null;
for (let i = 0; i < accounts.length; i++) {{
  try {{ if (String(accounts[i].name()) === p.account) {{ account = accounts[i]; break; }} }} catch (e) {{}}
}}
if (!account && accounts.length > 0) account = accounts[0];
if (!account) throw new Error('NO_ACCOUNT: no account configured in Mail');

const mailboxes = account.mailboxes();
let mailbox = null;
for (let i = 0; i < mailboxes.length; i++) {{
  try {{ if (String(mailboxes[i].name()).toUpperCase() === p.mailbox.toUpperCase()) {{ mailbox = mailboxes[i]; break; }} }} catch (e) {{}}
}}
if (!mailbox) {{
  for (let i = 0; i < mailboxes.length; i++) {{
    try {{ if (String(mailboxes[i].name()).toUpperCase() === 'INBOX') {{ mailbox = mailboxes[i]; break; }} }} catch (e) {{}}
  }}
}}
if (!mailbox) throw new Error('NO_MAILBOX: no INBOX for ' + account.name());

let messages = [];
try {{
  messages = mailbox.messages.whose({{ dateReceived: {{ _greaterThan: cutoff }} }})();
}} catch (e) {{
  const all = mailbox.messages();
  for (let i = 0; i < all.length; i++) {{
    try {{ if (new Date(all[i].dateReceived()) >= cutoff) messages.push(all[i]); }} catch (e2) {{}}
  }}
}}

const out = [];
for (let i = 0; i < messages.length && out.length < p.limit; i++) {{
  const message = messages[i];
  try {{
    out.push({{
      id: String(message.id()),
      subject: String(message.subject() || ''),
      sender: String(message.sender() || ''),
      dateReceived: new Date(message.dateReceived()).toISOString(),
      content: String(message.content() || '').slice(0, p.maxChars)
    }});
  }} catch (e) {{}}
}}
JSON.stringify({{ account: String(account.name()), mailbox: String(mailbox.name()), messages: out }});
"""
    data = json.loads(run_jxa(script))
    parsed: List[Message] = []
    for item in data.get("messages", []):
        parsed.append(Message(
            id=str(item.get("id", "")),
            subject=item.get("subject", ""),
            sender=item.get("sender", ""),
            date_received=_parse_received(item.get("dateReceived", "")),
            content=item.get("content", ""),
        ))
    return {
        "account": data.get("account", ""),
        "mailbox": data.get("mailbox", ""),
        "messages": parsed,
    }


def add_reminder(config: Dict[str, Any], title: str, notes: str,
                 due: datetime) -> Dict[str, Any]:
    """Create a reminder with a due date and an alarm, creating the list if needed."""
    params = {
        "list": config["reminders"]["list"],
        "title": title,
        "notes": notes,
        "due": due.isoformat(),
    }
    script = f"""
const p = {json.dumps(params)};
const Reminders = Application('Reminders');
const lists = Reminders.lists();
let list = null;
for (let i = 0; i < lists.length; i++) {{
  try {{ if (String(lists[i].name()) === p.list) {{ list = lists[i]; break; }} }} catch (e) {{}}
}}
if (!list) {{
  const created = Reminders.List({{ name: p.list }});
  Reminders.lists.push(created);
  list = created;
}}
const reminder = Reminders.Reminder({{ name: p.title, body: p.notes }});
list.reminders.push(reminder);
const when = new Date(p.due);
reminder.dueDate = when;
reminder.remindMeDate = when;
JSON.stringify({{ ok: true, id: String(reminder.id()) }});
"""
    return dict(json.loads(run_jxa(script)))


def list_exists(name: str) -> bool:
    script = f"""
const target = {json.dumps(name)};
const Reminders = Application('Reminders');
const lists = Reminders.lists();
let found = false;
for (let i = 0; i < lists.length; i++) {{
  try {{ if (String(lists[i].name()) === target) found = true; }} catch (e) {{}}
}}
JSON.stringify({{ exists: found }});
"""
    return bool(json.loads(run_jxa(script)).get("exists"))


def reminder_count(name: str) -> int:
    script = f"""
const target = {json.dumps(name)};
const Reminders = Application('Reminders');
const lists = Reminders.lists();
let count = 0;
for (let i = 0; i < lists.length; i++) {{
  try {{ if (String(lists[i].name()) === target) count = lists[i].reminders().length; }} catch (e) {{}}
}}
JSON.stringify({{ count: count }});
"""
    return int(json.loads(run_jxa(script)).get("count", 0))
