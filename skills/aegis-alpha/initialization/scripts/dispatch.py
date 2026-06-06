from __future__ import annotations

import argparse
import json
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRESETS = {
    "quick-research": {
        "label": "one-off research and evidence collection",
        "defaults": {
            "data_providers": "agent_native,skill_api",
            "cache_policy": "read-if-fresh",
            "manual_input": "ask-when-missing",
            "portfolio_source": "none",
            "heartbeat": "none",
        },
    },
    "daily-desk": {
        "label": "morning/nightly market desk workflow",
        "defaults": {
            "data_providers": "skill_api,agent_native",
            "cache_policy": "refresh-if-stale",
            "manual_input": "ask-when-missing",
            "portfolio_source": "none",
            "heartbeat": "daily-prewarm",
        },
    },
    "portfolio-desk": {
        "label": "holdings, trade ledger, risk review, and advice tracking",
        "defaults": {
            "data_providers": "skill_api,agent_native",
            "cache_policy": "read-if-fresh",
            "manual_input": "ask-when-missing",
            "portfolio_source": "manual-ledger",
            "heartbeat": "manual",
        },
    },
    "report-review": {
        "label": "evidence capture, report review, and outcome alignment",
        "defaults": {
            "data_providers": "agent_native,skill_api",
            "cache_policy": "cache-first",
            "manual_input": "ask-when-missing",
            "portfolio_source": "manual-ledger",
            "heartbeat": "none",
        },
    },
    "full-institutional": {
        "label": "full research, market, portfolio, validation, and reporting loop",
        "defaults": {
            "data_providers": "skill_api,agent_native",
            "cache_policy": "prewarm-required",
            "manual_input": "ask-when-missing",
            "portfolio_source": "manual-ledger",
            "heartbeat": "market-heartbeat",
        },
    },
}

REQUIRED_AXES = {
    "data_providers": "Acquisition priority; agent_native and skill_api can be combined.",
    "cache_policy": "Evidence cache/prewarm policy.",
    "manual_input": "Whether to ask for user-provided evidence when needed.",
    "portfolio_source": "Where holdings and trade records come from.",
    "heartbeat": "Requested recurring workflow mode; does not configure wakeups by itself.",
}

MARKET_DATA_REQUIRED_ENV = {
    "a_share": ["TUSHARE_TOKEN"],
    "overseas_primary": ["LONGPORT_APP_KEY", "LONGPORT_APP_SECRET", "LONGPORT_ACCESS_TOKEN"],
    "overseas_fallback": ["FINNHUB_API_KEY"],
}

OPTIONAL_API_GROUPS = ["market_intel", "research_search", "document_parse", "external_push"]
TERMINAL_SKIP_DECISIONS = {"skip", "disabled", "none"}
TERMINAL_PREWARM_DECISIONS = {"skip"}
TERMINAL_HEARTBEAT_DECISIONS = {"manual", "none", "skip"}
TERMINAL_PORTFOLIO_DECISIONS = {"none", "manual-ledger", "imported-file", "read-only-api", "skip"}


