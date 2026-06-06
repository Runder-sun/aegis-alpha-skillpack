from __future__ import annotations

import argparse
import json
import os
import subprocess
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


def _init_status(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace(payload.get("workspace"))
    profile_path = workspace / "config" / "runtime-profile.json"
    output = _base_output(command, payload)
    profile = _load_json(profile_path, None)
    initialized = isinstance(profile, dict)
    output["source"] = [str(profile_path)]
    output["sources"] = [str(profile_path)]
    output["result"] = {
        "initialized": initialized,
        "profile_path": str(profile_path),
        "workspace": str(workspace),
        "profile": profile if initialized else None,
    }
    if not initialized:
        output["warnings"] = ["runtime_profile_missing"]
    return output


def _api_status() -> dict[str, Any]:
    groups = {
        "research_search": ["TAVILY_API_KEYS", "QVERIS_API_KEY"],
        "document_parse": ["MINERU_API_KEY"],
        "market_data": ["TUSHARE_TOKEN", "FINNHUB_API_KEY"],
        "market_intel": ["JIN10_API_KEY", "TAVILY_API_KEYS", "QVERIS_API_KEY"],
        "external_push": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_RECEIVE_ID", "FEISHU_CHAT_ID"],
    }
    return {
        group: {
            "configured": any(os.environ.get(name) for name in names),
            "env": names,
            "present_env": [name for name in names if os.environ.get(name)],
            "missing_env": [name for name in names if not os.environ.get(name)],
        }
        for group, names in groups.items()
    }


def _init_plan(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    preset = str(payload.get("preset") or "auto")
    if preset != "auto" and preset not in PRESETS:
        return _fail(command, payload, [f"invalid_preset:{preset}"])
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

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    elif args.command == "init-plan":
        output = _init_plan(args.command, payload)
    elif args.command == "bootstrap-profile":
        output = _bootstrap_profile(args.command, payload)
    else:
        output = _fail(args.command, payload, [f"unknown_command:{args.command}"])
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
