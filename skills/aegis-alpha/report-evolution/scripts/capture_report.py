from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ARTIFACT_DIRECTORIES = {
    "pipeline_run_path": ("memory", "pipeline_runs"),
    "report_path": ("memory", "reports"),
    "market_context_path": ("memory", "pipeline_context"),
}


try:
    from ai_invest_openclaw.evolution_policy import (
        DEFAULT_TIMEZONE,
        OBSERVATION_WINDOWS,
        PHASE1_CAPTURE_PIPELINES,
        PIPELINE_ADVICE_COMMAND,
        PIPELINE_MARKET_CALENDAR,
    )
except ModuleNotFoundError:
    DEFAULT_TIMEZONE = "Asia/Shanghai"
    OBSERVATION_WINDOWS = {
        "nightly": {
            "primary_window": "tplus1_close",
            "windows": [
                "tplus1_intraday",
                "tplus1_close",
                "tplus3_close",
            ],
        }
    }
    PHASE1_CAPTURE_PIPELINES = {"nightly"}
    PIPELINE_ADVICE_COMMAND = {"nightly": "nightly-strategy"}
    PIPELINE_MARKET_CALENDAR = {"nightly": "cn-a-share"}


@dataclass
class RuntimeArtifacts:
    pipeline_run_path: Path
    report_path: Path
    market_context_path: Path
    subagent_run_id: str
    prompt_bundle: dict
    subagent_manifest: dict
    subagent_outputs: list[Path]


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_artifact(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _parse_stamp(value: str, pattern: str) -> str | None:
    match = re.search(pattern, value)
    return match.group(1) if match else None


def _report_stamp(report_path: Path, pipeline_id: str) -> str | None:
    return _parse_stamp(report_path.name, rf"^{re.escape(pipeline_id)}-report-(\d{{8}}-\d{{6}})\.md$")


def _run_stamp(pipeline_path: Path, pipeline_id: str) -> str | None:
    return _parse_stamp(pipeline_path.name, rf"^{re.escape(pipeline_id)}-(\d{{8}}-\d{{6}})\.json$")


def _context_stamp(context_path: Path, pipeline_id: str) -> str | None:
    return _parse_stamp(context_path.name, rf"^{re.escape(pipeline_id)}-context-(\d{{8}}-\d{{6}})\.json$")


def _extract_prompt_bundle(pipeline_payload: dict, pipeline_id: str) -> dict:
    advice_command = PIPELINE_ADVICE_COMMAND.get(pipeline_id)
    results = pipeline_payload.get("results") if isinstance(pipeline_payload.get("results"), list) else []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("package") != "advice-lifecycle":
            continue
        if advice_command and entry.get("command") != advice_command:
            continue
        output = entry.get("output")
        if isinstance(output, dict):
            result = output.get("result") if isinstance(output.get("result"), dict) else None
            if result and isinstance(result.get("prompt"), dict):
                return result.get("prompt") or {}
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                result = parsed.get("result") if isinstance(parsed.get("result"), dict) else None
                if result and isinstance(result.get("prompt"), dict):
                    return result.get("prompt") or {}
    return {}


def _load_subagent_manifest(workspace: Path, run_id: str) -> dict:
    runs_path = workspace / "memory" / "subagents" / "runs.jsonl"
    if not runs_path.exists():
        return {"run_id": run_id, "tasks": []}
    try:
        lines = runs_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"run_id": run_id, "tasks": []}
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("run_id") == run_id:
            return entry
    return {"run_id": run_id, "tasks": []}


def _collect_subagent_outputs(workspace: Path, run_id: str) -> list[Path]:
    run_dir = workspace / "memory" / "subagents" / run_id
    if not run_dir.exists():
        return []
    return sorted([path for path in run_dir.glob("*.md") if path.is_file()])


