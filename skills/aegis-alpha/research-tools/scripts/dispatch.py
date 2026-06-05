from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "research-tools"


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE", "")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _skills_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "package": PACKAGE,
        "command": command,
        "payload": payload,
        "ok": True,
        "decision_allowed": False,
        "max_action_level": "research_only",
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["result"] = {
        "note": "Research tool call failed; do not infer missing evidence.",
    }
    return output


def _call_skill(package: str, command: str, payload: dict[str, Any]) -> dict[str, Any]:
    dispatch = _skills_root() / package / "scripts" / "dispatch.py"
    if not dispatch.exists():
        raise RuntimeError(f"dispatch_not_found:{package}")
    env = dict(os.environ)
    env.setdefault("AEGIS_ALPHA_WORKSPACE", str(_workspace_dir()))
    proc = subprocess.run(
        [sys.executable, str(dispatch), "--command", command, "--payload", json.dumps(payload, ensure_ascii=False)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(dispatch.parent),
        check=False,
    )
    text = (proc.stdout or "").strip()
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"format": "text", "content": text, "returncode": proc.returncode}
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip() or f"{package}:{command} failed")
    return {"empty_result": True}


def _analysis_history(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    limit = int(payload.get("limit", 10))
    memory = _workspace_dir() / "memory"
    patterns = [
        ("reports", memory / "reports", "*.md"),
        ("pipeline_runs", memory / "pipeline_runs", "*.json"),
        ("report_evidence", memory / "report_evidence", "**/metadata.json"),
    ]
    items: list[dict[str, Any]] = []
    for kind, directory, pattern in patterns:
        if not directory.exists():
            continue
        for path in directory.glob(pattern):
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append({
                "kind": kind,
                "path": str(path),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "size": stat.st_size,
            })
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    output = _base_output(command, payload)
    output["sources"] = [str(memory)]
    output["result"] = {
        "items": items[:limit],
        "count": min(len(items), limit),
        "total_found": len(items),
    }
    return output


def _set_preference(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    key = str(payload.get("key") or "").strip()
    if not key:
        return _fail(command, payload, ["key_required"])
    value = payload.get("value")
    path = _workspace_dir() / "memory" / "research" / "preferences.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prefs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        return _fail(command, payload, ["preferences_invalid_json"], [str(path)])
    if not isinstance(prefs, dict):
        return _fail(command, payload, ["preferences_invalid_shape"], [str(path)])
    prefs[key] = {
        "value": value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    output = _base_output(command, payload)
    output["artifacts"] = [str(path)]
    output["result"] = {"key": key, "value": value}
    return output


def _web_content_fetch(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = payload.get("url")
    if not url:
        return _fail(command, payload, ["url_required"])
    result = _call_skill("content-extract", "extract-url", payload)
    output = _base_output(command, payload)
    output["sources"] = [str(url)]
    output["result"] = result
    return output


def _search_and_extract(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("url"):
        return _web_content_fetch(command, payload)
    if not payload.get("query") and not payload.get("queries"):
        return _fail(command, payload, ["query_or_url_required"])
    search_payload = dict(payload)
    search_payload.setdefault("extract_refs", True)
    result = _call_skill("search-layer", "search", search_payload)
    output = _base_output(command, payload)
    output["result"] = result
    return output


def _help(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["result"] = {
        "public_commands": [
            "analysis-history",
            "help",
            "search-and-extract",
            "set-preference",
            "web-content-fetch",
        ],
        "retired_or_rehomed_commands": {
            "asset-allocation": "use macro-regime/theme-cycle/trade-planning",
            "asset-bull-bear": "use macro-regime",
            "global-asset-scan": "use macro-regime::global-macro-analysis",
            "grok-search": "no configured Grok API; use search-layer",
        },
    }
    return output


def _run(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command == "analysis-history":
        return _analysis_history(command, payload)
    if command == "help":
        return _help(command, payload)
    if command == "search-and-extract":
        return _search_and_extract(command, payload)
    if command == "set-preference":
        return _set_preference(command, payload)
    if command == "web-content-fetch":
        return _web_content_fetch(command, payload)
    raise ValueError(f"unknown_command: {command}")


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
        output = _run(args.command, payload)
    except (RuntimeError, ValueError) as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
