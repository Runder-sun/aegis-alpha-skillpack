from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGE = "mineru-extract"


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


def _normalize_sources(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value)


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("OPENCLAW_WORKSPACE", str(_workspace_dir()))
    return env


def _run_json_command(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), env=_build_env())
    text = (proc.stdout or "").strip()
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or text or f"command failed: {' '.join(cmd)}")
    return json.loads(proc.stdout)


def run_command(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_command(command)
    scripts_dir = _package_root() / "scripts"

    if command == "parse-documents":
        sources = _normalize_sources(payload.get("file_sources"))
        if not sources:
            raise SystemExit("parse-documents requires file_sources")
        script = scripts_dir / "mineru_parse_documents.py"
        cmd = [sys.executable, str(script), "--file-sources", sources]
        if payload.get("enable_ocr"):
            cmd.append("--enable-ocr")
        if payload.get("language"):
            cmd.extend(["--language", str(payload["language"])])
        if payload.get("page_ranges"):
            cmd.extend(["--page-ranges", str(payload["page_ranges"])])
        if payload.get("model_version"):
            cmd.extend(["--model-version", str(payload["model_version"])])
        if payload.get("enable_table") is not None:
            cmd.extend(["--enable-table", "true" if payload.get("enable_table") else "false"])
        if payload.get("enable_formula") is not None:
            cmd.extend(["--enable-formula", "true" if payload.get("enable_formula") else "false"])
        if payload.get("extra_formats"):
            formats = payload["extra_formats"]
            if isinstance(formats, list):
                formats = ",".join(str(item) for item in formats if str(item).strip())
            cmd.extend(["--extra-formats", str(formats)])
        if payload.get("timeout") is not None:
            cmd.extend(["--timeout", str(payload["timeout"])])
        if payload.get("poll_interval") is not None:
            cmd.extend(["--poll-interval", str(payload["poll_interval"])])
        if payload.get("cache") is False:
            cmd.append("--no-cache")
        if payload.get("force"):
            cmd.append("--force")
        if payload.get("emit_markdown"):
            cmd.append("--emit-markdown")
        if payload.get("max_chars") is not None:
            cmd.extend(["--max-chars", str(payload["max_chars"])])
        return _run_json_command(cmd, cwd=scripts_dir)

    if command == "extract-url":
        source = payload.get("url") or payload.get("source")
        if not source:
            raise SystemExit("extract-url requires url")
        script = scripts_dir / "mineru_extract.py"
        cmd = [sys.executable, str(script), str(source)]
        if payload.get("model"):
            cmd.extend(["--model", str(payload["model"])])
        if payload.get("api_base"):
            cmd.extend(["--api-base", str(payload["api_base"])])
        if payload.get("timeout") is not None:
            cmd.extend(["--timeout", str(payload["timeout"])])
        if payload.get("poll_interval") is not None:
            cmd.extend(["--poll-interval", str(payload["poll_interval"])])
        if payload.get("ocr") is not None:
            cmd.append("--ocr" if payload.get("ocr") else "--no-ocr")
        if payload.get("formula") is not None:
            cmd.append("--formula" if payload.get("formula") else "--no-formula")
        if payload.get("table") is not None:
            cmd.append("--table" if payload.get("table") else "--no-table")
        if payload.get("language"):
            cmd.extend(["--language", str(payload["language"])])
        if payload.get("page_ranges"):
            cmd.extend(["--page-ranges", str(payload["page_ranges"])])
        if payload.get("extra_formats"):
            formats = payload["extra_formats"]
            if isinstance(formats, list):
                formats = ",".join(str(item) for item in formats if str(item).strip())
            cmd.extend(["--extra-formats", str(formats)])
        if payload.get("out"):
            cmd.extend(["--out", str(payload["out"])])
        if payload.get("print"):
            cmd.append("--print")
        if payload.get("max_chars") is not None:
            cmd.extend(["--max-chars", str(payload["max_chars"])])
        return _run_json_command(cmd, cwd=scripts_dir)

    raise SystemExit(f"unhandled command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    result = run_command(args.command, json.loads(args.payload))
    print(json.dumps({"package": PACKAGE, "command": args.command, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
