#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CAPABILITIES = (
    "research_search",
    "web_extract",
    "document_parse",
    "market_news",
    "structured_market_data",
    "external_push",
)


def _skillpack_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _profile(workspace: Path, explicit: str | None) -> dict[str, Any]:
    if explicit:
        return _load_json(Path(explicit).expanduser(), {})
    return _load_json(workspace / "config" / "runtime-profile.json", {})


def _provider_available(provider: str, profile: dict[str, Any]) -> tuple[bool, str]:
    data_source_mode = profile.get("data_source_mode") or "manual_payload"
    api = (((profile.get("providers") or {}).get("api")) or {})
    prewarm = (((profile.get("providers") or {}).get("prewarm")) or {})
    if provider == "manual_payload":
        return True, "manual payload is always allowed"
    if provider == "agent_native":
        if data_source_mode in {"agent_native", "auto"} or profile.get("mode") == "agent-native":
            return True, "selected runtime mode allows agent-native acquisition"
        return False, "runtime profile did not enable agent-native acquisition"
    if provider == "skill_api":
        configured = any(isinstance(group, dict) and group.get("configured") for group in api.values())
        return (configured, "at least one API group is configured" if configured else "no skill API key group is configured")
    if provider == "cache_or_prewarm":
        available = bool(prewarm.get("available"))
        return (available, "prewarm artifact is available" if available else "prewarm artifact is unavailable")
    return False, "unknown provider"


def resolve(capability: str, profile: dict[str, Any], capabilities: dict[str, Any]) -> dict[str, Any]:
    agent = profile.get("agent") or "unknown"
    configured = capabilities.get(agent) if isinstance(capabilities, dict) else None
    if not isinstance(configured, dict):
        configured = capabilities.get("unknown", {}) if isinstance(capabilities, dict) else {}
    provider_order = configured.get(capability) if isinstance(configured, dict) else None
    if not isinstance(provider_order, list):
        provider_order = ["manual_payload"]
    providers = []
    for provider in provider_order:
        ok, reason = _provider_available(str(provider), profile)
        providers.append({"provider": provider, "available": ok, "reason": reason})
    if not any(item["available"] for item in providers):
        providers.append({"provider": "manual_payload", "available": True, "reason": "fallback to manual payload"})
    return {
        "agent": agent,
        "capability": capability,
        "selected": next(item["provider"] for item in providers if item["available"]),
        "providers": providers,
        "decision_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Aegis Alpha data provider order for a runtime profile.")
    parser.add_argument("--capability", choices=CAPABILITIES, required=True)
    parser.add_argument("--workspace")
    parser.add_argument("--profile")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = _workspace(args.workspace)
    profile = _profile(workspace, args.profile)
    capabilities = _load_json(_skillpack_root() / "data" / "provider-capabilities.json", {})
    print(json.dumps(resolve(args.capability, profile, capabilities), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
