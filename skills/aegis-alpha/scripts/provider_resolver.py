#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
CACHE_PROVIDERS = {"workspace_cache", "cache_or_prewarm"}
LEGACY_MANUAL_PROVIDER = "manual_payload"
API_GROUPS_BY_CAPABILITY = {
    "research_search": ("research_search",),
    "web_extract": ("research_search", "document_parse"),
    "document_parse": ("document_parse",),
    "market_news": ("market_intel", "research_search"),
    "structured_market_data": ("market_data",),
    "external_push": ("external_push",),
}


def _skillpack_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    env = os.environ.get("AEGIS_ALPHA_WORKSPACE")
    if env:
        return Path(env).expanduser()
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


def _provider_available(provider: str, profile: dict[str, Any], capability: str) -> tuple[bool, str]:
    data_source_mode = profile.get("data_source_mode") or "none"
    provider_priority = profile.get("data_provider_priority") or profile.get("data_source_modes") or []
    if not isinstance(provider_priority, list):
        provider_priority = []
    api = (((profile.get("providers") or {}).get("api")) or {})
    prewarm = (((profile.get("providers") or {}).get("prewarm")) or {})
    if provider == LEGACY_MANUAL_PROVIDER:
        return False, "user-supplied evidence is not a provider; use manual_input_policy"
    if provider == "agent_native":
        if "agent_native" in provider_priority or data_source_mode in {"agent_native", "auto"} or profile.get("legacy_mode") == "agent-native":
            return True, "runtime profile allows agent-native acquisition"
        return False, "runtime profile did not enable agent-native acquisition"
    if provider == "skill_api":
        required_groups = API_GROUPS_BY_CAPABILITY.get(capability, ())
        configured_groups = [
            name
            for name in required_groups
            if isinstance(api.get(name), dict) and api[name].get("configured")
        ]
        configured = bool(configured_groups)
        expected = ", ".join(required_groups) if required_groups else "capability-specific API group"
        return (
            configured,
            f"configured API group(s): {', '.join(configured_groups)}"
            if configured
            else f"no configured API group for {capability}; expected one of: {expected}",
        )
    if provider in CACHE_PROVIDERS:
        cache_policy = profile.get("cache_policy") or ("cache-first" if provider == "cache_or_prewarm" else "none")
        if cache_policy == "none":
            return False, "runtime profile did not enable workspace cache"
        available = bool(prewarm.get("available"))
        return (available, "workspace cache/prewarm artifact is available" if available else "workspace cache/prewarm artifact is unavailable")
    return False, "unknown provider"


def _ordered_providers(capability: str, profile: dict[str, Any], capability_order: list[Any]) -> list[str]:
    base_order = ["workspace_cache" if str(item) == "cache_or_prewarm" else str(item) for item in capability_order]
    if capability == "external_push":
        return base_order
    profile_priority = profile.get("data_provider_priority") or profile.get("data_source_modes")
    acquisition_base = [item for item in base_order if item not in CACHE_PROVIDERS and item != LEGACY_MANUAL_PROVIDER]
    if isinstance(profile_priority, list):
        acquisition_order = [str(item) for item in profile_priority if str(item) in acquisition_base]
    else:
        acquisition_order = acquisition_base
    cache_policy = str(profile.get("cache_policy") or "none")
    cache_order = ["workspace_cache"] if "workspace_cache" in base_order and cache_policy != "none" else []
    if cache_policy in {"cache-first", "refresh-if-stale", "prewarm-required"}:
        return _dedupe(cache_order + acquisition_order)
    if cache_policy == "read-if-fresh":
        ordered: list[str] = []
        for item in base_order:
            if item == "workspace_cache" and cache_order:
                ordered.extend(cache_order)
            elif item in acquisition_order:
                ordered.append(item)
        return _dedupe(ordered)
    return _dedupe(acquisition_order)


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def resolve(capability: str, profile: dict[str, Any], capabilities: dict[str, Any]) -> dict[str, Any]:
    agent = profile.get("agent") or "unknown"
    configured = capabilities.get(agent) if isinstance(capabilities, dict) else None
    if not isinstance(configured, dict):
        configured = capabilities.get("unknown", {}) if isinstance(capabilities, dict) else {}
    provider_order = configured.get(capability) if isinstance(configured, dict) else None
    if not isinstance(provider_order, list):
        provider_order = []
    provider_order = _ordered_providers(capability, profile, provider_order)
    providers = []
    for provider in provider_order:
        ok, reason = _provider_available(str(provider), profile, capability)
        providers.append({"provider": provider, "available": ok, "reason": reason})
    selected = next((item["provider"] for item in providers if item["available"]), None)
    manual_input_policy = str(profile.get("manual_input_policy") or "ask-when-missing")
    requires_user_input = selected is None and manual_input_policy == "ask-when-missing" and capability != "external_push"
    return {
        "agent": agent,
        "capability": capability,
        "selected": selected,
        "available": selected is not None,
        "providers": providers,
        "manual_input_policy": manual_input_policy,
        "requires_user_input": requires_user_input,
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
