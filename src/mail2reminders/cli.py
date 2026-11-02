"""Command line interface for mail2reminders."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .apple import (
    AppleScriptError,
    add_reminder,
    app_path,
    fetch_messages,
    is_macos,
    list_exists,
    permission_denied,
    reminder_count,
)
from .config import app_dir, default_config_path, default_log_path, load_config
from .models import Event, Message
from .parse import clean_text, extract_events, flatten
from .state import State

COMMANDS = {"run", "check", "doctor", "install-launchd", "uninstall-launchd"}
LAUNCHD_LABEL = "com.mail2reminders"


def log(message: str, echo: bool = True,
        log_path: Optional[Path] = None) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} {message}"
    path = Path(log_path) if log_path else default_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    if echo:
        print(line, flush=True)


def build_notes(message: Message, event: Event) -> str:
    received = (message.date_received.strftime("%Y-%m-%d %H:%M")
                if message.date_received else "unknown")
    return (
        f"From: {message.sender}\n"
        f"Received: {received}\n"
        f"When: {event.phrase} -> {event.due:%Y-%m-%d %H:%M}\n"
        f"Snippet: {event.snippet}\n"
        f"Mail id: {message.id}"
    )


def notify(title: str, message: str) -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, default=None,
                        help="path to config.json")
    common.add_argument("--verbose", action="store_true",
                        help="print extra detail")

    parser = argparse.ArgumentParser(
        prog="mail2reminders",
        description="Extract dates and times from Apple Mail and create Apple Reminders.",
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", parents=[common],
                         help="scan mail and create reminders")
    run.add_argument("--dry-run", action="store_true",
                     help="show what would be created, write nothing")
    run.add_argument("--since-days", type=float, default=None,
                     help="override the lookback window")
    run.add_argument("--limit", type=int, default=None,
                     help="maximum number of messages to scan")
    run.add_argument("--quiet", action="store_true",
                     help="only write to the log file")

    check = sub.add_parser("check", parents=[common],
                           help="verify Mail connectivity")
    check.add_argument("--since-days", type=float, default=None)
    check.add_argument("--limit", type=int, default=None)

    sub.add_parser("doctor", parents=[common],
                   help="diagnose setup and permissions")

    install = sub.add_parser("install-launchd", parents=[common],
                             help="schedule runs with launchd")
    install.add_argument("--times", default="08:00,20:00",
                         help="comma-separated HH:MM times (default 08:00,20:00)")
    install.add_argument("--uninstall", action="store_true",
                         help="remove the job instead of installing")

    sub.add_parser("uninstall-launchd", parents=[common],
                   help="remove the launchd job")

    return parser


def command_run(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    log_path = default_log_path()
    quiet = bool(getattr(args, "quiet", False))
    log("=== start ===", echo=not quiet, log_path=log_path)

    if args.since_days is not None:
        config["mail"]["lookback_days"] = args.since_days
    if args.limit is not None:
        config["mail"]["max_messages"] = args.limit

    try:
        data = fetch_messages(config)
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR fetching mail: {exc}", log_path=log_path)
        if permission_denied(exc):
            log("Grant Automation permission: System Settings > Privacy & Security > "
                "Automation, then allow your terminal (or Python) to control Mail "
                "and Reminders.", log_path=log_path)
            return 2
        return 1

    messages: List[Message] = data["messages"]
    log(f"account={data['account']} mailbox={data['mailbox']} "
        f"messages={len(messages)}", echo=not quiet, log_path=log_path)

    state = State()
    now = datetime.now()
    created = 0
    skipped = 0

    for message in messages:
        text = flatten(clean_text(message.content))
        subject = flatten(message.subject)
        events = extract_events(text, subject, now, config["parsing"])
        for event in events:
            key = hashlib.sha1(
                f"{message.id}|{event.due.isoformat()}|{subject}".encode("utf-8")
            ).hexdigest()[:16]
            if state.is_done(key):
                skipped += 1
                continue

            title = (subject[:90] or "Email reminder").strip()
            if len(events) > 1:
                title = f"{title} \u2014 {event.due:%d/%m %H:%M}"
            notes = build_notes(message, event)

            if args.dry_run:
                log(f"DRY: {event.due:%Y-%m-%d %H:%M} | {title}",
                    echo=not quiet, log_path=log_path)
                continue

            try:
                add_reminder(config, title, notes, event.due)
            except Exception as exc:  # noqa: BLE001
                log(f"ERROR creating reminder: {exc}", log_path=log_path)
                continue

            state.mark(key, {
                "title": title,
                "due": event.due.isoformat(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })
            created += 1
            log(f"ADD: {event.due:%Y-%m-%d %H:%M} | {title}",
                echo=not quiet, log_path=log_path)

    state.save()
    log(f"done: created={created} skipped={skipped} scanned={len(messages)}",
        echo=not quiet, log_path=log_path)

    if created and not args.dry_run and config["reminders"].get("notify_on_run", True):
        notify("Email Reminders",
               f"Added {created} reminder(s) from {len(messages)} email(s)")
    return 0


def command_check(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    if args.since_days is not None:
        config["mail"]["lookback_days"] = args.since_days
    if args.limit is not None:
        config["mail"]["max_messages"] = args.limit
    try:
        data = fetch_messages(config)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        if permission_denied(exc):
            print("Grant Automation permission: System Settings > Privacy & Security > "
                  "Automation > allow your terminal to control Mail.")
        return 2
    print(f"account:  {data['account']}")
    print(f"mailbox:  {data['mailbox']}")
    print(f"messages: {len(data['messages'])}")
    for message in data["messages"][:5]:
        when = (message.date_received.strftime("%Y-%m-%d %H:%M")
                if message.date_received else "?")
        print(f"  - {when} | {message.sender[:40]} | {message.subject[:60]}")
    return 0


def command_doctor(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    healthy = True

    def line(status: str, text: str) -> None:
        print(f"[{status}] {text}")

    if not is_macos():
        line("FAIL", "macOS is required for Apple Mail automation")
        return 1
    line("ok", f"macOS detected (Python {sys.version.split()[0]})")

    for name in ("Mail", "Reminders"):
        path = app_path(name)
        if path:
            line("ok", f"{name}.app found at {path}")
        else:
            line("FAIL", f"{name}.app not found in /System/Applications or /Applications")
            healthy = False

    config_path = Path(args.config) if args.config else default_config_path()
    if config_path.exists():
        line("ok", f"config: {config_path}")
    else:
        line("warn", f"config will be created on first run: {config_path}")

    state_path = app_dir() / "state.json"
    line("info", f"state: {state_path}")

    try:
        data = fetch_messages(config)
        line("ok", f"Mail readable: account={data['account']} "
                   f"mailbox={data['mailbox']} messages={len(data['messages'])}")
    except Exception as exc:  # noqa: BLE001
        if permission_denied(exc):
            line("FAIL", "Automation permission missing for Mail")
            line("info", "System Settings > Privacy & Security > Automation > "
                         "enable your terminal / Python")
        else:
            line("FAIL", f"Mail error: {exc}")
        healthy = False

    try:
        list_name = config["reminders"]["list"]
        if list_exists(list_name):
            line("ok", f"Reminders list '{list_name}' exists "
                       f"({reminder_count(list_name)} reminders)")
        else:
            line("warn", f"Reminders list '{list_name}' will be created on first run")
    except Exception as exc:  # noqa: BLE001
        if permission_denied(exc):
            line("FAIL", "Automation permission missing for Reminders")
        else:
            line("FAIL", f"Reminders error: {exc}")
        healthy = False

    return 0 if healthy else 1


def _parse_times(value: str) -> List[tuple]:
    times = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            hour_text, minute_text = part.split(":")
            hour, minute = int(hour_text), int(minute_text)
        except ValueError:
            raise SystemExit(f"Invalid time '{part}', expected HH:MM")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise SystemExit(f"Invalid time '{part}', expected HH:MM")
        times.append((hour, minute))
    return times


def _launchd_program() -> List[str]:
    executable = shutil.which("mail2reminders")
    if executable:
        return [executable, "run", "--quiet"]
    return [sys.executable, "-m", "mail2reminders", "run", "--quiet"]


def _launchd_plist(times: List[tuple]) -> str:
    intervals = "".join(
        "    <dict><key>Hour</key><integer>{}</integer>"
        "<key>Minute</key><integer>{}</integer></dict>\n".format(hour, minute)
        for hour, minute in times
    )
    program = "".join(
        f"    <string>{html.escape(part)}</string>\n"
        for part in _launchd_program()
    )
    out_log = html.escape(str(app_dir() / "launchd.out.log"))
    err_log = html.escape(str(app_dir() / "launchd.err.log"))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCHD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{program}  </array>
  <key>StartCalendarInterval</key>
  <array>
{intervals}  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{out_log}</string>
  <key>StandardErrPath</key>
  <string>{err_log}</string>
</dict>
</plist>
"""


