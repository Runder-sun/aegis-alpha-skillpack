#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEGACY_MODES = (
    "offline-research",
    "agent-native",
    "api-assisted",
    "manual-portfolio",
    "report-review",
    "full-institutional",
)
PRESETS = {
    "quick-research": {
        "workflow_scope": "core-research",
        "provider_priority": ["agent_native", "skill_api"],
        "cache_policy": "read-if-fresh",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "none",
        "heartbeat": "none",
    },
    "daily-desk": {
        "workflow_scope": "market-desk",
        "provider_priority": ["skill_api", "agent_native"],
        "cache_policy": "refresh-if-stale",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "none",
        "heartbeat": "daily-prewarm",
    },
    "portfolio-desk": {
        "workflow_scope": "portfolio-review",
        "provider_priority": ["skill_api", "agent_native"],
        "cache_policy": "read-if-fresh",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
        "heartbeat": "manual",
    },
    "report-review": {
        "workflow_scope": "report-review",
        "provider_priority": ["agent_native", "skill_api"],
        "cache_policy": "cache-first",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
        "heartbeat": "none",
    },
    "full-institutional": {
        "workflow_scope": "full-institutional",
        "provider_priority": ["skill_api", "agent_native"],
        "cache_policy": "prewarm-required",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
        "heartbeat": "market-heartbeat",
    },
}
LEGACY_MODE_MAP = {
    "offline-research": {
        "preset": "quick-research",
        "workflow_scope": "core-research",
        "provider_priority": [],
        "cache_policy": "none",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "none",
    },
    "agent-native": {
        "preset": "quick-research",
        "workflow_scope": "core-research",
        "provider_priority": ["agent_native"],
        "cache_policy": "read-if-fresh",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "none",
    },
    "api-assisted": {
        "preset": "daily-desk",
        "workflow_scope": "market-desk",
        "provider_priority": ["skill_api", "agent_native"],
        "cache_policy": "refresh-if-stale",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "none",
    },
    "manual-portfolio": {
        "preset": "portfolio-desk",
        "workflow_scope": "portfolio-review",
        "provider_priority": [],
        "cache_policy": "read-if-fresh",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
    },
    "report-review": {
        "preset": "report-review",
        "workflow_scope": "report-review",
        "provider_priority": ["agent_native"],
        "cache_policy": "cache-first",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
    },
    "full-institutional": {
        "preset": "full-institutional",
        "workflow_scope": "full-institutional",
        "provider_priority": ["skill_api", "agent_native"],
        "cache_policy": "prewarm-required",
        "manual_input_policy": "ask-when-missing",
        "portfolio_source": "manual-ledger",
    },
}
WORKFLOW_SCOPES = ("auto", "core-research", "market-desk", "portfolio-review", "report-review", "full-institutional")
PORTFOLIO_SOURCES = ("auto", "none", "manual-ledger", "imported-file", "read-only-api")
PORTFOLIO_MODES = PORTFOLIO_SOURCES
DATA_PROVIDERS = ("agent_native", "skill_api")
LEGACY_MANUAL_PROVIDER = "manual_payload"
LEGACY_CACHE_PROVIDER = "cache_or_prewarm"
DATA_SOURCE_MODES = ("auto", "none") + DATA_PROVIDERS + (LEGACY_MANUAL_PROVIDER, LEGACY_CACHE_PROVIDER)
CACHE_POLICIES = ("auto", "none", "read-if-fresh", "cache-first", "refresh-if-stale", "prewarm-required")
MANUAL_INPUT_POLICIES = ("auto", "ask-when-missing", "disabled")
HEARTBEAT_MODES = ("auto", "none", "manual", "daily-prewarm", "market-heartbeat", "full")
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


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _parse_provider_priority(raw: str) -> tuple[list[str] | None, bool, bool]:
    if raw == "auto":
        return None, False, False
    providers = [item.strip() for item in raw.split(",") if item.strip()]
    cache_requested = LEGACY_CACHE_PROVIDER in providers
    manual_requested = LEGACY_MANUAL_PROVIDER in providers
    providers = [item for item in providers if item not in {LEGACY_CACHE_PROVIDER, LEGACY_MANUAL_PROVIDER, "none"}]
    invalid = [item for item in providers if item not in DATA_PROVIDERS]
    if invalid:
        raise SystemExit(f"Invalid --data-providers value(s): {', '.join(invalid)}")
    return _dedupe(providers), cache_requested, manual_requested