def _workspace(raw: str | None = None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "initialization",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "initialization state and plan are evaluated at command runtime",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "configuration_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str]) -> dict[str, Any]:
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


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _load_workspace_env(workspace: Path) -> None:
    env_path = workspace / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _choices_path(workspace: Path) -> Path:
    return workspace / "config" / "initialization-choices.json"


def _load_choices(workspace: Path) -> dict[str, Any]:
    data = _load_json(_choices_path(workspace), {})
    if isinstance(data, dict):
        data.setdefault("schema_version", 1)
        data.setdefault("choices", {})
        return data
    return {"schema_version": 1, "choices": {}}


def _save_choices(workspace: Path, choices: dict[str, Any]) -> Path:
    path = _choices_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    choices["schema_version"] = 1
    choices["updated_at"] = _now()
    path.write_text(json.dumps(choices, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _choice_decision(choices: dict[str, Any], key: str) -> str:
    raw = choices.get("choices", {}).get(key) if isinstance(choices.get("choices"), dict) else None
    if isinstance(raw, dict):
        return str(raw.get("decision") or "")
    return ""


def _api_group_configured(api: dict[str, Any], group: str) -> bool:
    status = api.get(group) if isinstance(api, dict) else None
    return bool(isinstance(status, dict) and status.get("configured"))


def _completion_state(profile: dict[str, Any] | None, choices: dict[str, Any] | None = None) -> dict[str, Any]:
    choices = choices or {"choices": {}}
    if not isinstance(profile, dict):
        return {
            "runtime_profile_exists": False,
            "market_data_ready": False,
            "prewarm_ready": False,
            "heartbeat_configured": False,
            "fully_initialized": False,
            "pending_operational_choices": ["runtime_profile"],
        }
    api = profile.get("providers", {}).get("api", {}) if isinstance(profile.get("providers"), dict) else {}
    market_data = api.get("market_data", {}) if isinstance(api, dict) else {}
    prewarm = profile.get("providers", {}).get("prewarm", {}) if isinstance(profile.get("providers"), dict) else {}
    automation = profile.get("automation", {}) if isinstance(profile.get("automation"), dict) else {}
    cache_policy = str(profile.get("cache_policy") or "none")
    heartbeat = str(automation.get("heartbeat_mode") or "none")
    portfolio_source = str(profile.get("portfolio_source") or "none")
    prewarm_required = cache_policy == "prewarm-required"
    heartbeat_requested = heartbeat not in {"none", "manual"}
    market_data_ready = bool(market_data.get("configured"))
    prewarm_decision = _choice_decision(choices, "prewarm")
    heartbeat_decision = _choice_decision(choices, "heartbeat")
    portfolio_decision = _choice_decision(choices, "portfolio")
    prewarm_ready = (not prewarm_required) or bool(prewarm.get("available")) or prewarm_decision in TERMINAL_PREWARM_DECISIONS
    heartbeat_configured = (not heartbeat_requested) or bool(automation.get("configured_by_agent")) or heartbeat_decision in TERMINAL_HEARTBEAT_DECISIONS
    portfolio_ready = portfolio_source == "none" or portfolio_decision in TERMINAL_PORTFOLIO_DECISIONS
    optional_api_status = {
        group: {
            "configured": _api_group_configured(api, group),
            "decision": _choice_decision(choices, group),
            "complete": _api_group_configured(api, group) or _choice_decision(choices, group) in TERMINAL_SKIP_DECISIONS,
        }
        for group in OPTIONAL_API_GROUPS
    }
    pending: list[str] = []
    if not market_data_ready:
        pending.append("market_data")
    if not prewarm_ready:
        pending.append("prewarm")
    if not heartbeat_configured:
        pending.append("heartbeat")
    if not portfolio_ready:
        pending.append("portfolio")
    pending.extend([f"optional_api:{group}" for group, status in optional_api_status.items() if not status["complete"]])
    fully_initialized = market_data_ready and prewarm_ready and heartbeat_configured and portfolio_ready and all(
        status["complete"] for status in optional_api_status.values()
    )
    return {
        "runtime_profile_exists": True,
        "market_data_ready": market_data_ready,
        "prewarm_required": prewarm_required,
        "prewarm_ready": prewarm_ready,
        "prewarm_decision": prewarm_decision,
        "heartbeat_requested": heartbeat_requested,
        "heartbeat_configured": heartbeat_configured,
        "heartbeat_decision": heartbeat_decision,
        "portfolio_ready": portfolio_ready,
        "portfolio_decision": portfolio_decision,
        "optional_api_status": optional_api_status,
        "fully_initialized": fully_initialized,
        "pending_operational_choices": pending,
    }


def _wizard_steps(profile: dict[str, Any] | None, choices: dict[str, Any], guide: dict[str, Any]) -> list[dict[str, Any]]:
    state = _completion_state(profile, choices)
    api = profile.get("providers", {}).get("api", {}) if isinstance(profile, dict) and isinstance(profile.get("providers"), dict) else {}
    api_groups = guide.get("api_groups", {}) if isinstance(guide.get("api_groups"), dict) else {}

    def api_urls(group: str) -> dict[str, str]:
        meta = api_groups.get(group) if isinstance(api_groups.get(group), dict) else {}
        urls = meta.get("setup_urls") if isinstance(meta.get("setup_urls"), dict) else {}
        return {str(k): str(v) for k, v in urls.items()}

    steps = [
        {
            "id": "capabilities",
            "label": "Explain Aegis Alpha capabilities and safety boundaries",
            "status": "done",
            "required": True,
        },
        {
            "id": "runtime_profile",
            "label": "Choose preset and required axes, then write runtime profile",
            "status": "done" if state["runtime_profile_exists"] else "pending",
            "required": True,
        },
        {
            "id": "market_data",
            "label": "Configure required market_data baseline",
            "status": "done" if state["market_data_ready"] else "pending",
            "required": True,
            "setup_urls": api_urls("market_data"),
        },
        {
            "id": "optional_api_groups",
            "label": "Confirm optional API groups: configure now, skip, or defer",
            "status": "done" if all(item["complete"] for item in state.get("optional_api_status", {}).values()) else "pending",
            "required": False,
            "groups": {
                group: {
                    **state.get("optional_api_status", {}).get(group, {}),
                    "setup_urls": api_urls(group),
                }
                for group in OPTIONAL_API_GROUPS
            },
        },
        {
            "id": "prewarm",
            "label": "Run, skip, or defer prewarm/cache artifact setup",
            "status": "done" if state["prewarm_ready"] else "pending",
            "required": state.get("prewarm_required", False),
            "decision": state.get("prewarm_decision", ""),
        },
        {
            "id": "heartbeat",
            "label": "Configure real heartbeat automation or choose manual/no heartbeat",
            "status": "done" if state["heartbeat_configured"] else "pending",
            "required": state.get("heartbeat_requested", False),
            "decision": state.get("heartbeat_decision", ""),
        },
        {
            "id": "portfolio",
            "label": "Confirm portfolio source and ledger/import/read-only setup",
            "status": "done" if state.get("portfolio_ready") else "pending",
            "required": True,
            "decision": state.get("portfolio_decision", ""),
        },
        {
            "id": "final_review",
            "label": "Review all configured or explicitly skipped choices",
            "status": "done" if state["fully_initialized"] else "pending",
            "required": True,
        },
    ]
    return steps


def _init_guide(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace(payload.get("workspace"))
    _load_workspace_env(workspace)
    profile_path = workspace / "config" / "runtime-profile.json"
    profile = _load_json(profile_path, None)
    choices = _load_choices(workspace)
    guide = _load_json(_package_root() / "data" / "capability-guide.json", {})
    state = _completion_state(profile if isinstance(profile, dict) else None, choices)
    steps = _wizard_steps(profile if isinstance(profile, dict) else None, choices, guide if isinstance(guide, dict) else {})
    current = next((step for step in steps if step.get("status") != "done"), None)
    output = _base_output(command, payload)
    output["source"] = [str(profile_path), str(_choices_path(workspace)), str(_package_root() / "data" / "capability-guide.json")]
    output["sources"] = list(output["source"])
    if not state["fully_initialized"]:
        output["warnings"] = [
            "initialization_incomplete",
            *[f"pending:{item}" for item in state["pending_operational_choices"]],
        ]
    output["result"] = {
        "initialized": state["fully_initialized"],
        "initialization_state": state,
        "steps": steps,
        "current_step": current,
        "choices_path": str(_choices_path(workspace)),
        "profile_path": str(profile_path),
        "instructions": [
            "Guide the user one step at a time.",
            "For each API group, explain what it unlocks, whether it is required, and where to configure credentials before asking for a key.",
            "Record every configure/skip/defer decision with record-choice.",
            "Do not claim initialization is complete until current_step is null and initialized is true.",
        ],
    }
    return output


def _record_choice(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace(payload.get("workspace"))
    choice = str(payload.get("choice") or "").strip()
    decision = str(payload.get("decision") or "").strip()
    if not choice or not decision:
        return _fail(command, payload, ["choice_and_decision_required"])
    valid_choices = {"prewarm", "heartbeat", "portfolio", *OPTIONAL_API_GROUPS}
    if choice not in valid_choices:
        return _fail(command, payload, [f"invalid_choice:{choice}"])
    choices = _load_choices(workspace)
    choices.setdefault("choices", {})
    choices["choices"][choice] = {
        "decision": decision,
        "decided_at": _now(),
        "note": str(payload.get("note") or ""),
    }
    if payload.get("metadata") and isinstance(payload.get("metadata"), dict):
        choices["choices"][choice]["metadata"] = payload["metadata"]
    path = _save_choices(workspace, choices)
    guide = _init_guide("init-guide", {"workspace": str(workspace)})
    output = _base_output(command, payload)
    output["artifacts"] = [str(path)]
    output["source"] = [str(path)]
    output["sources"] = [str(path)]
    output["warnings"] = guide.get("warnings", [])
    output["result"] = {
        "recorded": True,
        "choices_path": str(path),
        "choice": choices["choices"][choice],
        "guide": guide.get("result", {}),
    }
    return output


def _init_status(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace(payload.get("workspace"))
    _load_workspace_env(workspace)
    profile_path = workspace / "config" / "runtime-profile.json"
    output = _base_output(command, payload)
    profile = _load_json(profile_path, None)
    state = _completion_state(profile)
    output["source"] = [str(profile_path)]
    output["sources"] = [str(profile_path)]
    output["result"] = {
        "initialized": state["fully_initialized"],
        "runtime_profile_exists": state["runtime_profile_exists"],
        "initialization_state": state,
        "profile_path": str(profile_path),
        "workspace": str(workspace),
        "profile": profile if state["runtime_profile_exists"] else None,
    }
    if not state["runtime_profile_exists"]:
        output["warnings"] = ["runtime_profile_missing"]
    elif not state["fully_initialized"]:
        output["warnings"] = [
            "runtime_profile_exists_but_initialization_incomplete",
            *[f"pending:{item}" for item in state["pending_operational_choices"]],
        ]
    return output


def _api_status() -> dict[str, Any]:
    groups = {
        "research_search": ["TAVILY_API_KEYS", "QVERIS_API_KEY"],
        "document_parse": ["MINERU_API_KEY"],
        "market_data": ["TUSHARE_TOKEN", "LONGPORT_APP_KEY", "LONGPORT_APP_SECRET", "LONGPORT_ACCESS_TOKEN", "FINNHUB_API_KEY"],
        "market_intel": ["JIN10_API_KEY", "TAVILY_API_KEYS", "QVERIS_API_KEY"],
        "external_push": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID", "FEISHU_CHAT_ID"],
    }
    status = {
        group: {
            "configured": any(os.environ.get(name) for name in names),
            "env": names,
            "present_env": [name for name in names if os.environ.get(name)],
            "missing_env": [name for name in names if not os.environ.get(name)],
        }
        for group, names in groups.items()
    }
    status["market_data"].update(_market_data_status())
    return status


def _all_present(names: list[str]) -> bool:
    return all(os.environ.get(name) for name in names)


def _longbridge_cli_configured() -> bool:
    if not shutil.which("longbridge"):
        return False
    try:
        result = subprocess.run(
            ["longbridge", "auth", "status"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return result.returncode == 0 and "valid" in (result.stdout + result.stderr).lower()


def _market_data_status() -> dict[str, Any]:
    a_share_configured = _all_present(MARKET_DATA_REQUIRED_ENV["a_share"])
    overseas_primary_configured = _all_present(MARKET_DATA_REQUIRED_ENV["overseas_primary"])
    overseas_fallback_configured = _all_present(MARKET_DATA_REQUIRED_ENV["overseas_fallback"])
    overseas_cli_configured = _longbridge_cli_configured()
    missing = [
        name for name in MARKET_DATA_REQUIRED_ENV["a_share"] if not os.environ.get(name)
    ]
    if not (overseas_primary_configured or overseas_cli_configured or overseas_fallback_configured):
        missing.extend(MARKET_DATA_REQUIRED_ENV["overseas_primary"])
    return {
        "configured": a_share_configured and (overseas_primary_configured or overseas_cli_configured or overseas_fallback_configured),
        "required": True,
        "required_env": MARKET_DATA_REQUIRED_ENV,
        "missing_required_env": missing,
        "preferred_overseas_configured": overseas_primary_configured,
        "longbridge_cli_configured": overseas_cli_configured,
        "fallback_configured": overseas_fallback_configured,
        "routing": {
            "a_share": "$tushare via TUSHARE_TOKEN",
            "overseas_primary": "$longbridge / LongPort via LONGPORT_APP_KEY, LONGPORT_APP_SECRET, LONGPORT_ACCESS_TOKEN",
            "overseas_cli": "$longbridge CLI authenticated with `longbridge auth login`",
            "overseas_fallback": "FINNHUB_API_KEY only when LongBridge/LongPort is unavailable",
        },
    }


def _init_plan(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    preset = str(payload.get("preset") or "auto")
    if preset != "auto" and preset not in PRESETS:
        return _fail(command, payload, [f"invalid_preset:{preset}"])
    _load_workspace_env(_workspace(payload.get("workspace")))
    guide = _load_json(_package_root() / "data" / "capability-guide.json", {})
    selected = None if preset == "auto" else PRESETS[preset]
    output = _base_output(command, payload)
    output["source"] = [str(_package_root() / "data" / "capability-guide.json")]
    output["sources"] = list(output["source"])
    output["result"] = {
        "presets": PRESETS,
        "selected_preset": preset,
        "selected_defaults": selected["defaults"] if selected else None,
        "required_axes": REQUIRED_AXES,
        "api_groups": guide.get("api_groups", {}) if isinstance(guide, dict) else {},
        "capabilities": guide.get("capabilities", {}) if isinstance(guide, dict) else {},
        "preset_api_guidance": guide.get("preset_api_guidance", {}) if isinstance(guide, dict) else {},
        "current_api_status": _api_status(),
        "global_required_api_groups": ["market_data"],
        "global_required_market_data": {
            "a_share": "$tushare via TUSHARE_TOKEN",
            "overseas_primary": "$longbridge / LongPort via LONGPORT_APP_KEY, LONGPORT_APP_SECRET, LONGPORT_ACCESS_TOKEN",
            "overseas_fallback": "FINNHUB_API_KEY only when LongBridge/LongPort is unavailable",
        },
        "operational_options": {
            "prewarm": "Prewarm/cache artifacts must be run separately and are not created by choosing a preset.",
            "heartbeat": "Heartbeat requires native automation support or an OS scheduler fallback; preset choice does not configure wakeups.",
            "portfolio": "Portfolio review needs manual-ledger, imported-file, or read-only-api evidence before relying on holdings.",
            "external_push": "External push is disabled unless explicitly enabled and credentials are configured.",
        },
        "must_ask_user": [
            "preset",
            "data_providers",
            "cache_policy",
            "manual_input",
            "portfolio_source",
            "heartbeat",
            "market_data baseline: TUSHARE_TOKEN plus LongBridge/LongPort credentials, or Finnhub fallback for overseas data",
            "whether to configure recommended API groups",
            "whether to run prewarm jobs",
            "whether to configure real automation",
            "whether to create/import portfolio ledger",
            "whether to enable external push",
        ],
    }
    return output


def _bootstrap_profile(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("user_confirmed") is not True:
        return _fail(command, payload, ["user_confirmation_missing"])
    workspace = _workspace(payload.get("workspace"))
    _load_workspace_env(workspace)
    market_data_status = _market_data_status()
    if not market_data_status["configured"]:
        missing = market_data_status["missing_required_env"]
        return _fail(command, payload, [f"market_data_required_missing:{name}" for name in missing])
    required = ["preset", "data_providers", "cache_policy", "manual_input", "portfolio_source", "heartbeat"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return _fail(command, payload, [f"missing_required_axis:{key}" for key in missing])

    script = _package_root() / "scripts" / "bootstrap_runtime.py"
    cmd = [
        "python3",
        str(script),
        "--agent",
        str(payload.get("agent") or "auto"),
        "--preset",
        str(payload["preset"]),
        "--data-providers",
        str(payload["data_providers"]),
        "--cache-policy",
        str(payload["cache_policy"]),
        "--manual-input",
        str(payload["manual_input"]),
        "--portfolio-source",
        str(payload["portfolio_source"]),
        "--heartbeat",
        str(payload["heartbeat"]),
    ]
    if payload.get("external_push"):
        cmd.extend(["--external-push", str(payload["external_push"])])
    if payload.get("workspace"):
        cmd.extend(["--workspace", str(payload["workspace"])])

    env = dict(os.environ)
    env["AEGIS_ALPHA_WORKSPACE"] = str(workspace)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    if result.returncode != 0:
        return _fail(command, payload, [result.stderr.strip() or result.stdout.strip() or "bootstrap_failed"])
    try:
        bootstrap_payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return _fail(command, payload, ["bootstrap_output_invalid_json"])
    output = _base_output(command, payload)
    profile_path = bootstrap_payload.get("profile_path")
    if profile_path:
        output["artifacts"] = [str(profile_path)]
    output["source"] = [str(script)]
    output["sources"] = [str(script)]
    output["result"] = bootstrap_payload
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = _load_json(package_root / "data" / "command-manifest.json", {})
    available = {c["name"] for c in manifest.get("commands", []) if isinstance(c, dict)}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
    except ValueError as exc:
        print(json.dumps(_fail(args.command, {}, [str(exc)]), ensure_ascii=False))
        return 0

    if args.command == "init-status":
        output = _init_status(args.command, payload)
    elif args.command == "init-guide":
        output = _init_guide(args.command, payload)
    elif args.command == "init-plan":
        output = _init_plan(args.command, payload)
    elif args.command == "record-choice":
        output = _record_choice(args.command, payload)
    elif args.command == "bootstrap-profile":
        output = _bootstrap_profile(args.command, payload)
    else:
        output = _fail(args.command, payload, [f"unknown_command:{args.command}"])
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
