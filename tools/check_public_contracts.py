#!/usr/bin/env python3
"""Strict public command contract gate for Aegis Alpha.

This gate checks the requirements that are stricter than the lightweight
capability audit: every public command must document examples, dependencies,
freshness/staleness policy, and fail-closed error behavior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"

REQUIRED_COMMAND_FIELDS = {
    "name",
    "description",
    "status",
    "payload_schema",
    "result_schema",
    "upstream_dependencies",
    "error_behavior",
}

REQUIRED_RESULT_FIELDS = {
    "ok",
    "decision_allowed",
    "warnings",
    "errors",
    "result",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_ref(manifest: dict[str, Any], ref: str) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        return {}
    defs = manifest.get("$defs")
    if not isinstance(defs, dict):
        return {}
    target = defs.get(ref[len(prefix) :])
    return target if isinstance(target, dict) else {}


def _collect_properties(manifest: dict[str, Any], schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        return _collect_properties(manifest, _resolve_ref(manifest, str(schema["$ref"])))
    props: dict[str, Any] = {}
    if isinstance(schema.get("properties"), dict):
        props.update(schema["properties"])
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            props.update(_collect_properties(manifest, item))
    return props


def _check_command(manifest: dict[str, Any], skill: str, cmd: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    name = str(cmd.get("name") or "(unnamed)")
    for field in sorted(REQUIRED_COMMAND_FIELDS):
        if field not in cmd:
            failures.append({"skill": skill, "command": name, "field": field, "reason": "missing_command_field"})
    if "example" not in cmd and "examples" not in cmd:
        failures.append({"skill": skill, "command": name, "field": "example", "reason": "missing_example"})
    if "freshness_policy" not in cmd and "staleness_policy" not in cmd:
        failures.append({"skill": skill, "command": name, "field": "freshness_policy", "reason": "missing_freshness_policy"})
    if cmd.get("status") != "implemented":
        failures.append({"skill": skill, "command": name, "field": "status", "reason": "public_command_not_implemented"})

    result_props = _collect_properties(manifest, cmd.get("result_schema"))
    for field in sorted(REQUIRED_RESULT_FIELDS):
        if field not in result_props:
            failures.append({"skill": skill, "command": name, "field": f"result.{field}", "reason": "missing_result_field"})
    decision_allowed = result_props.get("decision_allowed")
    if isinstance(decision_allowed, dict) and decision_allowed.get("const") is not False:
        failures.append({"skill": skill, "command": name, "field": "result.decision_allowed", "reason": "must_const_false"})
    return failures


def check_contracts(source: Path) -> dict[str, Any]:
    surface = _load_json(source / "data" / "surface-map.json")
    public_skills = surface.get("public_skills") if isinstance(surface.get("public_skills"), list) else []
    failures: list[dict[str, Any]] = []
    checked_commands = 0
    for skill in public_skills:
        manifest_path = source / str(skill) / "data" / "command-manifest.json"
        manifest = _load_json(manifest_path)
        commands = manifest.get("commands") if isinstance(manifest.get("commands"), list) else []
        if not commands:
            failures.append({"skill": skill, "command": None, "field": "commands", "reason": "public_skill_has_no_commands"})
            continue
        for cmd in commands:
            if not isinstance(cmd, dict):
                failures.append({"skill": skill, "command": None, "field": "commands", "reason": "invalid_command_entry"})
                continue
            checked_commands += 1
            failures.extend(_check_command(manifest, str(skill), cmd))
    return {
        "ok": not failures,
        "public_skill_count": len(public_skills),
        "checked_commands": checked_commands,
        "failure_count": len(failures),
        "failures": failures,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Public Contract Check",
        "",
        f"- OK: {result['ok']}",
        f"- Public skills: {result['public_skill_count']}",
        f"- Checked commands: {result['checked_commands']}",
        f"- Failures: {result['failure_count']}",
        "",
    ]
    if result["failures"]:
        lines.extend(["## Failures", "", "| Skill | Command | Field | Reason |", "|---|---|---|---|"])
        for failure in result["failures"]:
            lines.append(
                f"| `{failure.get('skill')}` | `{failure.get('command')}` | "
                f"`{failure.get('field')}` | `{failure.get('reason')}` |"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = check_contracts(args.source.expanduser().resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "public-contract-check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.output_dir / "public-contract-check.md")
    print(json.dumps({"ok": result["ok"], "failures": result["failure_count"]}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