def _legacy_config(mode: str | None) -> dict[str, Any] | None:
    if not mode:
        return None
    return LEGACY_MODE_MAP.get(mode)


def _resolved_preset(args: argparse.Namespace) -> str:
    legacy = _legacy_config(args.mode)
    if args.preset != "auto":
        return args.preset
    if legacy:
        return str(legacy["preset"])
    return "quick-research"


def _preset_defaults(args: argparse.Namespace) -> dict[str, Any]:
    preset = _resolved_preset(args)
    defaults = dict(PRESETS[preset])
    legacy = _legacy_config(args.mode)
    if legacy and args.preset == "auto":
        defaults.update(legacy)
    defaults["preset"] = preset
    return defaults


def _provider_priority(args: argparse.Namespace, defaults: dict[str, Any]) -> tuple[list[str], bool, bool]:
    explicit, cache_requested, manual_requested = _parse_provider_priority(args.data_providers)
    if explicit is not None:
        return explicit, cache_requested, manual_requested
    if args.data_source != "auto":
        if args.data_source not in DATA_SOURCE_MODES:
            raise SystemExit(f"Invalid --data-source value: {args.data_source}")
        if args.data_source == "none":
            return [], False, False
        if args.data_source == LEGACY_CACHE_PROVIDER:
            return [], True, False
        if args.data_source == LEGACY_MANUAL_PROVIDER:
            return [], False, True
        return [args.data_source], False, False
    return list(defaults["provider_priority"]), False, False


def _cache_policy(args: argparse.Namespace, defaults: dict[str, Any], cache_requested: bool) -> str:
    if args.cache_policy != "auto":
        return args.cache_policy
    if cache_requested:
        return "cache-first"
    return str(defaults.get("cache_policy") or "none")


def _manual_input_policy(args: argparse.Namespace, defaults: dict[str, Any], manual_requested: bool) -> str:
    if args.manual_input != "auto":
        return args.manual_input
    if manual_requested:
        return "ask-when-missing"
    return str(defaults.get("manual_input_policy") or "ask-when-missing")


def _resolve_auto_fields(args: argparse.Namespace) -> dict[str, Any]:
    defaults = _preset_defaults(args)
    provider_priority, cache_requested, manual_requested = _provider_priority(args, defaults)
    cache_policy = _cache_policy(args, defaults, cache_requested)
    manual_input_policy = _manual_input_policy(args, defaults, manual_requested)
    workflow_scope = args.workflow_scope if args.workflow_scope != "auto" else str(defaults["workflow_scope"])
    requested_portfolio_source = args.portfolio_source if args.portfolio_source != "auto" else args.portfolio_mode
    portfolio_source = requested_portfolio_source if requested_portfolio_source != "auto" else str(defaults["portfolio_source"])
    heartbeat = args.heartbeat if args.heartbeat != "auto" else str(defaults["heartbeat"])
    return {
        "preset": str(defaults["preset"]),
        "workflow_scope": workflow_scope,
        "portfolio_source": portfolio_source,
        "cache_policy": cache_policy,
        "manual_input_policy": manual_input_policy,
        "heartbeat": heartbeat,
        "provider_priority": provider_priority,
        "data_source_mode": provider_priority[0] if provider_priority else "none",
    }


def _capability_level(workflow_scope: str, provider_priority: list[str], cache_policy: str, heartbeat: str, api: dict[str, Any], prewarm: dict[str, Any]) -> str:
    any_api = any(group.get("configured") for group in api.values())
    has_prewarm = bool(prewarm.get("available"))
    has_agent_native = "agent_native" in provider_priority
    if workflow_scope == "full-institutional" and cache_policy == "prewarm-required" and not has_prewarm:
        return "institutional-needs-prewarm"
    if workflow_scope == "full-institutional" and (any_api or has_agent_native):
        return "institutional-ready" if heartbeat not in {"none", "manual"} else "institutional-manual"
    if "skill_api" in provider_priority and any_api and has_agent_native:
        return "hybrid-agent-api"
    if "skill_api" in provider_priority and any_api:
        return "api-ready"
    if has_agent_native:
        return "agent-native-ready"
    if cache_policy != "none" and has_prewarm:
        return "cache-ready"
    return "offline"


