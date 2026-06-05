#!/usr/bin/env python3
"""Fill missing strict contract metadata for public ai-invest manifests.

This is a deterministic maintenance script for the optimization plan. It only
adds missing manifest fields and upgrades result-schema definitions with common
research safety envelope fields; it does not edit dispatch code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"


SKILL_POLICIES = {
    "information-retrieval": {
        "upstream": ["public facade route", "explicit query/url/path payload"],
        "freshness": "Freshness is delegated to the routed retrieval adapter and preserved in delegated result fields when available.",
        "errors": ["delegate_failed", "dispatch_not_found", "query_or_queries_required", "url_required", "document_source_required"],
        "example": {},
    },
    "market-data": {
        "upstream": ["memory/prewarm/nightly-prewarm-*.json"],
        "freshness": "Data is read only from the latest prewarm artifact; missing artifact or missing command field fails closed.",
        "errors": ["prewarm_directory_missing", "prewarm_artifact_missing", "prewarm_artifact_invalid_json", "required_market_data_missing"],
        "example": {},
    },
    "market-intel": {
        "upstream": ["memory/prewarm/nightly-prewarm-*.json", "optional explicit provider payload"],
        "freshness": "Intelligence freshness is inherited from prewarm artifacts and provider timestamps; provider absence is not neutral evidence.",
        "errors": ["intelligence_source_missing", "market_sentiment_inputs_missing", "policy_items_missing", "research_reports_missing"],
        "example": {},
    },
    "macro-regime": {
        "upstream": ["memory/prewarm/nightly-prewarm-*.json", "macro cache", "market-intel outputs when present"],
        "freshness": "Macro freshness is inherited from the latest artifact/cache timestamps; stale or missing critical fields are surfaced.",
        "errors": ["macro_regime_inputs_missing", "macro_snapshot_missing", "concept_inputs_missing", "global_macro_inputs_missing"],
        "example": {},
    },
    "theme-cycle": {
        "upstream": ["memory/prewarm/nightly-prewarm-*.json", "memory/themes.json", "macro-regime public outputs"],
        "freshness": "Theme freshness is inherited from theme store updated_at, latest prewarm artifact, and macro-regime outputs.",
        "errors": ["theme_store_missing", "market_risk_inputs_missing", "event_inputs_missing", "theme_inputs_missing"],
        "example": {},
    },
    "equity-screening": {
        "upstream": ["explicit candidates or memory/prewarm/nightly-prewarm-*.json", "memory/stock_pool artifacts when used"],
        "freshness": "Candidate freshness is inherited from explicit payload evidence or latest prewarm artifact; missing candidates fail closed.",
        "errors": ["candidates_missing", "evidence_source_missing", "stock_pool_invalid_json", "prewarm_snapshot_missing"],
        "example": {"candidates": [{"name": "示例公司", "theme": "示例主题", "net_yi": 1, "news_hits": 1}]},
    },
    "equity-research": {
        "upstream": ["explicit metrics/financials/context/news", "memory/prewarm/nightly-prewarm-*.json when used"],
        "freshness": "Research freshness is inherited from supplied metrics/evidence and latest prewarm artifact when used.",
        "errors": ["insufficient_financial_metrics", "valuation_metrics_missing", "code_name_or_query_required"],
        "example": {"code": "600000", "name": "示例公司", "metrics": {"roe": 0.15, "net_margin": 0.1, "revenue_growth": 0.1}},
    },
    "trade-planning": {
        "upstream": ["explicit candidates", "explicit themes", "explicit technical levels", "latest prewarm market gate when used"],
        "freshness": "Plan freshness is inherited from supplied market gate, candidates, themes, and technical levels.",
        "errors": ["candidates_missing", "themes_missing", "technical_inputs_missing", "market_filter_missing"],
        "example": {"themesurfer_status": "FULL", "risk_level": "green", "candidates": [{"name": "示例公司"}], "technical": {"price": 10, "ma20": 9}},
    },
    "portfolio-ops": {
        "upstream": ["portfolio-management facade route", "position-ops facade route", "memory/positions.json"],
        "freshness": "Portfolio freshness is delegated to state files and explicit trade/risk payloads; missing state fails closed.",
        "errors": ["portfolio_state_missing", "sell_quantity_exceeds_position", "missing_required_input", "dispatch_not_found"],
        "example": {},
    },
    "pipeline": {
        "upstream": ["pipeline-runner facade route", "pipeline-orchestrator facade route", "workspace skills"],
        "freshness": "Pipeline freshness is delegated to the routed pipeline artifact and step outputs.",
        "errors": ["pipeline_not_found", "delegate_failed", "dispatch_not_found", "pipeline_step_failed"],
        "example": {"dry_run": True},
    },
    "quality-gate": {
        "upstream": ["memory/prewarm", "memory/pipeline_runs", "memory/reports", "quant-validation when delegated"],
        "freshness": "Quality status is derived from current workspace artifacts at command runtime.",
        "errors": ["prewarm_present_failed", "pipeline_present_failed", "report_present_failed", "missing_runtime_artifacts"],
        "example": {},
    },
    "quant-validation": {
        "upstream": ["explicit price_series/prices/returns/equity_curve or explicit series_path"],
        "freshness": "Backtest freshness is inherited from the supplied historical series; missing or invalid history fails closed.",
        "errors": ["historical_series_required", "insufficient_history", "invalid_strategy", "grid_required"],
        "example": {"price_series": [{"close": 10}, {"close": 11}, {"close": 12}], "strategy": {"type": "buy_and_hold"}},
    },
    "report-evolution": {
        "upstream": ["memory/pipeline_runs", "memory/reports", "memory/pipeline_context", "memory/report_evidence"],
        "freshness": "Report evolution artifacts are derived from current workspace report, pipeline, context, and evidence artifacts.",
        "errors": ["report_evidence_not_found", "missing_explicit_artifact", "invalid_evidence_metadata", "invalid_payload_json"],
        "example": {"pipeline_id": "nightly"},
    },
    "execution-automation": {
        "upstream": ["memory/prewarm", "scripts/nightly_prewarm.py", "report text/path", "Feishu env vars for confirmed sends"],
        "freshness": "Automation freshness is current at command runtime; market evidence freshness is inherited from prewarm artifacts.",
        "errors": ["prewarm_artifact_missing", "prewarm_stale", "external_send_requires_confirm", "report_text_required"],
        "example": {"dry_run": True},
    },
    "advice-lifecycle": {
        "upstream": ["memory/advice/advice-ledger.json", "explicit recommendation/price/update payloads", "pipeline/prewarm/theme artifacts for reports"],
        "freshness": "Advice ledger freshness is current at command runtime; market freshness is inherited from source artifacts.",
        "errors": ["advice_ledger_missing", "recommendations_required", "prices_required", "updates_required"],
        "example": {},
    },
}


COMMAND_EXAMPLES = {
    "snapshot-full": {},
    "margin-full": {},
    "calendar-week": {},
    "macro-pmi": {},
    "macro-cpi": {},
    "macro-ppi": {},
    "index-daily": {"symbol": "sh.000001"},
    "stock-technical-scan": {"price": 10, "ma20": 9, "ma60": 8, "support": 8.5, "resistance": 12},
    "nightly-quality-gate": {},
    "backtest-loop": {"command": "nightly-eval-12m"},
    "capture-report-evidence": {"pipeline_id": "nightly"},
    "align-report-outcome": {"pipeline_id": "nightly"},
}


COMMON_RESULT_PROPERTIES = {
    "ok": {"type": "boolean"},
    "decision_allowed": {"type": "boolean", "const": False},
    "requires_human_confirmation": {"type": "boolean", "const": True},
    "as_of": {"type": "string"},
    "freshness": {"type": "object"},
    "source": {"type": ["array", "string"], "items": {"type": "string"}},
    "sources": {"type": "array", "items": {"type": "string"}},
    "artifacts": {"type": "array", "items": {"type": "string"}},
    "warnings": {"type": "array", "items": {"type": "string"}},
    "errors": {"type": "array", "items": {"type": "string"}},
    "missing_critical_inputs": {"type": "array"},
    "result": {"type": "object"},
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(manifest: dict[str, Any], ref: str) -> dict[str, Any] | None:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        return None
    defs = manifest.setdefault("$defs", {})
    target = defs.get(ref[len(prefix) :])
    return target if isinstance(target, dict) else None


def _upgrade_schema(schema: dict[str, Any], max_action_level: str | None) -> None:
    props = schema.setdefault("properties", {})
    props.update({key: value for key, value in COMMON_RESULT_PROPERTIES.items() if key not in props})
    if max_action_level:
        props.setdefault("max_action_level", {"type": "string", "const": max_action_level})
    else:
        props.setdefault("max_action_level", {"type": "string"})
    required = set(schema.get("required") if isinstance(schema.get("required"), list) else [])
    required.update(["ok", "decision_allowed", "warnings", "errors", "result"])
    schema["required"] = sorted(required)


def _upgrade_result_schema(manifest: dict[str, Any], cmd: dict[str, Any], max_action_level: str | None) -> None:
    schema = cmd.get("result_schema")
    if isinstance(schema, dict) and "$ref" in schema:
        target = _resolve_ref(manifest, str(schema["$ref"]))
        if target is not None:
            _upgrade_schema(target, max_action_level)
    elif isinstance(schema, dict):
        _upgrade_schema(schema, max_action_level)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    surface = _load_json(source / "data" / "surface-map.json")
    public_skills = surface.get("public_skills") if isinstance(surface.get("public_skills"), list) else []
    changed: list[str] = []
    for skill in public_skills:
        path = source / str(skill) / "data" / "command-manifest.json"
        manifest = _load_json(path)
        policy = SKILL_POLICIES.get(str(skill), {})
        safety = manifest.get("safety_policy") if isinstance(manifest.get("safety_policy"), dict) else manifest.get("safety_model")
        max_action_level = None
        if isinstance(safety, dict):
            max_action_level = safety.get("max_action_level")
        before = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
        for cmd in manifest.get("commands", []):
            if not isinstance(cmd, dict):
                continue
            name = str(cmd.get("name") or "")
            cmd.setdefault("upstream_dependencies", policy.get("upstream", []))
            cmd.setdefault("freshness_policy", policy.get("freshness", "Freshness is inherited from explicit payloads and source artifacts."))
            cmd.setdefault("error_behavior", policy.get("errors", ["missing_required_input"]))
            if "example" not in cmd and "examples" not in cmd:
                cmd["example"] = COMMAND_EXAMPLES.get(name, policy.get("example", {}))
            _upgrade_result_schema(manifest, cmd, str(max_action_level) if max_action_level else None)
        after = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
        if after != before:
            path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed.append(str(path))
    print(json.dumps({"changed": changed, "count": len(changed)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
