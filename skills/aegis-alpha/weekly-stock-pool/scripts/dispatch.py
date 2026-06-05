from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "package": "weekly-stock-pool",
        "command": command,
        "payload": payload,
        "as_of": _now_iso(),
        "freshness": {"status": "unknown", "max_age_minutes": None},
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "research_only",
        "source": "weekly-stock-pool",
        "sources": [
            "memory/pipeline_runs/weekly-*.json",
            "memory/pipeline_context/weekly-context-*.json",
            "memory/prewarm/nightly-prewarm-*.json",
        ],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], missing: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["errors"] = list(dict.fromkeys(errors))
    output["missing_critical_inputs"] = list(dict.fromkeys(missing))
    output["warnings"] = warnings or []
    output["result"] = {
        "candidate_count": 0,
        "candidates": None,
        "filters": [],
        "pool_state": "unavailable",
        "failure_policy": "fail_closed",
    }
    return output


def _success(command: str, payload: dict[str, Any], result: dict[str, Any], warnings: list[str], artifacts: list[str]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = True
    output["freshness"] = {"status": "artifact_derived", "max_age_minutes": payload.get("max_age_minutes")}
    output["warnings"] = warnings
    output["artifacts"] = artifacts
    output["result"] = result
    return output


def _load_latest_weekly_runs() -> tuple[list[dict], list[str], list[str]]:
    runs_dir = _workspace_dir() / "memory" / "pipeline_runs"
    if not runs_dir.exists():
        return [], [], []
    files = sorted(runs_dir.glob("weekly-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    runs: list[dict] = []
    errors: list[str] = []
    artifacts: list[str] = []
    for path in files[:2]:
        payload, error = _read_json(path)
        if error:
            errors.append(error)
        if isinstance(payload, dict):
            runs.append(payload)
            artifacts.append(str(path))
    return runs, errors, artifacts


def _load_latest_weekly_context() -> tuple[list[dict], list[str], list[str]]:
    ctx_dir = _workspace_dir() / "memory" / "pipeline_context"
    if not ctx_dir.exists():
        return [], [], []
    files = sorted(ctx_dir.glob("weekly-context-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    contexts: list[dict] = []
    errors: list[str] = []
    artifacts: list[str] = []
    for path in files[:2]:
        payload, error = _read_json(path)
        if error:
            errors.append(error)
        if isinstance(payload, list):
            contexts.append({"results": payload, "source": str(path)})
            artifacts.append(str(path))
        elif isinstance(payload, dict):
            contexts.append(payload)
            artifacts.append(str(path))
    return contexts, errors, artifacts


def _load_latest_prewarm() -> tuple[dict | None, str | None, str | None]:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return None, None, None
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, None, None
    payload, error = _read_json(files[0])
    if error:
        return None, error, str(files[0])
    if not isinstance(payload, dict):
        return None, f"prewarm snapshot is not an object: {files[0]}", str(files[0])
    return payload, None, str(files[0])


def _merge_candidates(items: list[dict], seen: set[str]) -> list[dict]:
    merged: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("symbol") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(item)
    return merged


def _extract_weekly_candidates(runs: list[dict], contexts: list[dict]) -> list[dict]:
    seen: set[str] = set()
    candidates: list[dict] = []

    for payload in runs:
        results = payload.get("result", {}).get("results") if isinstance(payload.get("result"), dict) else []
        if not isinstance(results, list):
            continue
        for entry in results:
            output = entry.get("output") if isinstance(entry, dict) else None
            if isinstance(output, dict) and isinstance(output.get("candidates"), list):
                candidates.extend(_merge_candidates(output.get("candidates"), seen))

    for payload in contexts:
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            continue
        for entry in results:
            output = entry.get("output") if isinstance(entry, dict) else None
            if isinstance(output, dict) and isinstance(output.get("candidates"), list):
                candidates.extend(_merge_candidates(output.get("candidates"), seen))

    return candidates


def _build_filters(runs: list[dict]) -> list[str]:
    filters: list[str] = []
    for payload in runs:
        results = payload.get("result", {}).get("results") if isinstance(payload.get("result"), dict) else []
        if not isinstance(results, list):
            continue
        for entry in results:
            if not isinstance(entry, dict):
                continue
            if entry.get("package") == "quality-gate" and entry.get("command") == "backtest-loop":
                filters.append("backtest-loop")
            if entry.get("package") == "theme-cycle" and entry.get("command") == "global-medium-long-strategy":
                filters.append("global-medium-long-strategy")
            if entry.get("package") == "macro-regime" and entry.get("command") == "global-macro-analysis":
                filters.append("global-macro-analysis")
    return list(dict.fromkeys(filters))


def _build_result(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    runs, run_errors, run_artifacts = _load_latest_weekly_runs()
    contexts, context_errors, context_artifacts = _load_latest_weekly_context()
    prewarm, prewarm_error, prewarm_artifact = _load_latest_prewarm()
    read_errors = [error for error in [*run_errors, *context_errors, prewarm_error] if error]

    missing: list[str] = []
    errors: list[str] = []
    if not runs:
        missing.append("weekly_pipeline_runs")
        errors.append("weekly_pipeline_runs_missing")
    if not contexts:
        missing.append("weekly_pipeline_context")
        errors.append("weekly_pipeline_context_missing")
    if prewarm is None:
        missing.append("prewarm_snapshot")
        errors.append("prewarm_snapshot_missing")
    if read_errors:
        errors.extend("artifact_read_error" for _ in read_errors)

    if errors:
        return _fail(command, payload, errors, missing, read_errors)

    candidates = _extract_weekly_candidates(runs, contexts)
    min_candidates = int(payload.get("min_candidates", 1) or 1)
    if len(candidates) < min_candidates:
        return _fail(
            command,
            payload,
            ["candidates_missing"],
            ["weekly_candidates"],
            [f"extracted {len(candidates)} candidates; required at least {min_candidates}"],
        )

    filters = _build_filters(runs)
    result = {
        "candidate_count": len(candidates),
        "candidates": candidates,
        "filters": filters,
        "pool_state": "available",
        "prewarm_keys": sorted(prewarm.keys()) if isinstance(prewarm, dict) else [],
        "source": {
            "pipeline_runs": "memory/pipeline_runs/weekly-*.json",
            "pipeline_context": "memory/pipeline_context/weekly-context-*.json",
            "prewarm": "memory/prewarm/nightly-prewarm-*.json",
        },
    }
    artifacts = [*run_artifacts, *context_artifacts]
    if prewarm_artifact:
        artifacts.append(prewarm_artifact)
    return _success(command, payload, result, [], artifacts)


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

    payload = json.loads(args.payload or "{}")
    if args.command == "weekly-stock-pool":
        output = _build_result(args.command, payload)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    if payload.get("write_artifact", True) and output.get("ok") is True:
        try:
            workspace = _workspace_dir()
            out_dir = workspace / "memory" / "stock_pool"
            _ensure_dir(out_dir)
            out_path = out_dir / f"weekly-stock-pool-{_timestamp()}.json"
            out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            output.setdefault("artifacts", []).append(str(out_path))
        except OSError as exc:
            output["ok"] = False
            output.setdefault("errors", []).append("artifact_write_failed")
            output.setdefault("warnings", []).append(str(exc))
            output.setdefault("missing_critical_inputs", []).append("writable_stock_pool_artifact_path")

    print(json.dumps(output, ensure_ascii=False))
    return 0 if output.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
