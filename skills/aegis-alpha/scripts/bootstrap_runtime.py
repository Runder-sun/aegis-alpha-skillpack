#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODES = (
    "offline-research",
    "agent-native",
    "api-assisted",
    "manual-portfolio",
    "report-review",
    "full-institutional",
)
DATA_SOURCE_MODES = ("auto", "manual_payload", "agent_native", "skill_api", "cache_or_prewarm")
HEARTBEAT_MODES = ("none", "manual", "daily-prewarm", "market-heartbeat", "full")
AGENTS = ("auto", "codex", "claude-code", "hermes", "openclaw", "unknown")
API_ENV_GROUPS = {
    "research_search": ("TAVILY_API_KEYS", "QVERIS_API_KEY"),
    "document_parse": ("MINERU_API_KEY",),
    "market_data": ("TUSHARE_TOKEN", "FINNHUB_API_KEY"),
    "market_intel": ("JIN10_API_KEY", "TAVILY_API_KEYS", "QVERIS_API_KEY"),
    "external_push": ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID", "FEISHU_CHAT_ID"),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _skillpack_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    env = os.environ.get("AEGIS_ALPHA_WORKSPACE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _detect_agent(explicit: str) -> str:
    if explicit != "auto":
        return explicit
    env_agent = os.environ.get("AEGIS_ALPHA_AGENT")
    if env_agent in AGENTS and env_agent != "auto":
        return env_agent
    probe = " ".join(
        [
            str(Path.cwd()),
            str(Path(__file__).resolve()),
            os.environ.get("CODEX_HOME", ""),
            os.environ.get("CLAUDE_CODE_SKILLS_HOME", ""),
            os.environ.get("HERMES_HOME", ""),
            os.environ.get("OPENCLAW_HOME", ""),
        ]
    )
    if ".codex" in probe or os.environ.get("CODEX_HOME"):
        return "codex"
    if ".claude" in probe or os.environ.get("CLAUDE_CODE_SKILLS_HOME"):
        return "claude-code"
    if ".hermes" in probe or os.environ.get("HERMES_HOME"):
        return "hermes"
    if ".openclaw" in probe or os.environ.get("OPENCLAW_HOME"):
        return "openclaw"
    return "unknown"


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _api_capabilities() -> dict[str, Any]:
    groups: dict[str, Any] = {}
    for group, names in API_ENV_GROUPS.items():
        present = [name for name in names if os.environ.get(name)]
        groups[group] = {
            "configured": bool(present),
            "present_env": present,
            "missing_env": [name for name in names if name not in present],
        }
    return groups


def _latest_prewarm(workspace: Path) -> dict[str, Any]:
    prewarm_dir = workspace / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return {"available": False, "reason": "prewarm_directory_missing"}
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {"available": False, "reason": "prewarm_artifact_missing"}
    latest = files[0]
    age_seconds = max(0.0, time.time() - latest.stat().st_mtime)
    return {
        "available": True,
        "artifact": str(latest),
        "age_seconds": age_seconds,
        "stale_12h": age_seconds > 12 * 3600,
    }


def _default_data_source_mode(mode: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if mode in {"offline-research", "manual-portfolio", "report-review"}:
        return "manual_payload"
    if mode == "agent-native":
        return "agent_native"
    if mode in {"api-assisted", "full-institutional"}:
        return "skill_api"
    return "manual_payload"


def _capability_level(mode: str, data_source_mode: str, api: dict[str, Any], prewarm: dict[str, Any]) -> str:
    any_api = any(group.get("configured") for group in api.values())
    has_prewarm = bool(prewarm.get("available"))
    if mode == "full-institutional" and any_api and has_prewarm:
        return "full"
    if data_source_mode == "agent_native":
        return "agent-native"
    if data_source_mode == "skill_api" and any_api:
        return "api-assisted"
    if has_prewarm:
        return "cache-ready"
    return "offline"


def _next_actions(mode: str, data_source_mode: str, heartbeat: str, api: dict[str, Any], prewarm: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if data_source_mode == "skill_api" and not any(group.get("configured") for group in api.values()):
        actions.append("Configure at least one skill API key in the runtime environment or workspace .env.")
    if data_source_mode in {"skill_api", "cache_or_prewarm"} and not prewarm.get("available"):
        actions.append("Run execution-automation morning-prewarm or nightly-prewarm before market-data workflows.")
    if heartbeat != "none":
        actions.append("Read references/automation-playbook.md and let the current agent configure supported automations.")
    if mode == "full-institutional" and heartbeat in {"none", "manual"}:
        actions.append("Full institutional mode normally expects daily prewarm or market heartbeat automation.")
    if not actions:
        actions.append("Runtime profile is ready for the selected mode.")
    return actions


def _ensure_workspace(workspace: Path) -> None:
    for rel in (
        "config",
        "memory/prewarm",
        "memory/reports",
        "memory/automation",
        "logs",
    ):
        (workspace / rel).mkdir(parents=True, exist_ok=True)


def build_profile(args: argparse.Namespace) -> dict[str, Any]:
    workspace = _workspace(args.workspace)
    agent = _detect_agent(args.agent)
    data_source_mode = _default_data_source_mode(args.mode, args.data_source)
    api = _api_capabilities()
    prewarm = _latest_prewarm(workspace)
    provider_capabilities = _load_json(_skillpack_root() / "data" / "provider-capabilities.json", {})
    automation_jobs = _load_json(_skillpack_root() / "data" / "automation-jobs.json", {})
    return {
        "schema_version": 1,
        "package": "aegis-alpha",
        "created_at": _now(),
        "updated_at": _now(),
        "agent": agent,
        "mode": args.mode,
        "capability_level": _capability_level(args.mode, data_source_mode, api, prewarm),
        "workspace": str(workspace),
        "data_source_mode": data_source_mode,
        "automation": {
            "heartbeat_mode": args.heartbeat,
            "external_push": args.external_push,
            "configured_by_agent": False,
            "job_count": len(automation_jobs.get("jobs", [])) if isinstance(automation_jobs, dict) else 0,
        },
        "providers": {
            "api": api,
            "prewarm": prewarm,
            "agent_provider_order": provider_capabilities.get(agent, {}) if isinstance(provider_capabilities, dict) else {},
        },
        "safety": {
            "decision_allowed": False,
            "requires_human_confirmation": True,
            "external_push_requires_confirmation": args.external_push != "disabled",
            "live_trading_allowed": False,
        },
        "next_actions": _next_actions(args.mode, data_source_mode, args.heartbeat, api, prewarm),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Aegis Alpha runtime profile.")
    parser.add_argument("--agent", choices=AGENTS, default="auto")
    parser.add_argument("--mode", choices=MODES, default="offline-research")
    parser.add_argument("--data-source", choices=DATA_SOURCE_MODES, default="auto")
    parser.add_argument("--heartbeat", choices=HEARTBEAT_MODES, default="none")
    parser.add_argument("--external-push", choices=("disabled", "confirm-only"), default="disabled")
    parser.add_argument("--workspace")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = _workspace(args.workspace)
    profile = build_profile(args)
    profile_path = workspace / "config" / "runtime-profile.json"
    if not args.dry_run:
        _ensure_workspace(workspace)
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "dry_run": args.dry_run,
        "profile_path": str(profile_path),
        "profile": profile,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
