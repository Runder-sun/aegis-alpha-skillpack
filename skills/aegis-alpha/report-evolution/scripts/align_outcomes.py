from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ai_invest_openclaw.evolution_policy import PHASE1_ALIGN_PIPELINES
except ModuleNotFoundError:
    PHASE1_ALIGN_PIPELINES = {"nightly"}

try:
    from capture_report import _read_json, _write_json, _workspace_dir
except ModuleNotFoundError:
    from .capture_report import _read_json, _write_json, _workspace_dir


SOURCE_LABEL = "report-evolution-phase1"


SAFE_PATH_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _safe_path_token(value: Any) -> str | None:
    token = str(value or "")
    if not token or any(char not in SAFE_PATH_CHARS for char in token):
        return None
    return token


def _safe_relative_dir(root: Path, token: str) -> Path | None:
    candidate = (root / token).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _latest_evidence_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    root_resolved = root.resolve()
    candidates: list[Path] = []
    for path in root.glob("*/metadata.json"):
        if not path.is_file():
            continue
        try:
            candidate_dir = path.parent.resolve()
            candidate_dir.relative_to(root_resolved)
        except ValueError:
            continue
        candidates.append(candidate_dir)
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def _resolve_evidence_dir(workspace: Path, payload: dict[str, Any]) -> Path | None:
    pipeline_id = _safe_path_token(payload.get("pipeline_id"))
    if not pipeline_id:
        return None
    evidence_root = (workspace / "memory" / "report_evidence").resolve()
    expected_root = _safe_relative_dir(evidence_root, pipeline_id)
    if expected_root is None:
        return None
    raw_report_id = payload.get("report_id")
    if raw_report_id is None or str(raw_report_id) == "":
        return _latest_evidence_dir(expected_root)
    report_id = _safe_path_token(raw_report_id)
    if report_id is None:
        return None
    evidence_dir = _safe_relative_dir(expected_root, report_id)
    if evidence_dir is None:
        return None
    if not (evidence_dir / "metadata.json").exists():
        return None
    return evidence_dir


def _validated_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    report_id = metadata.get("report_id")
    market_calendar = metadata.get("market_calendar")
    effective_trade_date = metadata.get("effective_trade_date")
    observation_windows = metadata.get("observation_windows")
    report_stamp = _safe_path_token(metadata.get("report_stamp"))
    pipeline_id = _safe_path_token(metadata.get("pipeline_id"))
    snapshot_version = metadata.get("snapshot_version")
    if (
        not isinstance(report_id, str)
        or not report_id
        or not isinstance(market_calendar, str)
        or not market_calendar
        or not isinstance(effective_trade_date, str)
        or not effective_trade_date
        or not isinstance(observation_windows, dict)
        or report_stamp is None
        or pipeline_id is None
        or not isinstance(snapshot_version, int)
    ):
        return None
    return {
        **metadata,
        "report_id": report_id,
        "market_calendar": market_calendar,
        "effective_trade_date": effective_trade_date,
        "observation_windows": observation_windows,
        "report_stamp": report_stamp,
        "pipeline_id": pipeline_id,
        "snapshot_version": snapshot_version,
    }


def _build_outcome(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": metadata["report_id"],
        "status": "pending",
        "market_calendar": metadata["market_calendar"],
        "effective_trade_date": metadata["effective_trade_date"],
        "observation_windows": metadata["observation_windows"],
        "fills": [],
        "notes": ["phase1 placeholder: no realized market outcome recorded yet"],
    }


def _build_version(metadata: dict[str, Any], version_id: str) -> dict[str, Any]:
    return {
        "version_id": version_id,
        "parent_version": None,
        "proposal_ids": [],
        "changed_files": [],
        "persona_versions": {},
        "evaluation_summary": {"status": "pending", "source": SOURCE_LABEL},
        "base_snapshot_version": metadata["snapshot_version"],
        "activated_snapshot_version": None,
        "release_state": "shadow",
        "rollback_to": None,
        "report_ids": [metadata["report_id"]],
    }


def align_report_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    pipeline_id = str(payload.get("pipeline_id") or "")
    if pipeline_id not in PHASE1_ALIGN_PIPELINES:
        return {"ok": False, "error": "unsupported_phase1_pipeline", "pipeline_id": pipeline_id}

    workspace = _workspace_dir()
    evidence_dir = _resolve_evidence_dir(workspace, payload)
    if evidence_dir is None:
        return {"ok": False, "error": "report_evidence_not_found"}

    metadata = _read_json(evidence_dir / "metadata.json")
    validated_metadata = _validated_metadata(metadata)
    if validated_metadata is None:
        return {"ok": False, "error": "invalid_evidence_metadata", "report_id": metadata.get("report_id")}

    outcome = _build_outcome(validated_metadata)
    _write_json(evidence_dir / "outcome.json", outcome)

    version_id = (
        f"evo-{validated_metadata['report_stamp']}-{validated_metadata['pipeline_id']}-sv{validated_metadata['snapshot_version']}"
    )
    log_dir = workspace / "memory" / "evolution" / "logs"
    version_dir = workspace / "memory" / "evolution" / "versions"
    rollback_dir = workspace / "memory" / "evolution" / "rollback"
    log_path = log_dir / f"align-{validated_metadata['report_stamp']}.json"
    version_path = version_dir / f"{version_id}.json"
    current_path = version_dir / "current.json"
    rollback_path = rollback_dir / "latest.json"

    _write_json(
        log_path,
        {
            "command": "align-report-outcome",
            "report_id": metadata["report_id"],
            "status": outcome["status"],
            "version_id": version_id,
        },
    )

    version = _build_version(metadata, version_id)
    _write_json(version_path, version)
    _write_json(current_path, version)
    _write_json(
        rollback_path,
        {
            "status": "not-requested",
            "current_version": version_id,
            "rollback_to": None,
            "source": SOURCE_LABEL,
        },
    )

    return {
        "ok": True,
        "saved_to": str(log_path),
        "report_id": metadata["report_id"],
        "version_id": version_id,
    }
