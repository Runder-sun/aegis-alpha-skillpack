from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PACKAGE = "search-layer"


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_manifest() -> dict[str, Any]:
    path = _package_root() / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_command(command: str) -> None:
    available = {item["name"] for item in _load_manifest().get("commands", [])}
    if command not in available:
        raise SystemExit(f"unknown command: {command}")


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return list()
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("OPENCLAW_WORKSPACE", str(_workspace_dir()))
    return env


def _run_command(cmd: list[str], *, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), env=_build_env())
    return proc.returncode, proc.stdout, proc.stderr


def _decode_output(returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"format": "markdown", "content": text}
    if returncode != 0:
        raise RuntimeError((stderr or "").strip() or f"command failed with exit code {returncode}")
    raise RuntimeError("empty_search_output")


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": PACKAGE,
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "search freshness is caller requested; provider freshness is preserved in result fields when available",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "research_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["errors"] = errors
    output["warnings"] = warnings or []
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Search evidence is unavailable; do not infer facts from missing retrieval results.",
        "missing_critical_inputs": errors,
    }
    return output


def _result_sources(result: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    raw = result.get("results")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                source = item.get("source")
                if source:
                    sources.append(str(source))
    if result.get("url"):
        sources.append(str(result.get("url")))
    if result.get("source_url"):
        sources.append(str(result.get("source_url")))
    return sorted(set(sources))


def run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_command(command)
    package_root = _package_root()
    scripts_dir = package_root / "scripts"

    if command == "search":
        script = scripts_dir / "search.py"
        cmd = [sys.executable, str(script)]
        queries = _normalize_list(payload.get("queries"))
        query = payload.get("query")
        if queries:
            cmd.extend(["--queries", *queries])
        elif query:
            cmd.append(str(query))
        else:
            raise ValueError("query_or_queries_required")
        if payload.get("mode"):
            cmd.extend(["--mode", str(payload["mode"])])
        if payload.get("intent"):
            cmd.extend(["--intent", str(payload["intent"])])
        if payload.get("freshness"):
            cmd.extend(["--freshness", str(payload["freshness"])])
        if payload.get("num") is not None:
            cmd.extend(["--num", str(payload["num"])])
        domain_boost = _normalize_list(payload.get("domain_boost"))
        if domain_boost:
            cmd.extend(["--domain-boost", ",".join(domain_boost)])
        sources = _normalize_list(payload.get("source"))
        if sources:
            cmd.extend(["--source", ",".join(sources)])
        if payload.get("extract_refs"):
            cmd.append("--extract-refs")
        extract_refs_urls = _normalize_list(payload.get("extract_refs_urls"))
        if extract_refs_urls:
            cmd.extend(["--extract-refs-urls", *extract_refs_urls])
        return _decode_output(*_run_command(cmd, cwd=scripts_dir))

    if command == "extract-refs":
        urls = _normalize_list(payload.get("urls"))
        if not urls:
            raise ValueError("urls_required")
        script = scripts_dir / "search.py"
        cmd = [sys.executable, str(script), "--extract-refs-urls", *urls]
        if payload.get("intent"):
            cmd.extend(["--intent", str(payload["intent"])])
        return _decode_output(*_run_command(cmd, cwd=scripts_dir))

    if command == "fetch-thread":
        url = payload.get("url")
        if not url:
            raise ValueError("url_required")
        script = scripts_dir / "fetch_thread.py"
        cmd = [sys.executable, str(script), str(url)]
        if payload.get("max_comments") is not None:
            cmd.extend(["--max-comments", str(payload["max_comments"])])
        if payload.get("extract_refs_only"):
            cmd.append("--extract-refs-only")
        if payload.get("format"):
            cmd.extend(["--format", str(payload["format"])])
        return _decode_output(*_run_command(cmd, cwd=scripts_dir))

    raise ValueError(f"unhandled_command:{command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
        result = run_command(args.command, payload)
        output = _base_output(args.command, payload)
        output["result"] = result
        output["sources"] = _result_sources(result)
        output["source"] = output["sources"]
        if isinstance(result.get("warning"), str):
            output["warnings"] = [result["warning"]]
    except (RuntimeError, ValueError) as exc:
        output = _fail(args.command, payload, [str(exc)])
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
