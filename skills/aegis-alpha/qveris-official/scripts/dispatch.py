from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "qveris-official",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "QVeris wrapper output is evaluated at command runtime",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "data_only",
        "source": ["https://qveris.ai/api/v1"],
        "sources": ["https://qveris.ai/api/v1"],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], raw: str = "") -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "QVeris evidence is unavailable; do not infer structured data from this connector.",
        "raw": raw,
    }
    return output


def _load_manifest(base: Path) -> dict[str, Any]:
    return json.loads((base / "data" / "command-manifest.json").read_text(encoding="utf-8"))


def _run_qveris_tool(args: list[str]) -> tuple[int, str]:
    script = Path(__file__).resolve().parent / "qveris_tool.mjs"
    proc = subprocess.run(
        ["node", str(script), *args, "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        env=dict(os.environ),
    )
    return proc.returncode, (proc.stdout or "").strip()


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return None


def _search(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        return _fail(command, payload, ["query_required"])
    limit = int(payload.get("limit") or 10)
    timeout = int(payload.get("timeout_seconds") or 30)
    code, raw = _run_qveris_tool(["search", query, "--limit", str(limit), "--timeout", str(timeout)])
    parsed = _parse_json(raw)
    if code != 0 or parsed is None:
        return _fail(command, payload, ["qveris_search_failed"], raw)
    output = _base_output(command, payload)
    output["result"] = parsed
    return output


def _get_by_ids(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    ids = payload.get("tool_ids")
    if isinstance(ids, str):
        ids = [ids]
    if not isinstance(ids, list) or not [item for item in ids if item]:
        return _fail(command, payload, ["tool_ids_required"])
    args = ["get-by-ids", *[str(item) for item in ids if item]]
    if payload.get("search_id"):
        args.extend(["--search-id", str(payload["search_id"])])
    if payload.get("timeout_seconds"):
        args.extend(["--timeout", str(int(payload["timeout_seconds"]))])
    code, raw = _run_qveris_tool(args)
    parsed = _parse_json(raw)
    if code != 0 or parsed is None:
        return _fail(command, payload, ["qveris_get_by_ids_failed"], raw)
    output = _base_output(command, payload)
    output["result"] = parsed
    return output


def _execute(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool_id = str(payload.get("tool_id") or "").strip()
    search_id = str(payload.get("search_id") or "").strip()
    params = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    if not tool_id:
        return _fail(command, payload, ["tool_id_required"])
    if not search_id:
        return _fail(command, payload, ["search_id_required"])
    args = [
        "execute",
        tool_id,
        "--search-id",
        search_id,
        "--params",
        json.dumps(params, ensure_ascii=False),
    ]
    if payload.get("max_response_size"):
        args.extend(["--max-size", str(int(payload["max_response_size"]))])
    if payload.get("timeout_seconds"):
        args.extend(["--timeout", str(int(payload["timeout_seconds"]))])
    code, raw = _run_qveris_tool(args)
    parsed = _parse_json(raw)
    if code != 0 or parsed is None:
        return _fail(command, payload, ["qveris_execute_failed"], raw)
    output = _base_output(command, payload)
    output["result"] = parsed
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = _load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", []) if isinstance(c, dict)}
    if args.command not in available:
        print(json.dumps(_fail(args.command, {}, [f"unknown_command:{args.command}"]), ensure_ascii=False))
        return 0

    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
    except ValueError as exc:
        print(json.dumps(_fail(args.command, {}, [str(exc)]), ensure_ascii=False))
        return 0

    if args.command == "search":
        output = _search(args.command, payload)
    elif args.command == "get-by-ids":
        output = _get_by_ids(args.command, payload)
    elif args.command == "execute":
        output = _execute(args.command, payload)
    else:
        output = _fail(args.command, payload, [f"unimplemented_command:{args.command}"])
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
