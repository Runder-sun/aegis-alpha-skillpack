from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "portfolio-ops"


ROUTES = {
    "portfolio-add": ("portfolio-management", "portfolio-add"),
    "portfolio-remove": ("portfolio-management", "portfolio-remove"),
    "portfolio-view": ("portfolio-management", "portfolio-view"),
    "portfolio-report": ("portfolio-management", "portfolio-report"),
    "record-trade": ("portfolio-management", "record-trade"),
    "portfolio-risk-check": ("position-ops", "portfolio-risk-check"),
    "position-sizing-advisor": ("position-ops", "position-sizing-advisor"),
    "position-management": ("position-ops", "position-management-v2"),
}


def _skills_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE", "")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "package": PACKAGE,
        "command": command,
        "payload": payload,
        "as_of": _now(),
        "freshness": {"status": "delegated"},
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "analysis_only",
        "source": PACKAGE,
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _call(package: str, command: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    dispatch = _skills_root() / package / "scripts" / "dispatch.py"
    if not dispatch.exists():
        return 127, {"ok": False, "errors": ["dispatch_not_found"], "missing_critical_inputs": [f"{package}::dispatch.py"]}
    env = dict(os.environ)
    env.setdefault("AEGIS_ALPHA_WORKSPACE", str(_workspace_dir()))
    proc = subprocess.run(
        [sys.executable, str(dispatch), "--command", command, "--payload", json.dumps(payload, ensure_ascii=False)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(dispatch.parent),
        check=False,
    )
    text = (proc.stdout or "").strip()
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"ok": False, "errors": ["delegate_invalid_json"], "raw": text, "stderr": proc.stderr}
    return proc.returncode, parsed if isinstance(parsed, dict) else {"result": parsed}


def _wrap(command: str, payload: dict[str, Any], route: tuple[str, str], code: int, delegated: dict[str, Any]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = bool(delegated.get("ok")) and code == 0
    output["source"] = f"{route[0]}::{route[1]}"
    output["sources"] = [output["source"]]
    output["warnings"] = list(delegated.get("warnings") or [])
    output["errors"] = list(delegated.get("errors") or [])
    output["missing_critical_inputs"] = list(delegated.get("missing_critical_inputs") or delegated.get("errors") or [])
    output["artifacts"] = list(delegated.get("artifacts") or [])
    output["result"] = {"delegated": delegated}
    if not output["ok"] and not output["errors"]:
        output["errors"] = ["delegate_failed"]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")
    route = ROUTES.get(args.command)
    if route is None:
        output = _base_output(args.command, payload)
        output["errors"] = ["unknown_command"]
        output["missing_critical_inputs"] = ["known_portfolio_ops_command"]
        print(json.dumps(output, ensure_ascii=False))
        return 2
    code, delegated = _call(route[0], route[1], payload)
    output = _wrap(args.command, payload, route, code, delegated)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