def _resolve_artifact_path(workspace: Path, payload: dict, field: str, pattern: str) -> tuple[Path | None, dict | None]:
    raw_path = payload.get(field)
    expected_root = workspace.joinpath(*ARTIFACT_DIRECTORIES[field]).resolve()
    if raw_path:
        candidate = Path(str(raw_path)).expanduser()
        if not candidate.is_absolute():
            candidate = workspace / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(workspace.resolve())
        except ValueError:
            return None, {"ok": False, "error": "artifact_path_outside_workspace", "field": field, "path": str(resolved)}
        try:
            resolved.relative_to(expected_root)
        except ValueError:
            return None, {"ok": False, "error": "artifact_path_invalid_location", "field": field, "path": str(resolved)}
        if not resolved.exists() or not resolved.is_file():
            return None, {"ok": False, "error": "missing_explicit_artifact", "field": field, "path": str(resolved)}
        return resolved, None
    return _latest_artifact(expected_root, pattern), None


def _resolve_runtime_artifacts(workspace: Path, pipeline_id: str, payload: dict) -> tuple[RuntimeArtifacts | None, dict | None]:
    pipeline_path, pipeline_error = _resolve_artifact_path(workspace, payload, "pipeline_run_path", f"{pipeline_id}-*.json")
    if pipeline_error:
        return None, pipeline_error
    report_path, report_error = _resolve_artifact_path(workspace, payload, "report_path", f"{pipeline_id}-report-*.md")
    if report_error:
        return None, report_error
    context_path, context_error = _resolve_artifact_path(workspace, payload, "market_context_path", f"{pipeline_id}-context-*.json")
    if context_error:
        return None, context_error

    if not pipeline_path or not report_path or not context_path:
        return None, None

    report_stamp = _report_stamp(report_path, pipeline_id)
    subagent_run_id = payload.get("subagent_run_id") or (f"{pipeline_id}-{report_stamp}" if report_stamp else pipeline_id)

    try:
        pipeline_payload = _read_json(pipeline_path)
    except json.JSONDecodeError:
        return None, {"ok": False, "error": "invalid_pipeline_payload", "path": str(pipeline_path)}
    prompt_bundle = _extract_prompt_bundle(pipeline_payload, pipeline_id)
    subagent_manifest = _load_subagent_manifest(workspace, subagent_run_id)
    subagent_outputs = _collect_subagent_outputs(workspace, subagent_run_id)

    return RuntimeArtifacts(
        pipeline_run_path=pipeline_path,
        report_path=report_path,
        market_context_path=context_path,
        subagent_run_id=subagent_run_id,
        prompt_bundle=prompt_bundle,
        subagent_manifest=subagent_manifest,
        subagent_outputs=subagent_outputs,
    ), None


def _effective_trade_date(report_stamp: str) -> str:
    date_part = report_stamp.split("-")[0]
    base = datetime.strptime(date_part, "%Y%m%d").date()
    return (base + timedelta(days=1)).isoformat()


def _build_metadata(runtime: RuntimeArtifacts, pipeline_id: str, snapshot_version: int) -> dict:
    report_stamp = _report_stamp(runtime.report_path, pipeline_id) or ""
    run_stamp = _run_stamp(runtime.pipeline_run_path, pipeline_id) or ""
    market_context_stamp = _context_stamp(runtime.market_context_path, pipeline_id) or ""
    market_calendar = PIPELINE_MARKET_CALENDAR.get(pipeline_id, "")
    effective_trade_date = _effective_trade_date(report_stamp) if report_stamp else ""
    report_id = f"{pipeline_id}-{report_stamp}-td{effective_trade_date}-{market_calendar}-sv{snapshot_version}"
    observation = OBSERVATION_WINDOWS.get(pipeline_id, {"primary_window": None, "windows": []})
    windows = observation.get("windows") if isinstance(observation.get("windows"), list) else []
    observation_windows = {
        "primary_window": observation.get("primary_window"),
        "windows": [
            {"key": key, "offset": None, "unit": None, "anchor": None}
            if isinstance(key, str)
            else key
            for key in windows
        ],
    }
    return {
        "report_id": report_id,
        "pipeline_id": pipeline_id,
        "report_stamp": report_stamp,
        "run_stamp": run_stamp,
        "context_stamp": market_context_stamp,
        "snapshot_version": snapshot_version,
        "timezone": DEFAULT_TIMEZONE,
        "market_calendar": market_calendar,
        "effective_trade_date": effective_trade_date,
        "observation_windows": observation_windows,
        "pipeline_run_path": str(runtime.pipeline_run_path),
        "report_path": str(runtime.report_path),
        "market_context_path": str(runtime.market_context_path),
        "pipeline_run_digest": _file_digest(runtime.pipeline_run_path),
        "report_digest": _file_digest(runtime.report_path),
        "market_context_digest": _file_digest(runtime.market_context_path),
        "subagent_run_id": runtime.subagent_run_id,
        "system_version": "phase1-bootstrap",
        "persona_bundle_version": "unconfigured",
    }


