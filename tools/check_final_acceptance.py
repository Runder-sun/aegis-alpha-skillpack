#!/usr/bin/env python3
"""Final go/no-go acceptance gate for Aegis Alpha."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"
REQUIRED_CONTRACT_TERMS = {
    "as_of",
    "freshness",
    "decision_allowed",
    "source",
    "warnings",
    "errors",
    "missing_critical_inputs",
}
REQUIRED_DATA_QUALITY_TERMS = {
    "Data Quality Policy",
    "unit",
    "frequency",
    "adjustment",
    "source",
    "freshness",
    "missing_critical_inputs",
    "fail",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        return {"_invalid_json": str(exc)}
    return payload if isinstance(payload, dict) else {"_invalid_json": "not_an_object"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _add(checks: list[dict[str, Any]], category: str, name: str, passed: bool, evidence: Any) -> None:
    checks.append({
        "category": category,
        "name": name,
        "passed": bool(passed),
        "evidence": evidence,
    })


def _public_skill_contract_docs(source: Path, public_skills: list[str]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    forbidden_hits: dict[str, list[str]] = {}
    for skill in public_skills:
        text = _read_text(source / skill / "references" / "contracts.md")
        terms_missing = sorted(term for term in REQUIRED_CONTRACT_TERMS if term not in text)
        if terms_missing:
            missing[skill] = terms_missing
        bad_terms = []
        lowered = text.lower()
        for term in ("empty structure when missing", "empty result when missing", "silently fallback", "silent fallback"):
            if term in lowered:
                bad_terms.append(term)
        if bad_terms:
            forbidden_hits[skill] = bad_terms
    return {"missing_terms": missing, "forbidden_terms": forbidden_hits}


def _count_command_statuses(capability: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for skill in capability.get("skills", []):
        if not isinstance(skill, dict):
            continue
        for command in skill.get("commands", []):
            if not isinstance(command, dict):
                continue
            status = str(command.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
    return counts


def _public_command_failures(capability: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for skill in capability.get("skills", []):
        if not isinstance(skill, dict) or skill.get("visibility") != "public":
            continue
        for command in skill.get("commands", []):
            if not isinstance(command, dict):
                continue
            if command.get("status") != "implemented":
                failures.append({
                    "skill": skill.get("name"),
                    "command": command.get("name"),
                    "status": command.get("status"),
                    "reasons": command.get("reasons"),
                })
    return failures


def _closed_loop_stage_coverage(closed_loop: dict[str, Any]) -> dict[str, bool]:
    names = " | ".join(str(check.get("name") or "") for check in closed_loop.get("checks", []) if isinstance(check, dict)).lower()
    return {
        "regime": "regime" in names,
        "theme": "theme" in names,
        "screening": "candidate" in names or "screening" in names,
        "research": "research" in names,
        "trade_plan": "trade plan" in names,
        "portfolio_risk": "portfolio risk" in names,
        "advice_lifecycle": "advice" in names and "lifecycle" in names,
        "report_review": "report" in names and ("alignment" in names or "evidence" in names),
    }


def _smoke_fail_closed_coverage(smoke: dict[str, Any]) -> dict[str, Any]:
    fail_closed = []
    for check in smoke.get("checks", []):
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "").lower()
        if "fails closed" in name or "fail-closed" in name:
            fail_closed.append({"name": check.get("name"), "ok": check.get("ok") is True})
    return {
        "count": len(fail_closed),
        "failed": [item for item in fail_closed if not item["ok"]],
        "checks": fail_closed,
    }


def evaluate(source: Path, audit_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    surface = _load_json(source / "data" / "surface-map.json")
    capability = _load_json(audit_dir / "capability-map.json")
    surface_report = _load_json(audit_dir / "surface-report.json")
    visibility = _load_json(audit_dir / "public-skill-visibility.json")
    contracts = _load_json(audit_dir / "public-contract-check.json")
    pipeline = _load_json(audit_dir / "pipeline-integrity.json")
    smoke = _load_json(audit_dir / "smoke-results.json")
    closed_loop = _load_json(audit_dir / "closed-loop-smoke-results.json")

    public_skills = [str(item) for item in surface.get("public_skills", []) if item]
    internal_skills = sorted((surface.get("internal_skills") or {}).keys())
    safety = surface.get("safety_policy") if isinstance(surface.get("safety_policy"), dict) else {}

    _add(
        checks,
        "surface",
        "public surface is no more than declared limit",
        len(public_skills) <= int(surface.get("public_skill_limit") or 15) and surface_report.get("public_within_limit") is True,
        {"public_count": len(public_skills), "limit": surface.get("public_skill_limit"), "surface_report": surface_report.get("public_count")},
    )
    _add(
        checks,
        "surface",
        "internal adapters are hidden from default discovery",
        visibility.get("ok") is True and not visibility.get("listed_internal") and not visibility.get("command_internal") and not visibility.get("prompt_internal"),
        visibility,
    )
    _add(
        checks,
        "surface",
        "surface map declares public and internal layers",
        bool(public_skills) and bool(internal_skills),
        {"public_skills": public_skills, "internal_count": len(internal_skills)},
    )

    command_counts = _count_command_statuses(capability)
    public_command_failures = _public_command_failures(capability)
    _add(
        checks,
        "implementation",
        "all public commands are implemented",
        not public_command_failures,
        public_command_failures,
    )
    _add(
        checks,
        "implementation",
        "no stub or partial commands remain in manifests",
        command_counts.get("stub", 0) == 0 and command_counts.get("partial", 0) == 0,
        command_counts,
    )

    _add(
        checks,
        "contract",
        "public manifest contract gate passes",
        contracts.get("ok") is True and int(contracts.get("failure_count") or 0) == 0,
        contracts,
    )
    doc_check = _public_skill_contract_docs(source, public_skills)
    _add(
        checks,
        "contract",
        "public contract docs include required provenance and safety fields",
        not doc_check["missing_terms"],
        doc_check["missing_terms"],
    )
    _add(
        checks,
        "contract",
        "public contract docs do not describe missing data as empty success",
        not doc_check["forbidden_terms"],
        doc_check["forbidden_terms"],
    )

    description = _read_text(source / "DESCRIPTION.md")
    missing_data_quality_terms = sorted(term for term in REQUIRED_DATA_QUALITY_TERMS if term not in description)
    _add(
        checks,
        "data_quality",
        "package-level data quality policy documents freshness, units, frequency, adjustment basis, and provenance",
        not missing_data_quality_terms,
        {"missing_terms": missing_data_quality_terms},
    )
    _add(
        checks,
        "safety",
        "surface safety policy is fail-closed and research-only",
        safety.get("decision_allowed") is False
        and safety.get("requires_human_confirmation") is True
        and safety.get("fail_closed") is True
        and safety.get("no_silent_fallback") is True
        and safety.get("no_empty_success_for_missing_evidence") is True,
        safety,
    )

    _add(
        checks,
        "pipeline",
        "pipeline references resolve to implemented commands",
        pipeline.get("ok") is True and not pipeline.get("failures"),
        pipeline,
    )

    fail_closed = _smoke_fail_closed_coverage(smoke)
    _add(
        checks,
        "smoke",
        "critical smoke suite passes",
        smoke.get("ok") is True and not smoke.get("failed"),
        {"ok": smoke.get("ok"), "failed": smoke.get("failed")},
    )
    _add(
        checks,
        "smoke",
        "smoke suite covers multiple fail-closed scenarios",
        fail_closed["count"] >= 5 and not fail_closed["failed"],
        fail_closed,
    )

    closed_loop_coverage = _closed_loop_stage_coverage(closed_loop)
    _add(
        checks,
        "closed_loop",
        "investment closed-loop smoke passes",
        closed_loop.get("ok") is True and not closed_loop.get("failed"),
        {"ok": closed_loop.get("ok"), "failed": closed_loop.get("failed"), "artifacts": closed_loop.get("artifacts")},
    )
    _add(
        checks,
        "closed_loop",
        "closed-loop smoke covers regime, theme, screening, research, trade plan, risk, advice, and report review",
        all(closed_loop_coverage.values()),
        closed_loop_coverage,
    )

    failures = [check for check in checks if not check["passed"]]
    return {
        "ok": not failures,
        "source": str(source),
        "audit_dir": str(audit_dir),
        "checked_at": None,
        "summary": {
            "checks": len(checks),
            "failures": len(failures),
            "public_skill_count": len(public_skills),
            "internal_skill_count": len(internal_skills),
            "public_command_count": contracts.get("checked_commands"),
            "pipeline_steps": pipeline.get("checked_steps"),
            "smoke_checks": len(smoke.get("checks", [])) if isinstance(smoke.get("checks"), list) else None,
            "closed_loop_checks": len(closed_loop.get("checks", [])) if isinstance(closed_loop.get("checks"), list) else None,
        },
        "checks": checks,
        "failures": failures,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Acceptance Matrix",
        "",
        f"- OK: {result['ok']}",
        f"- Source: `{result['source']}`",
        f"- Audit dir: `{result['audit_dir']}`",
        f"- Checks: {result['summary']['checks']}",
        f"- Failures: {result['summary']['failures']}",
        f"- Public skills: {result['summary']['public_skill_count']}",
        f"- Internal skills: {result['summary']['internal_skill_count']}",
        f"- Public commands checked: {result['summary']['public_command_count']}",
        f"- Pipeline steps checked: {result['summary']['pipeline_steps']}",
        "",
        "## Checks",
        "",
        "| Category | Check | Pass |",
        "|---|---|---:|",
    ]
    for check in result["checks"]:
        lines.append(f"| `{check['category']}` | {check['name']} | {check['passed']} |")
    if result["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in result["failures"]:
            lines.append(f"- `{failure['category']}`: {failure['name']}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.source.expanduser().resolve(), args.audit_dir.resolve())
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    (args.audit_dir / "final-acceptance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.audit_dir / "final-acceptance.md")
    print(json.dumps({"ok": result["ok"], "failures": result["summary"]["failures"]}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