def _next_actions(workflow_scope: str, provider_priority: list[str], cache_policy: str, manual_input_policy: str, heartbeat: str, portfolio_source: str, api: dict[str, Any], prewarm: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if "skill_api" in provider_priority and not any(group.get("configured") for group in api.values()):
        actions.append("Configure at least one skill API key if API-backed data should be used, or put agent_native first for capabilities the current agent can satisfy.")
    if cache_policy in {"cache-first", "refresh-if-stale", "prewarm-required"} and not prewarm.get("available"):
        actions.append("Run execution-automation morning-prewarm or nightly-prewarm before cache-dependent workflows.")
    if not provider_priority and manual_input_policy == "disabled":
        actions.append("Enable agent_native or skill_api before research workflows, or allow manual input prompts.")
    if heartbeat != "none":
        actions.append("Read references/automation-playbook.md and let the current agent configure supported automations.")
    if workflow_scope == "full-institutional" and heartbeat in {"none", "manual"}:
        actions.append("Full institutional workflow scope can run manually, but daily prewarm or market heartbeat automation is recommended.")
    if workflow_scope in {"portfolio-review", "full-institutional"} and portfolio_source == "none":
        actions.append("Select manual-ledger, imported-file, or read-only-api portfolio source before portfolio review workflows.")
    if not actions:
        actions.append("Runtime profile is ready for the selected preset and capability configuration.")
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
    resolved = _resolve_auto_fields(args)
    api = _api_capabilities()
    prewarm = _latest_prewarm(workspace)
    provider_capabilities = _load_json(_skillpack_root() / "data" / "provider-capabilities.json", {})
    automation_jobs = _load_json(_skillpack_root() / "data" / "automation-jobs.json", {})
    return {
        "schema_version": 2,
        "package": "aegis-alpha",
        "created_at": _now(),
        "updated_at": _now(),
        "agent": agent,
        "preset": resolved["preset"],
        "mode": resolved["preset"],
        "legacy_mode": args.mode,
        "preset_policy": {
            "type": "default_orchestration",
            "feature_gate": False,
            "all_public_skills_available": True,
            "out_of_preset_requests": "allowed_with_provider_resolution_and_fail_closed_safety",
        },
        "workflow_scope": resolved["workflow_scope"],
        "portfolio_source": resolved["portfolio_source"],
        "portfolio_mode": resolved["portfolio_source"],
        "cache_policy": resolved["cache_policy"],
        "manual_input_policy": resolved["manual_input_policy"],
        "capability_level": _capability_level(
            resolved["workflow_scope"],
            resolved["provider_priority"],
            resolved["cache_policy"],
            resolved["heartbeat"],
            api,
            prewarm,
        ),
        "workspace": str(workspace),
        "data_source_mode": resolved["data_source_mode"],
        "data_source_modes": resolved["provider_priority"],
        "data_provider_priority": resolved["provider_priority"],
        "automation": {
            "heartbeat_mode": resolved["heartbeat"],
            "requested_heartbeat_mode": args.heartbeat,
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
        "next_actions": _next_actions(
            resolved["workflow_scope"],
            resolved["provider_priority"],
            resolved["cache_policy"],
            resolved["manual_input_policy"],
            resolved["heartbeat"],
            resolved["portfolio_source"],
            api,
            prewarm,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Aegis Alpha runtime profile.")
    parser.add_argument("--agent", choices=AGENTS, default="auto")
    parser.add_argument("--preset", choices=("auto",) + tuple(PRESETS.keys()), default="auto")
    parser.add_argument("--mode", choices=LEGACY_MODES, default=None, help="Deprecated compatibility alias; use --preset plus explicit capability axes.")
    parser.add_argument("--workflow-scope", choices=WORKFLOW_SCOPES, default="auto")
    parser.add_argument("--portfolio-source", choices=PORTFOLIO_SOURCES, default="auto")
    parser.add_argument("--portfolio-mode", choices=PORTFOLIO_MODES, default="auto", help="Deprecated alias for --portfolio-source.")
    parser.add_argument("--data-source", default="auto", help="Deprecated alias for one acquisition provider; use --data-providers plus --cache-policy and --manual-input.")
    parser.add_argument("--data-providers", default="auto", help="Comma-separated acquisition provider priority, e.g. agent_native,skill_api. Deprecated provider aliases are accepted only for migration.")
    parser.add_argument("--cache-policy", choices=CACHE_POLICIES, default="auto")
    parser.add_argument("--manual-input", choices=MANUAL_INPUT_POLICIES, default="auto")
    parser.add_argument("--heartbeat", choices=HEARTBEAT_MODES, default="auto")
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
