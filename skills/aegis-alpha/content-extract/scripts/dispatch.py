from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGE = "content-extract"


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_manifest() -> dict[str, Any]:
    path = _package_root() / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_command(command: str) -> None:
    available = {item["name"] for item in _load_manifest().get("commands", [])}
    if command not in available:
        raise SystemExit(f"unknown command: {command}")


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("OPENCLAW_WORKSPACE", str(_workspace_dir()))
    return env


def run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_command(command)
    if command != "extract-url":
        raise SystemExit(f"unhandled command: {command}")

    url = payload.get("url")
    if not url:
        raise SystemExit("extract-url requires url")

    script = _package_root() / "scripts" / "content_extract.py"
    cmd = [sys.executable, str(script), "--url", str(url)]
    if payload.get("model"):
        cmd.extend(["--model", str(payload["model"])])
    if payload.get("language"):
        cmd.extend(["--language", str(payload["language"])])
    if payload.get("max_chars") is not None:
        cmd.extend(["--max-chars", str(payload["max_chars"])])
    if payload.get("force"):
        cmd.append("--force")

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(script.parent), env=_build_env())
    text = (proc.stdout or "").strip()
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or text or f"command failed: {' '.join(cmd)}")
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    result = run_command(args.command, json.loads(args.payload))
    print(json.dumps({"package": PACKAGE, "command": args.command, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
