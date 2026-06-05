#!/usr/bin/env python3
"""Audit Aegis Alpha skill capabilities.

This script intentionally uses lightweight static inspection. It does not call
financial data providers or execute skill commands. The goal is to classify the
public command surface before consolidation work begins.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"
PUBLIC_ACCEPTANCE_RISKS = {
    "missing_dispatch",
    "has_not_implemented_return",
    "placeholder_dispatch",
    "hardcoded_root_path",
    "hardcoded_legacy_home_hint",
    "manifest_missing_payload_schema",
    "manifest_missing_result_schema",
    "thin_contract",
}


@dataclass
class CommandAudit:
    name: str
    status: str
    reasons: list[str] = field(default_factory=list)
    manifest_has_description: bool = False
    manifest_has_payload_schema: bool = False
    manifest_has_result_schema: bool = False


@dataclass
class SkillAudit:
    name: str
    path: str
    description: str
    visibility: str
    facade: str
    command_count: int
    commands: list[CommandAudit]
    skill_status: str
    risks: list[str] = field(default_factory=list)
    dispatch_lines: int = 0
    contract_lines: int = 0
    scenario_lines: int = 0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _line_count(path: Path) -> int:
    text = _read_text(path)
    return len(text.splitlines()) if text else 0


def _frontmatter_value(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end < 0:
        return ""
    frontmatter = text[3:end]
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        value = value[1:-1]
    if value == ">-":
        return "(multiline description)"
    return value


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    commands = payload.get("commands")
    return commands if isinstance(commands, list) else []


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_skill_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    frontmatter = text[3:end]
    try:
        import yaml

        parsed = yaml.safe_load(frontmatter)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _skill_visibility(frontmatter: dict[str, Any]) -> tuple[str, str]:
    metadata = frontmatter.get("metadata")
    hermes = metadata.get("hermes") if isinstance(metadata, dict) else {}
    if not isinstance(hermes, dict):
        hermes = {}
    visibility = str(hermes.get("visibility") or "").strip().lower()
    internal = bool(hermes.get("internal")) or visibility in {"internal", "hidden"}
    return ("internal" if internal else "public"), str(hermes.get("facade") or "")


def _extract_compared_commands(dispatch_text: str) -> set[str]:
    commands: set[str] = set()
    command_context_re = re.compile(r"\b(?:args\.)?command\b.*(?:==|!=|\bin\b)")
    for line in dispatch_text.splitlines():
        if "command" in line or "args.command" in line:
            if command_context_re.search(line):
                for name in re.findall(r"""["']([a-z0-9][a-z0-9-]+)["']""", line):
                    if name not in {"source", "result", "status", "data"}:
                        commands.add(name)
        if '": (' in line or '": "' in line:
            for name in re.findall(r"""^\s*["']([a-z0-9][a-z0-9-]+)["']\s*:""", line):
                commands.add(name)
    return commands


def _is_echo_stub(dispatch_text: str) -> bool:
    stripped = dispatch_text.strip()
    if not stripped:
        return False
    if "entrypoint placeholder" in stripped.lower():
        return True
    lines = stripped.splitlines()
    if len(lines) > 80:
        return False
    if "'payload': payload" in dispatch_text and "'result'" not in dispatch_text and '"result"' not in dispatch_text:
        return True
    if '"payload": payload' in dispatch_text and "'result'" not in dispatch_text and '"result"' not in dispatch_text:
        return True
    return False


def _risk_flags(skill_dir: Path, dispatch_text: str, commands: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if not (skill_dir / "scripts" / "dispatch.py").exists():
        risks.append("missing_dispatch")
    if "command not implemented" in dispatch_text:
        risks.append("has_not_implemented_return")
    if "entrypoint placeholder" in dispatch_text.lower():
        risks.append("placeholder_dispatch")
    if "/root/" in dispatch_text:
        risks.append("hardcoded_root_path")
    if "~/.claude" in dispatch_text or "~/.openclaw" in dispatch_text:
        risks.append("hardcoded_legacy_home_hint")
    if re.search(r"return\s+\{\}", dispatch_text):
        risks.append("empty_dict_return")
    if "positions" in dispatch_text and "return []" in dispatch_text:
        risks.append("empty_positions_possible")
    if any("payload_schema" not in cmd and "parameters" not in cmd for cmd in commands):
        risks.append("manifest_missing_payload_schema")
    if any("result_schema" not in cmd for cmd in commands):
        risks.append("manifest_missing_result_schema")
    if _line_count(skill_dir / "references" / "contracts.md") <= 5:
        risks.append("thin_contract")
    return sorted(set(risks))


def _classify_command(
    command: dict[str, Any],
    implemented_commands: set[str],
    dispatch_text: str,
    echo_stub: bool,
    dispatch_exists: bool,
) -> CommandAudit:
    name = str(command.get("name") or command.get("command") or command.get("id") or "")
    has_description = bool(command.get("description"))
    has_payload_schema = bool(command.get("payload_schema") or command.get("parameters"))
    has_result_schema = bool(command.get("result_schema"))
    reasons: list[str] = []

    if not name:
        return CommandAudit(
            name="(unnamed)",
            status="invalid",
            reasons=["manifest command has no name"],
            manifest_has_description=has_description,
            manifest_has_payload_schema=has_payload_schema,
            manifest_has_result_schema=has_result_schema,
        )

    if not dispatch_exists:
        status = "missing"
        reasons.append("dispatch.py missing")
    elif echo_stub:
        status = "stub"
        reasons.append("dispatch only echoes payload or is placeholder")
    elif name in implemented_commands:
        status = "implemented"
        reasons.append("command has explicit dispatch branch")
    elif "command not implemented" in dispatch_text:
        status = "stub"
        reasons.append("manifest command lacks dispatch branch and generic not-implemented fallback exists")
    else:
        status = "partial"
        reasons.append("manifest command not statically matched to a branch")

    if not has_payload_schema:
        reasons.append("manifest missing payload schema")
    if not has_result_schema:
        reasons.append("manifest missing result schema")
    if not has_description:
        reasons.append("manifest missing description")

    return CommandAudit(
        name=name,
        status=status,
        reasons=reasons,
        manifest_has_description=has_description,
        manifest_has_payload_schema=has_payload_schema,
        manifest_has_result_schema=has_result_schema,
    )


def audit_skill(skill_dir: Path) -> SkillAudit:
    skill_text = _read_text(skill_dir / "SKILL.md")
    frontmatter = _parse_skill_frontmatter(skill_text)
    name = _frontmatter_value(skill_text, "name") or skill_dir.name
    description = _frontmatter_value(skill_text, "description")
    visibility, facade = _skill_visibility(frontmatter)
    commands = _load_manifest(skill_dir / "data" / "command-manifest.json")
    dispatch_path = skill_dir / "scripts" / "dispatch.py"
    dispatch_text = _read_text(dispatch_path)
    implemented = _extract_compared_commands(dispatch_text)
    echo_stub = _is_echo_stub(dispatch_text)
    command_audits = [
        _classify_command(cmd, implemented, dispatch_text, echo_stub, dispatch_path.exists())
        for cmd in commands
    ]

    status_counts = Counter(cmd.status for cmd in command_audits)
    if not command_audits:
        skill_status = "no_commands"
    elif status_counts["implemented"] == len(command_audits):
        skill_status = "implemented"
    elif status_counts["implemented"] > 0:
        skill_status = "partial"
    elif status_counts["stub"] > 0:
        skill_status = "stub"
    else:
        skill_status = "unknown"

    return SkillAudit(
        name=name,
        path=str(skill_dir),
        description=description,
        visibility=visibility,
        facade=facade,
        command_count=len(command_audits),
        commands=command_audits,
        skill_status=skill_status,
        risks=_risk_flags(skill_dir, dispatch_text, commands),
        dispatch_lines=_line_count(dispatch_path),
        contract_lines=_line_count(skill_dir / "references" / "contracts.md"),
        scenario_lines=_line_count(skill_dir / "examples" / "scenarios.md"),
    )


def _to_jsonable(audit: SkillAudit) -> dict[str, Any]:
    return {
        "name": audit.name,
        "path": audit.path,
        "description": audit.description,
        "visibility": audit.visibility,
        "facade": audit.facade,
        "skill_status": audit.skill_status,
        "command_count": audit.command_count,
        "dispatch_lines": audit.dispatch_lines,
        "contract_lines": audit.contract_lines,
        "scenario_lines": audit.scenario_lines,
        "risks": audit.risks,
        "commands": [
            {
                "name": cmd.name,
                "status": cmd.status,
                "reasons": cmd.reasons,
                "manifest_has_description": cmd.manifest_has_description,
                "manifest_has_payload_schema": cmd.manifest_has_payload_schema,
                "manifest_has_result_schema": cmd.manifest_has_result_schema,
            }
            for cmd in audit.commands
        ],
    }


def write_markdown(audits: list[SkillAudit], source: Path, out_path: Path) -> None:
    total_commands = sum(a.command_count for a in audits)
    command_status = Counter(cmd.status for audit in audits for cmd in audit.commands)
    skill_status = Counter(a.skill_status for a in audits)
    visibility_status = Counter(a.visibility for a in audits)

    lines: list[str] = [
        "# AI-Invest-OpenClaw Capability Audit",
        "",
        "Generated from static inspection.",
        "",
        f"- Source: `{source}`",
        f"- Skills: {len(audits)}",
        f"- Commands: {total_commands}",
        f"- Visibility: {dict(visibility_status)}",
        f"- Skill status: {dict(skill_status)}",
        f"- Command status: {dict(command_status)}",
        "",
        "## Skill Summary",
        "",
        "| Skill | Visibility | Facade | Status | Commands | Dispatch LOC | Main risks |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for audit in audits:
        risks = ", ".join(audit.risks[:5]) if audit.risks else ""
        if len(audit.risks) > 5:
            risks += f", +{len(audit.risks) - 5} more"
        lines.append(
            f"| `{audit.name}` | `{audit.visibility}` | `{audit.facade}` | `{audit.skill_status}` | "
            f"{audit.command_count} | {audit.dispatch_lines} | {risks} |"
        )

    lines.extend(["", "## Command Classification", ""])
    for audit in audits:
        lines.extend([f"### {audit.name}", ""])
        if not audit.commands:
            lines.append("- No manifest commands found.")
            lines.append("")
            continue
        for cmd in audit.commands:
            lines.append(f"- `{cmd.name}`: `{cmd.status}` - {'; '.join(cmd.reasons)}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_stub_list(audits: list[SkillAudit], out_path: Path) -> None:
    lines = [
        "# AI-Invest-OpenClaw Stub And Partial Command List",
        "",
        "This file lists commands that should not remain in the default public surface without remediation.",
        "",
        "## Stub Commands",
        "",
    ]
    stub_count = 0
    for audit in audits:
        stubs = [cmd for cmd in audit.commands if cmd.status == "stub"]
        if not stubs:
            continue
        lines.append(f"### {audit.name}")
        for cmd in stubs:
            stub_count += 1
            lines.append(f"- `{cmd.name}` - {'; '.join(cmd.reasons)}")
        lines.append("")

    lines.extend(["## Partial Commands", ""])
    partial_count = 0
    for audit in audits:
        partials = [cmd for cmd in audit.commands if cmd.status == "partial"]
        if not partials:
            continue
        lines.append(f"### {audit.name}")
        for cmd in partials:
            partial_count += 1
            lines.append(f"- `{cmd.name}` - {'; '.join(cmd.reasons)}")
        lines.append("")

    lines.insert(3, f"- Stub commands: {stub_count}")
    lines.insert(4, f"- Partial commands: {partial_count}")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_risk_list(audits: list[SkillAudit], out_path: Path) -> None:
    risk_counter = Counter(risk for audit in audits for risk in audit.risks)
    lines = [
        "# AI-Invest-OpenClaw Risk List",
        "",
        "Static risks found during capability audit.",
        "",
        "## Risk Counts",
        "",
        "| Risk | Count |",
        "|---|---:|",
    ]
    for risk, count in sorted(risk_counter.items()):
        lines.append(f"| `{risk}` | {count} |")

    lines.extend(["", "## Risk By Skill", ""])
    for audit in audits:
        if not audit.risks:
            continue
        lines.append(f"### {audit.name}")
        for risk in audit.risks:
            lines.append(f"- `{risk}`")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_merge_map(audits: list[SkillAudit], out_path: Path) -> None:
    skill_names = {audit.name for audit in audits}
    rows = [
        ("search-layer", "information-retrieval", "merge with extraction and research stubs"),
        ("content-extract", "information-retrieval", "merge URL markdown extraction"),
        ("mineru-extract", "information-retrieval", "merge high-fidelity parsing fallback"),
        ("research-tools", "information-retrieval", "replace echo-stub surface with real retrieval router"),
        ("portfolio-management", "portfolio-ops", "merge with position operations and implement state mutations"),
        ("position-ops", "portfolio-ops", "merge risk and sizing commands"),
        ("pipeline-runner", "pipeline", "merge pipeline definitions"),
        ("pipeline-orchestrator", "pipeline", "merge pipeline execution"),
        ("theme-cycle", "theme-cycle", "keep public theme layer"),
        ("themesurfer-signal", "theme-cycle", "move MA signal into theme-cycle"),
        ("akshare", "market-data/internal-adapter", "keep as source adapter"),
        ("baostock", "market-data/internal-adapter", "keep as source adapter"),
        ("tushare", "market-data/internal-adapter", "keep as source adapter"),
        ("hhxg-market", "market-data/internal-adapter", "keep as source adapter"),
        ("jin10-feed", "market-intel/internal-adapter", "keep as news adapter"),
        ("qveris-official", "external-connector", "move out of default investment surface unless implemented"),
    ]

    lines = [
        "# AI-Invest-OpenClaw Merge Map",
        "",
        "Recommended consolidation map generated from the current audit and optimization requirements.",
        "",
        "| Current skill | Target surface | Action | Present |",
        "|---|---|---|---:|",
    ]
    for current, target, action in rows:
        present = "yes" if current in skill_names else "no"
        lines.append(f"| `{current}` | `{target}` | {action} | {present} |")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_surface_report(audits: list[SkillAudit], source: Path, out_path: Path) -> None:
    surface = _load_json(source / "data" / "surface-map.json")
    declared_public = surface.get("public_skills") if isinstance(surface.get("public_skills"), list) else []
    declared_internal = surface.get("internal_skills") if isinstance(surface.get("internal_skills"), dict) else {}
    public_limit = int(surface.get("public_skill_limit") or 15)
    public = sorted(a.name for a in audits if a.visibility == "public")
    internal = sorted(a.name for a in audits if a.visibility == "internal")
    missing_declared_public = sorted(set(declared_public) - set(public))
    undeclared_public = sorted(set(public) - set(declared_public))
    internal_declared_but_not_marked = sorted(set(declared_internal) - set(internal))
    public_risks = {
        a.name: [risk for risk in a.risks if risk in PUBLIC_ACCEPTANCE_RISKS]
        for a in audits
        if a.visibility == "public" and any(risk in PUBLIC_ACCEPTANCE_RISKS for risk in a.risks)
    }
    report = {
        "public_limit": public_limit,
        "public_count": len(public),
        "internal_count": len(internal),
        "public_within_limit": len(public) <= public_limit,
        "public_skills": public,
        "internal_skills": internal,
        "declared_public_skills": declared_public,
        "missing_declared_public": missing_declared_public,
        "undeclared_public": undeclared_public,
        "internal_declared_but_not_marked": internal_declared_but_not_marked,
        "public_risks": public_risks,
    }
    out_path.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# AI-Invest-OpenClaw Surface Report",
        "",
        f"- Public limit: {public_limit}",
        f"- Public count: {len(public)}",
        f"- Internal count: {len(internal)}",
        f"- Public within limit: {len(public) <= public_limit}",
        "",
        "## Public Skills",
        "",
    ]
    lines.extend(f"- `{name}`" for name in public)
    lines.extend(["", "## Internal Skills", ""])
    lines.extend(f"- `{name}`" for name in internal)
    if missing_declared_public or undeclared_public or internal_declared_but_not_marked or public_risks:
        lines.extend(["", "## Surface Risks", ""])
        for name in missing_declared_public:
            lines.append(f"- declared public but not visible: `{name}`")
        for name in undeclared_public:
            lines.append(f"- visible but not declared public: `{name}`")
        for name in internal_declared_but_not_marked:
            lines.append(f"- declared internal but not marked internal: `{name}`")
        for name, risks in public_risks.items():
            lines.append(f"- public skill risks `{name}`: {', '.join(risks)}")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")

    skill_dirs = sorted(path.parent for path in source.glob("*/SKILL.md"))
    audits = [audit_skill(path) for path in skill_dirs]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": str(source),
        "skill_count": len(audits),
        "command_count": sum(a.command_count for a in audits),
        "skills": [_to_jsonable(audit) for audit in audits],
    }
    (args.output_dir / "capability-map.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(audits, source, args.output_dir / "capability-map.md")
    write_stub_list(audits, args.output_dir / "stub-list.md")
    write_risk_list(audits, args.output_dir / "risk-list.md")
    write_merge_map(audits, args.output_dir / "merge-map.md")
    write_surface_report(audits, source, args.output_dir / "surface-report.md")
    visibility = Counter(a.visibility for a in audits)
    print(json.dumps({
        "source": str(source),
        "skills": len(audits),
        "commands": payload["command_count"],
        "visibility": dict(visibility),
        "output_dir": str(args.output_dir),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