def command_install_launchd(args: argparse.Namespace,
                            config: Dict[str, Any]) -> int:
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"

    if args.uninstall:
        return _uninstall_launchd(plist_path)

    times = _parse_times(args.times)
    if not times:
        print("No valid times supplied. Example: --times 08:00,20:00")
        return 1

    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(_launchd_plist(times), encoding="utf-8")
    print(f"wrote {plist_path}")

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)],
                   capture_output=True)
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"launchctl bootstrap failed: {result.stderr.strip() or result.stdout.strip()}")
        return 1

    pretty = ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in times)
    print(f"installed {LAUNCHD_LABEL}: runs daily at {pretty}")
    print("check with: launchctl print "
          f"gui/{uid}/{LAUNCHD_LABEL} | grep -E 'state|runs|last exit'")
    return 0


def _uninstall_launchd(plist_path: Path) -> int:
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)],
                   capture_output=True)
    if plist_path.exists():
        plist_path.unlink()
        print(f"removed {plist_path}")
    else:
        print("no launchd job was installed")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["run"]
    elif argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "--version"):
        argv.insert(0, "run")

    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "run":
        return command_run(args, config)
    if args.command == "check":
        return command_check(args, config)
    if args.command == "doctor":
        return command_doctor(args, config)
    if args.command == "install-launchd":
        return command_install_launchd(args, config)
    if args.command == "uninstall-launchd":
        return _uninstall_launchd(
            Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
