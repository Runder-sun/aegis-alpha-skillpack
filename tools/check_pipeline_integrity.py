#!/usr/bin/env python3
"""Validate Aegis Alpha pipeline references.

The acceptance doc requires every pipeline package/command reference to exist
and not depend on stub commands. This check is static by design; runtime smoke
tests separately verify selected happy/fail-closed paths.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_compared_commands(dispatch_text: str) -> set[str]:
    commands: set[str] = set()
    command_context_re = re.compile(r"\b(?:args\.)?command\b.*(?:==|!=|\bin\b)")
    for line in dispatch_text.splitlines():
        if "command" in line or "args.command" in line:
            if command_context_re.search(line):
                for name in re.findall(r"""["']([a-z0-9][a-z0-9-]+)["']""", line):
                    commands.add(name)
        if '": (' in line or '": "' in line:
            for name in re.findall(r"""^\s*["']([a-z0-9][a-z0-9-]+)["']\s*:""", line):
                commands.add(name)
    return commands


def _manifest_commands(source: Path) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    for path in source.glob("*/data/command-manifest.json"):
        skill = path.parents[1].name
        manifest = _load_json(path)
        commands = {}
        for cmd in manifest.get("commands", []):
            if isinstance(cmd, dict) and cmd.get("name"):
                commands[str(cmd["name"])] = cmd
        index[skill] = commands
    return index


def check_pipeline_integrity(source: Path) -> dict[str, Any]:
    pipelines_path = source / "pipeline-runner" / "data" / "pipelines.json"
    pipelines = _load_json(pipelines_path).get("pipelines")
    manifest_index = _manifest_commands(source)
    failures: list[dict[str, Any]] = []
    checked_steps = 0
    push_steps = 0

    if not isinstance(pipelines, list):
        return {
            "ok": False,
            "checked_steps": 0,
            "push_steps": 0,
            "failures": [{"pipeline": None, "step": None, "reason": "pipelines_json_missing_or_invalid"}],
        }

    for pipeline in pipelines:
        if not isinstance(pipeline, dict):
            failures.append({"pipeline": None, "step": None, "reason": "invalid_pipeline_entry"})
            continue
        pipeline_id = pipeline.get("id")
        steps = pipeline.get("steps")
        if not isinstance(steps, list) or not steps:
            failures.append({"pipeline": pipeline_id, "step": None, "reason": "pipeline_has_no_steps"})
            continue
        for idx, step in enumerate(steps):
            checked_steps += 1
            if not isinstance(step, dict):
                failures.append({"pipeline": pipeline_id, "step": idx, "reason": "invalid_step_entry"})
                continue
            package = str(step.get("package") or "")
            command = str(step.get("command") or "")
            if "push" in command or command.endswith("-push"):
                push_steps += 1
                if step.get("optional") is not True:
                    failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "push_step_must_be_optional"})
            if package not in manifest_index:
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "package_manifest_missing"})
                continue
            cmd_manifest = manifest_index[package].get(command)
            if cmd_manifest is None:
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "command_manifest_missing"})
                continue
            if str(cmd_manifest.get("status") or "implemented") in {"stub", "planned", "partial", "not_implemented"}:
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "command_not_implemented"})
            dispatch = source / package / "scripts" / "dispatch.py"
            if not dispatch.exists():
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "dispatch_missing"})
                continue
            dispatch_text = dispatch.read_text(encoding="utf-8", errors="ignore")
            if "command not implemented" in dispatch_text:
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "dispatch_has_not_implemented_fallback"})
            implemented = _extract_compared_commands(dispatch_text)
            if command not in implemented:
                failures.append({"pipeline": pipeline_id, "step": idx, "package": package, "command": command, "reason": "command_not_statically_matched"})

    return {
        "ok": not failures,
        "pipeline_count": len(pipelines),
        "checked_steps": checked_steps,
        "push_steps": push_steps,
        "push_default_policy": "pipeline-orchestrator skips *-push steps unless allow_push=true",
        "failures": failures,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Pipeline Integrity Check",
        "",
        f"- OK: {result['ok']}",
        f"- Pipelines: {result.get('pipeline_count')}",
        f"- Checked steps: {result['checked_steps']}",
        f"- Push steps: {result['push_steps']}",
        f"- Push default policy: {result['push_default_policy']}",
        "",
    ]
    if result["failures"]:
        lines.extend(["## Failures", "", "| Pipeline | Step | Package | Command | Reason |", "|---|---:|---|---|---|"])
        for failure in result["failures"]:
            lines.append(
                f"| `{failure.get('pipeline')}` | {failure.get('step')} | "
                f"`{failure.get('package')}` | `{failure.get('command')}` | `{failure.get('reason')}` |"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = check_pipeline_integrity(args.source.expanduser().resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "pipeline-integrity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.output_dir / "pipeline-integrity.md")
    print(json.dumps({"ok": result["ok"], "failures": len(result["failures"])}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
