from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "pipeline"
PIPELINE_SHORTCUTS = {
    "pipeline-run-nightly": "nightly",
    "pipeline-run-morning": "morning",
    "pipeline-run-weekly": "weekly",
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
        "max_action_level": "workflow_orchestration_only",
        "source": PACKAGE,
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _ensure_workspace_skill_link(workspace: Path) -> None:
    skills_root = _skills_root()
    workspace_skills = workspace / "skills"
    workspace_skills.mkdir(parents=True, exist_ok=True)
    for package in ("pipeline-runner", "pipeline-orchestrator"):
        target = workspace_skills / package
        if target.exists():
            continue
        source = skills_root / package
        try:
            target.symlink_to(source, target_is_directory=True)
        except OSError:
            pass


def _call(package: str, command: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    dispatch = _skills_root() / package / "scripts" / "dispatch.py"
    if not dispatch.exists():
        return 127, {"ok": False, "errors": ["dispatch_not_found"], "missing_critical_inputs": [f"{package}::dispatch.py"]}
    workspace = _workspace_dir()
    if package == "pipeline-orchestrator":
        _ensure_workspace_skill_link(workspace)
    env = dict(os.environ)
    env.setdefault("AEGIS_ALPHA_WORKSPACE", str(workspace))
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
    output["ok"] = bool(delegated.get("ok", code == 0)) and code == 0
    output["source"] = f"{route[0]}::{route[1]}"
    output["sources"] = [output["source"]]
    output["warnings"] = list(delegated.get("warnings") or [])
    output["errors"] = list(delegated.get("errors") or [])
    output["missing_critical_inputs"] = list(delegated.get("missing_critical_inputs") or delegated.get("errors") or [])
    if delegated.get("saved_to"):
        output["artifacts"] = [str(delegated["saved_to"])]
    else:
        output["artifacts"] = list(delegated.get("artifacts") or [])
    output["result"] = {"delegated": delegated}
    if not output["ok"] and not output["errors"]:
        output["errors"] = ["delegate_failed"]
    return output


def _resolve(command: str, payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]] | None:
    if command == "pipeline-list":
        return "pipeline-runner", "pipeline-list", payload
    if command == "pipeline-dry-run":
        next_payload = dict(payload)
        next_payload["dry_run"] = True
        return "pipeline-orchestrator", "pipeline-dry-run", next_payload
    if command == "pipeline-run":
        return "pipeline-orchestrator", "pipeline-run", payload
    pipeline_id = PIPELINE_SHORTCUTS.get(command)
    if pipeline_id:
        next_payload = dict(payload)
        next_payload.setdefault("pipeline_id", pipeline_id)
        return "pipeline-orchestrator", "pipeline-run", next_payload
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")
    route = _resolve(args.command, payload)
    if route is None:
        output = _base_output(args.command, payload)
        output["errors"] = ["unknown_command"]
        output["missing_critical_inputs"] = ["known_pipeline_command"]
        print(json.dumps(output, ensure_ascii=False))
        return 2
    package, command, next_payload = route
    code, delegated = _call(package, command, next_payload)
    output = _wrap(args.command, payload, (package, command), code, delegated)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
