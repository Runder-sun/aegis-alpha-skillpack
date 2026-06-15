#!/usr/bin/env python3
"""Smoke tests for the Aegis Alpha public skill surface.

The tests use a temporary workspace and avoid network-dependent commands.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"


def _run(workspace: Path, package: str, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    dispatch = SKILL_ROOT / package / "scripts" / "dispatch.py"
    env = dict(os.environ)
    env["AEGIS_ALPHA_WORKSPACE"] = str(workspace)
    args = [sys.executable, str(dispatch), "--command", command]
    if payload is not None:
        args.extend(["--payload", json.dumps(payload, ensure_ascii=False)])
    proc = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
    text = (proc.stdout or "").strip()
    try:
        output = json.loads(text) if text else {}
    except json.JSONDecodeError:
        output = {"ok": False, "raw": text, "stderr": proc.stderr}
    output["_returncode"] = proc.returncode
    return output


def _check(name: str, condition: bool, detail: Any) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(condition),
        "detail": detail,
    }


def _delegated_result(output: dict[str, Any]) -> dict[str, Any]:
    delegated = output.get("result", {}).get("delegated")
    if isinstance(delegated, dict) and isinstance(delegated.get("result"), dict):
        return delegated["result"]
    result = output.get("result")
    return result if isinstance(result, dict) else {}


def _delegated_errors(output: dict[str, Any]) -> list[str]:
    errors = list(output.get("errors") or [])
    delegated = output.get("result", {}).get("delegated")
    if isinstance(delegated, dict):
        errors.extend(delegated.get("errors") or [])
    return errors


def run_smoke(workspace: Path) -> dict[str, Any]:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    checks: list[dict[str, Any]] = []

    missing = _run(workspace, "portfolio-ops", "portfolio-view")
    checks.append(_check(
        "portfolio-view fails closed when state is missing",
        missing.get("ok") is False and _delegated_result(missing).get("portfolio_state_known") is False,
        missing,
    ))

    added = _run(workspace, "portfolio-ops", "portfolio-add", {
        "code": "600519",
        "name": "贵州茅台",
        "quantity": 10,
        "price": 1500,
    })
    checks.append(_check(
        "portfolio-add creates state artifact",
        added.get("ok") is True and (workspace / "memory" / "positions.json").exists(),
        added,
    ))

    sold = _run(workspace, "portfolio-ops", "record-trade", {
        "code": "600519",
        "side": "sell",
        "quantity": 3,
        "price": 1600,
    })
    checks.append(_check(
        "record-trade sell updates remaining quantity",
        sold.get("ok") is True and _delegated_result(sold).get("remaining_quantity") == 7.0,
        sold,
    ))

    oversell = _run(workspace, "portfolio-ops", "record-trade", {
        "code": "600519",
        "side": "sell",
        "quantity": 99,
        "price": 1600,
    })
    checks.append(_check(
        "record-trade oversell fails closed",
        oversell.get("ok") is False and "sell_quantity_exceeds_position" in _delegated_errors(oversell),
        oversell,
    ))

    position_view = _run(workspace, "portfolio-ops", "position-management")
    checks.append(_check(
        "position-management-v2 reads known state",
        position_view.get("ok") is True and _delegated_result(position_view).get("count") == 1,
        position_view,
    ))

    risk = _run(workspace, "portfolio-ops", "portfolio-risk-check", {"max_single_position_pct": 0.5})
    checks.append(_check(
        "portfolio-risk-check flags concentration",
        risk.get("ok") is True and _delegated_result(risk).get("risk_flag_count", 0) >= 1,
        risk,
    ))

    sizing_missing = _run(workspace, "portfolio-ops", "position-sizing-advisor", {"portfolio_value": 100000})
    checks.append(_check(
        "position-sizing-advisor fails closed on missing inputs",
        sizing_missing.get("ok") is False and any("missing_required_input" in e for e in _delegated_errors(sizing_missing)),
        sizing_missing,
    ))

    research_history = _run(workspace, "information-retrieval", "research-history", {})
    checks.append(_check(
        "information-retrieval research-history returns local artifact envelope",
        research_history.get("ok") is True
        and research_history.get("decision_allowed") is False
        and "delegated" in research_history.get("result", {}),
        research_history,
    ))

    preference = _run(workspace, "information-retrieval", "set-research-preference", {
        "key": "preferred_sources",
        "value": ["official", "exchange", "company"],
    })
    checks.append(_check(
        "information-retrieval set-research-preference writes artifact",
        preference.get("ok") is True and (workspace / "memory" / "research" / "preferences.json").exists(),
        preference,
    ))

    equity_payload = {
        "code": "600519",
        "name": "贵州茅台",
        "metrics": {
            "roe": 0.28,
            "net_margin": 0.42,
            "revenue_growth": 0.12,
            "net_profit_growth": 0.15,
            "debt_to_asset": 0.22,
            "operating_cashflow": 720,
            "net_profit": 650,
            "price": 1500,
            "eps": 60,
            "industry_pe": 30,
            "dividend_yield": 0.035,
        },
        "context": {
            "summary": "高端白酒龙头，现金流强。",
            "thesis": "品牌和渠道壁垒支撑长期盈利。",
            "risks": ["消费疲弱", "估值波动"],
        },
        "news": [{"title": "贵州茅台发布经营数据", "content": "贵州茅台收入增长稳健"}],
        "narrative_score": 75,
    }

    diagnosis = _run(workspace, "equity-research", "financial-diagnosis", equity_payload)
    checks.append(_check(
        "equity financial-diagnosis scores supplied metrics",
        diagnosis.get("ok") is True and diagnosis.get("result", {}).get("grade") == "strong",
        diagnosis,
    ))

    valuation_missing = _run(workspace, "equity-research", "valuation-check", {"code": "600519"})
    checks.append(_check(
        "equity valuation-check fails closed without valuation metrics",
        valuation_missing.get("ok") is False and "valuation_metrics_missing" in valuation_missing.get("errors", []),
        valuation_missing,
    ))

    stock_analysis = _run(workspace, "equity-research", "stock-analysis", equity_payload)
    checks.append(_check(
        "equity stock-analysis composes complete research package",
        stock_analysis.get("ok") is True
        and stock_analysis.get("result", {}).get("research_complete") is True
        and stock_analysis.get("decision_allowed") is False,
        stock_analysis,
    ))

    screening_payload = {
        "candidates": [
            {"name": "贵州茅台", "theme": "消费", "net_yi": 5, "news_hits": 2, "research_hits": 1},
            {"name": "宁德时代", "theme": "新能源", "net_yi": 8, "limitup": 2, "news_hits": 3},
        ],
        "min_score": 50,
    }

    screening = _run(workspace, "equity-screening", "stock-screening", screening_payload)
    checks.append(_check(
        "equity-screening stock-screening scores payload candidates",
        screening.get("ok") is True
        and screening.get("decision_allowed") is False
        and len(screening.get("result", {}).get("candidates", [])) == 2,
        screening,
    ))

    screening_missing = _run(workspace, "equity-screening", "stock-screening", {})
    checks.append(_check(
        "equity-screening stock-screening fails closed without candidates or prewarm",
        screening_missing.get("ok") is False and "candidates_missing" in screening_missing.get("errors", []),
        screening_missing,
    ))

    layered_screening = _run(workspace, "equity-screening", "layered-stock-screening", screening_payload)
    checks.append(_check(
        "equity-screening layered-stock-screening returns candidate layers",
        layered_screening.get("ok") is True
        and "watchlist" in layered_screening.get("result", {}).get("layers", {}),
        layered_screening,
    ))

    theme_chain_screening = _run(workspace, "equity-screening", "theme-chain-screening", {
        "theme_ids": ["ai-infrastructure"],
        "max_forward_pe": 20,
        "min_score": 55,
    })
    checks.append(_check(
        "equity-screening theme-chain-screening scores AI infrastructure template",
        theme_chain_screening.get("ok") is True
        and theme_chain_screening.get("decision_allowed") is False
        and theme_chain_screening.get("result", {}).get("template_only") is True
        and theme_chain_screening.get("result", {}).get("count", 0) >= 1
        and "watchlist" in theme_chain_screening.get("result", {}).get("layers", {}),
        theme_chain_screening,
    ))

    theme_signals = _run(workspace, "theme-cycle", "record-theme-signals", {
        "signals": [
            {
                "theme_hint": "AI Infrastructure",
                "node_hint": "HBM DRAM",
                "companies": ["SK Hynix", "Micron"],
                "catalyst_type": "earnings_call",
                "claim": "AI server demand is lifting HBM and DRAM pricing power.",
                "source_url": "https://example.com/hbm-note",
                "as_of": "2026-06-04",
                "confidence": 0.8,
            },
            {
                "theme_hint": "AI Infrastructure",
                "node_hint": "AI Server ODM",
                "companies": ["Quanta", "Wistron"],
                "catalyst_type": "supply_chain",
                "claim": "AI server buildout is increasing ODM order visibility.",
                "source_url": "https://example.com/odm-note",
                "as_of": "2026-06-04",
                "confidence": 0.7,
            },
        ]
    })
    checks.append(_check(
        "theme-cycle record-theme-signals writes evidence ledger",
        theme_signals.get("ok") is True
        and theme_signals.get("result", {}).get("signal_count") == 2
        and any("evidence-ledger.jsonl" in path for path in theme_signals.get("artifacts", [])),
        theme_signals,
    ))

    theme_registry = _run(workspace, "theme-cycle", "write-theme-registry", {})
    checks.append(_check(
        "theme-cycle write-theme-registry writes registry and chain map",
        theme_registry.get("ok") is True
        and theme_registry.get("result", {}).get("updated", 0) >= 1
        and any("theme-registry.json" in path for path in theme_registry.get("artifacts", []))
        and any("theme-chain-map.json" in path for path in theme_registry.get("artifacts", [])),
        theme_registry,
    ))

    coverage_plan = _run(workspace, "equity-screening", "plan-theme-coverage", {
        "theme_ids": ["ai-infrastructure"],
        "required_markets": ["US", "KR", "TW"],
    })
    checks.append(_check(
        "equity-screening plan-theme-coverage writes coverage plan",
        coverage_plan.get("ok") is True
        and any("coverage-plan.json" in path for path in coverage_plan.get("artifacts", []))
        and coverage_plan.get("result", {}).get("coverage_complete") is False,
        coverage_plan,
    ))

    theme_pool_missing = _run(workspace, "equity-screening", "refresh-theme-stock-pool", {
        "theme_ids": ["ai-infrastructure"],
        "min_score": 55,
    })
    checks.append(_check(
        "equity-screening refresh-theme-stock-pool fails closed without recorded candidates",
        theme_pool_missing.get("ok") is False
        and "theme_stock_pool_candidates_missing" in theme_pool_missing.get("errors", []),
        theme_pool_missing,
    ))

    record_candidates = _run(workspace, "equity-screening", "record-theme-candidates", {
        "theme_ids": ["ai-infrastructure"],
        "candidates": [
            {
                "symbol": "000660.KS",
                "name": "SK Hynix",
                "region": "KR",
                "chain_node_id": "hbm-dram",
                "theme_exposure": 95,
                "evidence_quality": 80,
                "confidence": 0.85,
                "verified_by": ["agent_native_research"],
            },
            {
                "symbol": "MU",
                "name": "Micron Technology",
                "region": "US",
                "chain_node_id": "hbm-dram",
                "theme_exposure": 90,
                "evidence_quality": 80,
                "confidence": 0.82,
                "verified_by": ["agent_native_research"],
            },
        ],
    })
    checks.append(_check(
        "equity-screening record-theme-candidates writes candidate ledger",
        record_candidates.get("ok") is True
        and record_candidates.get("result", {}).get("recorded_count") == 2
        and any("theme-candidates.jsonl" in path for path in record_candidates.get("artifacts", [])),
        record_candidates,
    ))

    theme_pool = _run(workspace, "equity-screening", "refresh-theme-stock-pool", {
        "theme_ids": ["ai-infrastructure"],
        "min_score": 55,
    })
    checks.append(_check(
        "equity-screening refresh-theme-stock-pool writes dynamic theme pool",
        theme_pool.get("ok") is True
        and theme_pool.get("result", {}).get("pool_count", 0) >= 1
        and any("theme-stock-pool.json" in path for path in theme_pool.get("artifacts", [])),
        theme_pool,
    ))

    theme_pool_audit = _run(workspace, "equity-screening", "theme-stock-pool-audit", {})
    checks.append(_check(
        "equity-screening theme-stock-pool-audit validates usable pool",
        theme_pool_audit.get("ok") is True
        and theme_pool_audit.get("result", {}).get("ok_to_use_pool") is True,
        theme_pool_audit,
    ))

    theme_research_batch = _run(workspace, "equity-screening", "batch-theme-research", {"limit": 3})
    checks.append(_check(
        "equity-screening batch-theme-research prepares deep-dive queue",
        theme_research_batch.get("ok") is True
        and theme_research_batch.get("result", {}).get("count", 0) >= 1,
        theme_research_batch,
    ))

    rating = _run(workspace, "equity-screening", "stock-rating", {
        "candidate": {"name": "贵州茅台", "theme": "消费", "net_yi": 5, "news_hits": 2, "research_hits": 1}
    })
    checks.append(_check(
        "equity-screening stock-rating rates one candidate",
        rating.get("ok") is True and rating.get("result", {}).get("grade") == "watchlist",
        rating,
    ))

    evidence_missing = _run(workspace, "equity-screening", "company-evidence-collect", {"name": "贵州茅台"})
    checks.append(_check(
        "equity-screening evidence collection fails closed without evidence source",
        evidence_missing.get("ok") is False and "evidence_source_missing" in evidence_missing.get("errors", []),
        evidence_missing,
    ))

    evidence_payload = _run(workspace, "equity-screening", "company-evidence-collect", {
        "name": "贵州茅台",
        "news": [{"title": "贵州茅台发布经营数据", "content": "贵州茅台收入增长稳健"}],
    })
    checks.append(_check(
        "equity-screening evidence collection uses payload evidence",
        evidence_payload.get("ok") is True
        and len(evidence_payload.get("result", {}).get("news", [])) == 1,
        evidence_payload,
    ))

    pool_update = _run(workspace, "equity-screening", "stock-pool-incremental-am", screening_payload)
    checks.append(_check(
        "equity-screening stock-pool update writes artifact",
        pool_update.get("ok") is True
        and (workspace / "memory" / "stock_pool" / "screening-pool.json").exists(),
        pool_update,
    ))

    (workspace / "memory" / "stock_pool" / "screening-pool.json").write_text("{bad json", encoding="utf-8")
    corrupt_pool = _run(workspace, "equity-screening", "stock-pool-maintenance", screening_payload)
    checks.append(_check(
        "equity-screening stock-pool maintenance fails closed on corrupt pool",
        corrupt_pool.get("ok") is False and "stock_pool_invalid_json" in corrupt_pool.get("errors", []),
        corrupt_pool,
    ))

    trade_missing = _run(workspace, "trade-planning", "short-term-analysis", {"themesurfer_status": "FULL"})
    checks.append(_check(
        "trade short-term-analysis fails closed without candidates or prewarm",
        trade_missing.get("ok") is False and "candidates_missing" in trade_missing.get("errors", []),
        trade_missing,
    ))

    theme_gate_missing = _run(workspace, "theme-cycle", "themesurfer-check", {})
    checks.append(_check(
        "theme-cycle themesurfer-check fails closed without market risk inputs",
        theme_gate_missing.get("ok") is False and "market_risk_inputs_missing" in theme_gate_missing.get("errors", []),
        theme_gate_missing,
    ))

    market_intel_missing = _run(workspace, "market-intel", "market-sentiment-index", {})
    checks.append(_check(
        "market-intel sentiment index fails closed without snapshot inputs",
        market_intel_missing.get("ok") is False and "market_sentiment_inputs_missing" in market_intel_missing.get("errors", []),
        market_intel_missing,
    ))

    macro_missing = _run(workspace, "macro-regime", "macro-regime-query", {})
    checks.append(_check(
        "macro-regime query fails closed without snapshot inputs",
        macro_missing.get("ok") is False and "macro_regime_inputs_missing" in macro_missing.get("errors", []),
        macro_missing,
    ))

    prewarm_dir = workspace / "memory" / "prewarm"
    prewarm_dir.mkdir(parents=True, exist_ok=True)
    (prewarm_dir / "nightly-prewarm-2026-06-04.json").write_text(
        json.dumps({
            "hhxg_snapshot": {
                "market": {
                    "sentiment_index": 28,
                    "limit_down": 12,
                    "fried": 35,
                    "promotion_rate": 0.2,
                },
                "hotmoney": {
                    "total_net_yi": 21.5,
                    "top_net_buy": [{"name": "贵州茅台", "code": "600519", "net_yi": 5.2}],
                },
                "hot_themes": [
                    {
                        "name": "AI算力",
                        "net_yi": 8,
                        "limitup_count": 3,
                        "stock_count": 18,
                        "top_stocks": [{"name": "中科曙光"}],
                    }
                ],
                "sectors": [
                    {
                        "label": "行业",
                        "strong": [{"name": "半导体", "leader": "中芯国际", "net_yi": 6, "limitup_count": 2}],
                        "weak": [{"name": "地产"}],
                    }
                ],
                "ai_summary": {"text": "市场情绪偏弱，算力方向活跃"},
            },
            "hhxg_news": [{"title": "A股收评：半导体走强", "content": "半导体板块走强"}],
            "tushare_news": [{"title": "中国PMI发布", "content": "中国PMI保持扩张"}],
            "tushare_major_news": [{"title": "Fed signals rate cut", "content": "global markets risk on"}],
            "tushare_policy": [{"title": "支持科技创新政策", "content": "支持半导体和AI", "issue_date": "20260604"}],
            "tushare_research_report": [
                {
                    "title": "半导体行业研究",
                    "org_name": "券商",
                    "author": "分析师",
                    "issue_date": "20260604",
                    "summary": "景气改善",
                    "ts_code": "000001.SZ",
                }
            ],
            "tushare_eco_cal": [
                {"country": "US", "event": "CPI", "report_date": "2026-06-12", "forecast": "2.8", "previous": "3.0"}
            ],
            "hhxg_calendar": {"trading_days": ["2026-06-05"]},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    macro_regime = _run(workspace, "macro-regime", "macro-regime-query", {})
    checks.append(_check(
        "macro-regime query returns risk-off bundle from snapshot",
        macro_regime.get("ok") is True
        and macro_regime.get("result", {}).get("risk", {}).get("risk_mode") == "risk_off"
        and macro_regime.get("decision_allowed") is False,
        macro_regime,
    ))

    concept_heat = _run(workspace, "macro-regime", "concept-heat", {})
    checks.append(_check(
        "macro-regime concept-heat ranks hot themes",
        concept_heat.get("ok") is True and concept_heat.get("result", {}).get("heat", [{}])[0].get("name") == "AI算力",
        concept_heat,
    ))

    macro_alert = _run(workspace, "macro-regime", "macro-alert-check", {})
    checks.append(_check(
        "macro-regime alert check emits high risk alerts",
        macro_alert.get("ok") is True
        and macro_alert.get("result", {}).get("risk", {}).get("risk_level") == "red"
        and macro_alert.get("result", {}).get("alerts"),
        macro_alert,
    ))

    market_sentiment = _run(workspace, "market-intel", "market-sentiment-index", {})
    checks.append(_check(
        "market-intel sentiment index reads snapshot inputs",
        market_sentiment.get("ok") is True
        and market_sentiment.get("result", {}).get("sentiment_index") == 28
        and market_sentiment.get("decision_allowed") is False,
        market_sentiment,
    ))

    daily_news = _run(workspace, "market-intel", "daily-news-scan", {})
    checks.append(_check(
        "market-intel daily news scan reads prewarm news",
        daily_news.get("ok") is True and daily_news.get("result", {}).get("count", 0) >= 2,
        daily_news,
    ))

    policy = _run(workspace, "market-intel", "policy-analysis", {})
    checks.append(_check(
        "market-intel policy-analysis reads policy feed",
        policy.get("ok") is True and len(policy.get("result", {}).get("policies", [])) == 1,
        policy,
    ))

    reports = _run(workspace, "market-intel", "research-reports", {})
    checks.append(_check(
        "market-intel research-reports reads report feed",
        reports.get("ok") is True and len(reports.get("result", {}).get("research_reports", [])) == 1,
        reports,
    ))

    theme_gate = _run(workspace, "theme-cycle", "themesurfer-check", {})
    checks.append(_check(
        "theme-cycle themesurfer-check returns lockout under red risk",
        theme_gate.get("ok") is True
        and theme_gate.get("result", {}).get("status") == "LOCKOUT"
        and theme_gate.get("decision_allowed") is False,
        theme_gate,
    ))

    theme_event = _run(workspace, "theme-cycle", "event-analysis", {
        "events": [{"title": "AI算力政策催化，通胀风险升温"}]
    })
    checks.append(_check(
        "theme-cycle event-analysis maps event to active theme",
        theme_event.get("ok") is True
        and "AI算力" in theme_event.get("result", {}).get("events", [{}])[0].get("matched_themes", []),
        theme_event,
    ))

    rebalance = _run(workspace, "theme-cycle", "rebalance-check", {})
    checks.append(_check(
        "theme-cycle rebalance-check returns paper-only lockout actions",
        rebalance.get("ok") is True
        and rebalance.get("result", {}).get("actions", [{}])[0].get("paper_only") is True,
        rebalance,
    ))

    (workspace / "memory" / "themes.json").write_text(
        json.dumps({
            "themes": {
                "A股:ultra_short:AI算力": {
                    "name": "AI算力",
                    "horizon": "ultra_short",
                    "asset_class": "A股",
                    "status": "active",
                    "lifecycle": "accelerating",
                    "history": [{"date": "2026-06-04", "changes": {"created": True}}],
                }
            }
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    theme_tracker = _run(workspace, "theme-cycle", "theme-tracker", {})
    checks.append(_check(
        "theme-cycle theme-tracker reads local theme store",
        theme_tracker.get("ok") is True and theme_tracker.get("result", {}).get("count") == 1,
        theme_tracker,
    ))

    weekly_stats = _run(workspace, "theme-cycle", "themesurfer-weekly-stats", {})
    checks.append(_check(
        "theme-cycle weekly stats summarizes local theme store",
        weekly_stats.get("ok") is True and weekly_stats.get("result", {}).get("theme_count") == 1,
        weekly_stats,
    ))

    trade_payload = {
        "themesurfer_status": "FULL",
        "risk_level": "green",
        "themes": [{"name": "消费", "strength": 0.8}],
        "candidates": [
            {"name": "贵州茅台", "theme": "消费", "net_yi": 5, "limitup": 1, "news_hits": 2, "research_hits": 1}
        ],
        "technical": {"price": 1500, "ma20": 1450, "ma60": 1400, "support": 1380, "resistance": 1680, "rsi": 62},
    }

    short_term = _run(workspace, "trade-planning", "short-term-analysis", trade_payload)
    checks.append(_check(
        "trade short-term-analysis returns paper-only candidates",
        short_term.get("ok") is True
        and short_term.get("decision_allowed") is False
        and short_term.get("requires_human_confirmation") is True
        and short_term.get("result", {}).get("candidates"),
        short_term,
    ))

    full_plan = _run(workspace, "trade-planning", "full-investment-plan", trade_payload)
    checks.append(_check(
        "trade full-investment-plan composes complete paper plan",
        full_plan.get("ok") is True
        and full_plan.get("result", {}).get("plan_complete") is True
        and full_plan.get("decision_allowed") is False,
        full_plan,
    ))

    advice_missing = _run(workspace, "advice-lifecycle", "advice-history", {})
    checks.append(_check(
        "advice-lifecycle history fails closed without ledger",
        advice_missing.get("ok") is False
        and "advice_ledger_missing" in advice_missing.get("errors", [])
        and advice_missing.get("decision_allowed") is False,
        advice_missing,
    ))

    advice_create = _run(workspace, "advice-lifecycle", "investment-advice", {
        "recommendations": [
            {
                "id": "adv-600519",
                "code": "600519",
                "name": "贵州茅台",
                "theme": "消费",
                "thesis": "品牌壁垒强，仅作研究跟踪",
                "entry_price": 1500,
                "valid_until": "2020-01-01",
                "invalidation": "基本面恶化",
            }
        ]
    })
    checks.append(_check(
        "advice-lifecycle investment-advice records explicit paper advice",
        advice_create.get("ok") is True
        and advice_create.get("requires_human_confirmation") is True
        and advice_create.get("max_action_level") == "research_only"
        and (workspace / "memory" / "advice" / "advice-ledger.json").exists(),
        advice_create,
    ))

    advice_price = _run(workspace, "advice-lifecycle", "advice-update-prices", {
        "prices": {"adv-600519": 1650}
    })
    checks.append(_check(
        "advice-lifecycle advice-update-prices updates explicit price",
        advice_price.get("ok") is True
        and advice_price.get("result", {}).get("updated_count") == 1,
        advice_price,
    ))

    advice_stats = _run(workspace, "advice-lifecycle", "advice-track-stats", {})
    checks.append(_check(
        "advice-lifecycle advice-track-stats computes paper return",
        advice_stats.get("ok") is True
        and advice_stats.get("result", {}).get("avg_return_pct") == 10.0
        and advice_stats.get("decision_allowed") is False,
        advice_stats,
    ))

    advice_expired = _run(workspace, "advice-lifecycle", "advice-expire-check", {})
    checks.append(_check(
        "advice-lifecycle expire check is review-only by default",
        advice_expired.get("ok") is True
        and advice_expired.get("result", {}).get("expired_count") == 1
        and advice_expired.get("result", {}).get("applied") is False,
        advice_expired,
    ))

    automation_dry = _run(workspace, "execution-automation", "nightly-prewarm", {"dry_run": True})
    checks.append(_check(
        "execution-automation nightly-prewarm supports dry-run without network",
        automation_dry.get("ok") is True
        and automation_dry.get("result", {}).get("dry_run") is True
        and automation_dry.get("decision_allowed") is False,
        automation_dry,
    ))

    empty_auto_workspace = workspace / "empty-automation"
    empty_auto_workspace.mkdir(parents=True, exist_ok=True)
    prewarm_missing = _run(empty_auto_workspace, "execution-automation", "prewarm-status", {})
    checks.append(_check(
        "execution-automation prewarm-status fails closed without artifact",
        prewarm_missing.get("ok") is False
        and any("prewarm_" in e for e in prewarm_missing.get("errors", [])),
        prewarm_missing,
    ))

    automation_status = _run(workspace, "execution-automation", "prewarm-status", {"max_age_minutes": 720})
    checks.append(_check(
        "execution-automation prewarm-status validates latest artifact",
        automation_status.get("ok") is True
        and automation_status.get("result", {}).get("artifact"),
        automation_status,
    ))

    heartbeat = _run(workspace, "execution-automation", "market-heartbeat", {"max_age_minutes": 720})
    checks.append(_check(
        "execution-automation market-heartbeat reads prewarm evidence",
        heartbeat.get("ok") is True
        and heartbeat.get("result", {}).get("heartbeat_status") in {"ALERT", "HEARTBEAT_OK"},
        heartbeat,
    ))

    push_dry = _run(workspace, "execution-automation", "nightly-push", {
        "text": "research-only nightly report",
        "dry_run": True,
    })
    checks.append(_check(
        "execution-automation push dry-run does not send externally",
        push_dry.get("ok") is True
        and push_dry.get("result", {}).get("sent") is False,
        push_dry,
    ))

    push_unconfirmed = _run(workspace, "execution-automation", "nightly-push", {
        "text": "research-only nightly report"
    })
    checks.append(_check(
        "execution-automation push fails closed without explicit confirmation",
        push_unconfirmed.get("ok") is False
        and "external_send_requires_confirm" in push_unconfirmed.get("errors", []),
        push_unconfirmed,
    ))

    quant_series = {
        "price_series": [
            {"date": "d1", "close": 10},
            {"date": "d2", "close": 11},
            {"date": "d3", "close": 12},
            {"date": "d4", "close": 11},
            {"date": "d5", "close": 13},
            {"date": "d6", "close": 14},
        ],
        "periods_per_year": 6,
    }
    quant_missing = _run(workspace, "quant-validation", "strategy-backtest", {})
    checks.append(_check(
        "quant-validation strategy-backtest fails closed without history",
        quant_missing.get("ok") is False
        and "historical_series_required" in quant_missing.get("errors", []),
        quant_missing,
    ))

    quant_backtest = _run(workspace, "quant-validation", "strategy-backtest", {
        **quant_series,
        "strategy": {"type": "buy_and_hold"},
    })
    checks.append(_check(
        "quant-validation strategy-backtest computes metrics from explicit series",
        quant_backtest.get("ok") is True
        and quant_backtest.get("decision_allowed") is False
        and quant_backtest.get("result", {}).get("metrics", {}).get("period_count") == 5,
        quant_backtest,
    ))

    quant_batch = _run(workspace, "quant-validation", "batch-backtest", {
        **quant_series,
        "strategies": [
            {"id": "hold", "type": "buy_and_hold"},
            {"id": "cash", "type": "cash"},
        ],
    })
    checks.append(_check(
        "quant-validation batch-backtest ranks valid strategies",
        quant_batch.get("ok") is True
        and quant_batch.get("result", {}).get("valid_count") == 2
        and quant_batch.get("result", {}).get("ranking", [{}])[0].get("strategy_id") == "hold",
        quant_batch,
    ))

    quant_grid = _run(workspace, "quant-validation", "grid-search-advisor", {
        **quant_series,
        "grid": {"short_window": [1, 2], "long_window": [3, 4]},
    })
    checks.append(_check(
        "quant-validation grid-search-advisor evaluates bounded grid",
        quant_grid.get("ok") is True
        and quant_grid.get("result", {}).get("evaluated") == 4
        and quant_grid.get("result", {}).get("recommendation", {}).get("paper_only") is True,
        quant_grid,
    ))

    search_missing = _run(workspace, "information-retrieval", "research-search", {})
    checks.append(_check(
        "information-retrieval research-search fails closed without query",
        search_missing.get("ok") is False
        and "query_or_queries_required" in _delegated_errors(search_missing)
        and search_missing.get("decision_allowed") is False,
        search_missing,
    ))

    refs = _run(workspace, "information-retrieval", "research-search", {
        "query": "OpenAI python issue 1",
        "extract_refs": True,
        "extract_refs_urls": ["https://github.com/openai/openai-python/issues/1"],
    })
    checks.append(_check(
        "information-retrieval research-search returns structured delegated envelope",
        refs.get("ok") is True
        and refs.get("decision_allowed") is False
        and isinstance(refs.get("result", {}).get("delegated"), dict),
        refs,
    ))

    empty_weekly_workspace = workspace / "empty-weekly-stock-pool"
    empty_weekly_workspace.mkdir(parents=True, exist_ok=True)
    weekly_missing = _run(empty_weekly_workspace, "weekly-stock-pool", "weekly-stock-pool", {})
    checks.append(_check(
        "weekly-stock-pool fails closed without weekly artifacts",
        weekly_missing.get("ok") is False
        and "weekly_pipeline_runs_missing" in weekly_missing.get("errors", [])
        and "weekly_pipeline_context_missing" in weekly_missing.get("errors", [])
        and "prewarm_snapshot_missing" in weekly_missing.get("errors", [])
        and weekly_missing.get("result", {}).get("candidates") is None
        and weekly_missing.get("decision_allowed") is False,
        weekly_missing,
    ))

    weekly_run_dir = workspace / "memory" / "pipeline_runs"
    weekly_context_dir = workspace / "memory" / "pipeline_context"
    weekly_run_dir.mkdir(parents=True, exist_ok=True)
    weekly_context_dir.mkdir(parents=True, exist_ok=True)
    weekly_candidate = {
        "name": "贵州茅台",
        "code": "600519",
        "theme": "消费",
        "score": 82,
        "source": "smoke-weekly-pipeline",
    }
    (weekly_run_dir / "weekly-2026-06-04.json").write_text(
        json.dumps({
            "result": {
                "results": [
                    {
                        "package": "equity-screening",
                        "command": "stock-screening",
                        "output": {"candidates": [weekly_candidate]},
                    },
                    {
                        "package": "quality-gate",
                        "command": "backtest-loop",
                        "output": {"ok": True},
                    },
                    {
                        "package": "theme-cycle",
                        "command": "global-medium-long-strategy",
                        "output": {"ok": True},
                    },
                    {
                        "package": "macro-regime",
                        "command": "global-macro-analysis",
                        "output": {"ok": True},
                    },
                ]
            }
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (weekly_context_dir / "weekly-context-2026-06-04.json").write_text(
        json.dumps({
            "results": [
                {
                    "package": "equity-research",
                    "command": "stock-analysis",
                    "output": {"candidates": [{"name": "宁德时代", "code": "300750", "theme": "新能源", "score": 76}]},
                }
            ]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    weekly_pool = _run(workspace, "weekly-stock-pool", "weekly-stock-pool", {"min_candidates": 2})
    checks.append(_check(
        "weekly-stock-pool consolidates verified weekly artifacts",
        weekly_pool.get("ok") is True
        and weekly_pool.get("decision_allowed") is False
        and weekly_pool.get("requires_human_confirmation") is True
        and weekly_pool.get("result", {}).get("candidate_count") == 2
        and "backtest-loop" in weekly_pool.get("result", {}).get("filters", [])
        and any("memory/stock_pool/weekly-stock-pool-" in path for path in weekly_pool.get("artifacts", [])),
        weekly_pool,
    ))

    failed = [check for check in checks if not check["ok"]]
    return {
        "ok": not failed,
        "workspace": str(workspace),
        "checks": checks,
        "failed": failed,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Portfolio / Position / Research / Equity / Screening / Macro / Theme / Intel / Trade / Advice / Automation / Quant / Search / Weekly Pool Smoke Results",
        "",
        f"- OK: {result['ok']}",
        f"- Workspace: `{result['workspace']}`",
        "",
        "| Check | OK |",
        "|---|---:|",
    ]
    for check in result["checks"]:
        lines.append(f"| {check['name']} | {check['ok']} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("/tmp/aegis-alpha-smoke"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = run_smoke(args.workspace)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "smoke-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.output_dir / "smoke-results.md")
    print(json.dumps({"ok": result["ok"], "failed": len(result["failed"])}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
