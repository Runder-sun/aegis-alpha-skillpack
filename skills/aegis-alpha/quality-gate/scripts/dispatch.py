from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_PATTERNS = [
    "nightly-strategy-report-*.md",
    "nightly-report-*.md",
]


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_artifact(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"failed to read {path}: {exc}"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "quality-gate",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "quality status is derived from current workspace artifacts at command runtime",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "quality_validation_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "ok": False,
        "note": "Quality gate could not prove required artifacts.",
        "missing_critical_inputs": errors,
    }
    return output


def _wrap(command: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["result"] = result
    saved_to = result.get("saved_to")
    if saved_to:
        output["artifacts"] = [str(saved_to)]
    result_artifacts = result.get("artifacts")
    if isinstance(result_artifacts, dict):
        output["sources"] = [str(value) for value in result_artifacts.values() if value]
        output["source"] = list(output["sources"])
    errors = result.get("errors")
    if isinstance(errors, list):
        output["errors"] = [str(error) for error in errors if error]
    if result.get("ok") is False:
        output["ok"] = False
        output["freshness"]["status"] = "unavailable"
        missing = output["errors"] or [str(result.get("reason") or "quality_gate_failed")]
        output["missing_critical_inputs"] = missing
    return output


def _latest_report(report_dir: Path) -> Path | None:
    for pattern in REPORT_PATTERNS:
        report_path = _latest_artifact(report_dir, pattern)
        if report_path:
            return report_path
    return None


def _backtest_runtime_artifacts(workspace: Path) -> dict[str, str | None]:
    pipeline_path = _latest_artifact(workspace / "memory" / "pipeline_runs", "nightly-*.json")
    report_path = _latest_report(workspace / "memory" / "reports")
    context_path = _latest_artifact(workspace / "memory" / "pipeline_context", "nightly-context-*.json")
    return {
        "pipeline": str(pipeline_path) if pipeline_path else None,
        "report": str(report_path) if report_path else None,
        "market_context": str(context_path) if context_path else None,
    }


def _summarize_prewarm(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {"present": False, "keys": [], "grouped": False}
    grouped = isinstance(payload.get("market_data"), dict) or isinstance(payload.get("news_sentiment"), dict)
    return {
        "present": True,
        "keys": sorted(payload.keys()),
        "grouped": grouped,
    }


def _summarize_pipeline(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {"present": False, "failed": None, "count": 0}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    results = result.get("results") if isinstance(result.get("results"), list) else []
    failed = result.get("failed") if isinstance(result.get("failed"), int) else None
    return {
        "present": True,
        "failed": failed,
        "count": len(results),
    }


def _summarize_report(path: Path | None) -> tuple[dict, str | None]:
    if not path or not path.exists():
        return {"present": False, "lines": 0}, None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {"present": False, "lines": 0}, f"failed to read {path}: {exc}"
    return {
        "present": True,
        "lines": len(text.splitlines()),
    }, None


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _nightly_quality_gate(payload: dict) -> dict:
    workspace = _workspace_dir()
    prewarm_path = _latest_artifact(workspace / "memory" / "prewarm", "nightly-prewarm-*.json")
    pipeline_path = _latest_artifact(workspace / "memory" / "pipeline_runs", "nightly-*.json")
    report_path = _latest_report(workspace / "memory" / "reports")

    prewarm_payload, prewarm_error = _read_json(prewarm_path) if prewarm_path else (None, None)
    pipeline_payload, pipeline_error = _read_json(pipeline_path) if pipeline_path else (None, None)

    prewarm_summary = _summarize_prewarm(prewarm_payload)
    pipeline_summary = _summarize_pipeline(pipeline_payload)
    report_summary, report_error = _summarize_report(report_path)

    checks = [
        {
            "name": "prewarm_present",
            "ok": prewarm_summary["present"] and prewarm_error is None,
            "detail": "latest nightly prewarm artifact",
            "error": prewarm_error,
        },
        {
            "name": "pipeline_present",
            "ok": pipeline_summary["present"] and pipeline_error is None,
            "detail": "latest nightly pipeline run",
            "error": pipeline_error,
        },
        {
            "name": "report_present",
            "ok": report_summary["present"] and report_error is None,
            "detail": "latest nightly report",
            "error": report_error,
        },
    ]

    ok = all(check["ok"] for check in checks)
    stats = {
        "prewarm_keys": len(prewarm_summary["keys"]) if prewarm_summary["present"] else 0,
        "pipeline_steps": pipeline_summary["count"],
        "pipeline_failed": pipeline_summary["failed"],
        "report_lines": report_summary["lines"],
        "grouped_prewarm": prewarm_summary["grouped"],
    }
    artifacts = {
        "prewarm": str(prewarm_path) if prewarm_path else None,
        "pipeline": str(pipeline_path) if pipeline_path else None,
        "report": str(report_path) if report_path else None,
    }

    errors = [error for error in [prewarm_error, pipeline_error, report_error] if error]
    result = {
        "ok": ok,
        "checks": checks,
        "stats": stats,
        "artifacts": artifacts,
        "source": {
            "prewarm": "memory/prewarm",
            "pipeline_runs": "memory/pipeline_runs",
            "reports": "memory/reports",
        },
        "errors": errors,
    }

    out_dir = workspace / "memory" / "quality_gate"
    _ensure_dir(out_dir)
    out_path = out_dir / f"quality-gate-{_timestamp()}.json"
    result["saved_to"] = str(out_path)

    output = _wrap("nightly-quality-gate", payload, result)
    _write_json(out_path, output)
    return output


def _run_quant_validation(command: str, payload: dict) -> dict:
    workspace = _workspace_dir()
    script = workspace / "skills" / "quant-validation" / "scripts" / "dispatch.py"
    cmd = [
        "python3",
        str(script),
        "--command",
        command,
        "--payload",
        json.dumps(payload, ensure_ascii=False),
    ]
    if script.exists():
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False, cwd=workspace)
        raw = (proc.stdout or "").strip()
        try:
            parsed = json.loads(raw.splitlines()[-1]) if raw else None
        except Exception:
            parsed = None
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "raw": raw,
            "json": parsed,
            "cmd": cmd,
        }
    return {
        "ok": False,
        "code": 1,
        "raw": "quant-validation dispatch not found",
        "json": None,
        "cmd": cmd,
    }


def _backtest_loop(payload: dict) -> dict:
    workspace = _workspace_dir()
    invalid_payload = not isinstance(payload, dict)
    run_payload = payload if isinstance(payload, dict) else {}
    run_command = run_payload.get("command") or "nightly-eval-12m"
    if run_command not in {"nightly-eval-12m", "batch-backtest"}:
        run_command = "nightly-eval-12m"

    artifacts = _backtest_runtime_artifacts(workspace)
    if invalid_payload:
        result = {
            "ok": False,
            "source": "quant-validation",
            "command": run_command,
            "reason": "invalid_payload_type",
            "artifacts": artifacts,
            "output": None,
            "raw": None,
            "code": None,
            "cmd": None,
        }
    elif not all(artifacts.values()):
        result = {
            "ok": False,
            "source": "quant-validation",
            "command": run_command,
            "reason": "missing_runtime_artifacts",
            "artifacts": artifacts,
            "output": None,
            "raw": None,
            "code": None,
            "cmd": None,
        }
    else:
        run = _run_quant_validation(run_command, run_payload)
        result = {
            "ok": run.get("ok", False),
            "source": "quant-validation",
            "command": run_command,
            "artifacts": artifacts,
            "output": run.get("json"),
            "raw": run.get("raw"),
            "code": run.get("code"),
            "cmd": run.get("cmd"),
        }

    out_dir = workspace / "memory" / "backtests"
    _ensure_dir(out_dir)
    out_path = out_dir / f"backtest-{_timestamp()}.json"
    result["saved_to"] = str(out_path)

    output = _wrap("backtest-loop", payload, result)
    _write_json(out_path, output)
    return output


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
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps(_fail(args.command, {}, [str(exc)]), ensure_ascii=False))
        return 0

    if args.command == "nightly-quality-gate":
        output = _nightly_quality_gate(payload)
    elif args.command == "backtest-loop":
        output = _backtest_loop(payload)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
