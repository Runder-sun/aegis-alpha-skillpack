#!/usr/bin/env python3
"""hhxg-market dispatch.py — routes named commands to existing hhxg scripts.

Available commands:
  snapshot-full, snapshot-market, snapshot-themes, snapshot-ladder,
  snapshot-hotmoney, snapshot-sectors, snapshot-news, snapshot-summary,
  calendar-week, calendar-trading, calendar-unlock, calendar-earnings,
  calendar-delivery, margin-overview, margin-top, margin-full
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def _run_script(script: str, *args: str) -> dict:
    """Run a sibling script with --json flag and parse output."""
    cmd = [PYTHON, str(SCRIPTS_DIR / script), *args, "--json"]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "script timeout after 30s"}

    raw_out = (result.stdout or "").strip()
    raw_err = (result.stderr or "").strip()

    if not raw_out:
        return {"success": False, "error": raw_err or "empty output", "returncode": result.returncode}

    try:
        data = json.loads(raw_out)
        return {"success": result.returncode == 0, "data": data}
    except json.JSONDecodeError:
        return {"success": result.returncode == 0, "raw": raw_out}


def _run_command(command: str, payload: dict) -> dict:
    # ── fetch_snapshot.py ────────────────────────────────────────────────────
    if command == "snapshot-full":
        return _run_script("fetch_snapshot.py")
    if command == "snapshot-market":
        return _run_script("fetch_snapshot.py", "market")
    if command == "snapshot-themes":
        return _run_script("fetch_snapshot.py", "themes")
    if command == "snapshot-ladder":
        return _run_script("fetch_snapshot.py", "ladder")
    if command == "snapshot-hotmoney":
        return _run_script("fetch_snapshot.py", "hotmoney")
    if command == "snapshot-sectors":
        return _run_script("fetch_snapshot.py", "sectors")
    if command == "snapshot-news":
        return _run_script("fetch_snapshot.py", "news")
    if command == "snapshot-summary":
        return _run_script("fetch_snapshot.py", "summary")

    # ── calendar_hhxg.py ─────────────────────────────────────────────────────
    if command == "calendar-week":
        return _run_script("calendar_hhxg.py", "week")
    if command == "calendar-trading":
        date = payload.get("date", "")
        args = ("trading", date) if date else ("trading",)
        return _run_script("calendar_hhxg.py", *args)
    if command == "calendar-unlock":
        month = payload.get("month", "")
        args = ("unlock", month) if month else ("unlock",)
        return _run_script("calendar_hhxg.py", *args)
    if command == "calendar-earnings":
        month = payload.get("month", "")
        args = ("earnings", month) if month else ("earnings",)
        return _run_script("calendar_hhxg.py", *args)
    if command == "calendar-delivery":
        return _run_script("calendar_hhxg.py", "delivery")

    # ── margin.py ────────────────────────────────────────────────────────────
    if command == "margin-full":
        return _run_script("margin.py")
    if command == "margin-overview":
        return _run_script("margin.py", "overview")
    if command == "margin-top":
        return _run_script("margin.py", "top")

    raise ValueError(f"unknown command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")

    try:
        result = _run_command(args.command, payload)
        print(json.dumps({
            "package": "hhxg-market",
            "command": args.command,
            "success": True,
            "payload": payload,
            "result": result,
        }, ensure_ascii=False))
        return 0
    except ValueError as exc:
        print(json.dumps({
            "package": "hhxg-market",
            "command": args.command,
            "success": False,
            "error": str(exc),
        }, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({
            "package": "hhxg-market",
            "command": args.command,
            "success": False,
            "error": str(exc),
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