def _build_outcome_placeholder(metadata: dict) -> dict:
    return {
        "report_id": metadata.get("report_id"),
        "status": "pending",
        "market_calendar": metadata.get("market_calendar"),
        "effective_trade_date": metadata.get("effective_trade_date"),
        "observation_windows": metadata.get("observation_windows"),
        "fills": [],
        "notes": ["phase1 placeholder: no realized market outcome recorded yet"],
    }


def _copy_subagents(subagent_outputs: list[Path], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in subagent_outputs:
        if path.is_file():
            shutil.copy2(path, destination / path.name)


def _same_sources(metadata: dict, runtime: RuntimeArtifacts) -> bool:
    return (
        str(runtime.pipeline_run_path) == metadata.get("pipeline_run_path")
        and str(runtime.report_path) == metadata.get("report_path")
        and str(runtime.market_context_path) == metadata.get("market_context_path")
        and metadata.get("pipeline_run_digest") == _file_digest(runtime.pipeline_run_path)
        and metadata.get("report_digest") == _file_digest(runtime.report_path)
        and metadata.get("market_context_digest") == _file_digest(runtime.market_context_path)
        and runtime.subagent_run_id == metadata.get("subagent_run_id")
    )


def capture_report_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    pipeline_id = str(payload.get("pipeline_id") or "")
    if pipeline_id not in PHASE1_CAPTURE_PIPELINES:
        return {"ok": False, "error": "unsupported_phase1_pipeline", "pipeline_id": pipeline_id}

    workspace = _workspace_dir()
    runtime, resolve_error = _resolve_runtime_artifacts(workspace, pipeline_id, payload)
    if resolve_error is not None:
        return resolve_error | {"pipeline_id": pipeline_id}
    if runtime is None:
        return {"ok": False, "error": "missing_runtime_artifacts", "pipeline_id": pipeline_id}

    snapshot_version = int(payload.get("snapshot_version") or 0)
    try:
        metadata = _build_metadata(runtime, pipeline_id, snapshot_version)
    except ValueError:
        return {"ok": False, "error": "invalid_report_stamp", "path": str(runtime.report_path), "pipeline_id": pipeline_id}
    report_id = metadata["report_id"]

    evidence_dir = workspace / "memory" / "report_evidence" / pipeline_id / report_id
    if (evidence_dir / "metadata.json").exists():
        existing = _read_json(evidence_dir / "metadata.json")
        if existing.get("report_id") == report_id and _same_sources(existing, runtime):
            return {"ok": True, "saved_to": str(evidence_dir), "report_id": report_id, "idempotent": True}
        return {"ok": False, "error": "duplicate_runtime_report_id", "report_id": report_id}

    evidence_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(runtime.pipeline_run_path, evidence_dir / "pipeline.json")
    shutil.copy2(runtime.report_path, evidence_dir / "final-report.md")
    shutil.copy2(runtime.market_context_path, evidence_dir / "market-context.json")

    _write_json(evidence_dir / "prompt-bundle.json", runtime.prompt_bundle)
    _write_json(evidence_dir / "metadata.json", metadata)
    _write_json(evidence_dir / "outcome.json", _build_outcome_placeholder(metadata))
    _write_json(evidence_dir / "subagent-manifest.json", runtime.subagent_manifest)

    _copy_subagents(runtime.subagent_outputs, evidence_dir / "subagents")

    return {"ok": True, "saved_to": str(evidence_dir), "report_id": report_id, "idempotent": False}
