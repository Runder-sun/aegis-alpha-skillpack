from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_NAME = "report-evolution"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_output(command: str, payload: dict[str, Any] | str) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": PACKAGE_NAME,
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "report evolution artifacts are derived from current workspace report, pipeline, and evidence artifacts",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "report_review_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any] | str, errors: list[str]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "ok": False,
        "missing_critical_inputs": errors,
    }
    return output


def _wrap(command: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["result"] = result
    saved_to = result.get("saved_to")
    if saved_to:
        output["artifacts"] = [str(saved_to)]
        output["sources"] = [str(saved_to)]
        output["source"] = [str(saved_to)]
    if result.get("ok") is False:
        error = str(result.get("error") or "report_evolution_failed")
        output["ok"] = False
        output["freshness"]["status"] = "unavailable"
        output["errors"] = [error]
        output["missing_critical_inputs"] = [error]
    return output


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _capture_report_evidence(payload: dict) -> dict:
    try:
        from capture_report import capture_report_evidence
    except ModuleNotFoundError:
        from .capture_report import capture_report_evidence
    return capture_report_evidence(payload)


def _align_report_outcome(payload: dict) -> dict:
    try:
        from align_outcomes import align_report_outcome
    except ModuleNotFoundError:
        from .align_outcomes import align_report_outcome
    return align_report_outcome(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = _load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", [])}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    try:
        payload = json.loads(args.payload or "{}")
    except json.JSONDecodeError:
        payload = None

    if payload is None:
        output = _fail(args.command, args.payload, ["invalid_payload_json"])
        print(json.dumps(output, ensure_ascii=False))
        return 0
    if not isinstance(payload, dict):
        output = _fail(args.command, payload, ["invalid_payload_type"])
        print(json.dumps(output, ensure_ascii=False))
        return 0

    if args.command == "capture-report-evidence":
        result = _capture_report_evidence(payload)
    elif args.command == "align-report-outcome":
        result = _align_report_outcome(payload)
    else:
        result = {"status": "unsupported", "payload": payload}

    output = _wrap(args.command, payload, result if isinstance(result, dict) else {"ok": False, "error": "invalid_result"})

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
