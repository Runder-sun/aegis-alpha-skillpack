#!/usr/bin/env python3
"""End-to-end research-only investment closed-loop smoke.

This smoke uses explicit local fixtures and avoids provider/network calls. It
verifies the public surface can compose a complete research loop without
allowing executable investment decisions.
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
    return {"name": name, "ok": bool(condition), "detail": detail}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_workspace(workspace: Path) -> None:
    prewarm = {
        "hhxg_snapshot": {
            "market": {
                "sentiment_index": 55,
                "limit_down": 4,
                "fried": 12,
                "promotion_rate": 0.42,
            },
            "hotmoney": {
                "total_net_yi": 16.5,
                "top_net_buy": [{"name": "中科曙光", "code": "603019", "net_yi": 4.8}],
            },
            "hot_themes": [
                {
                    "name": "AI算力",
                    "net_yi": 9,
                    "limitup_count": 4,
                    "stock_count": 22,
                    "top_stocks": [{"name": "中科曙光", "code": "603019"}],
                }
            ],
            "sectors": [
                {"label": "行业", "strong": [{"name": "半导体", "leader": "中芯国际", "net_yi": 6}], "weak": [{"name": "地产"}]}
            ],
            "ai_summary": {"text": "市场情绪修复，AI算力和半导体方向活跃"},
        },
        "hhxg_news": [{"title": "AI算力政策催化", "content": "算力基础设施政策继续落地"}],
        "tushare_news": [{"title": "科技产业政策发布", "content": "支持AI和半导体"}],
        "tushare_policy": [{"title": "支持科技创新政策", "content": "支持半导体和AI", "issue_date": "20260604"}],
        "tushare_research_report": [
            {
                "title": "AI算力行业深度",
                "org_name": "券商",
                "author": "分析师",
                "issue_date": "20260604",
                "summary": "需求维持高景气",
                "ts_code": "603019.SH",
            }
        ],
        "tushare_eco_cal": [{"country": "CN", "event": "PMI", "report_date": "2026-06-10"}],
        "hhxg_calendar": {"trading_days": ["2026-06-05"]},
    }
    _write_json(workspace / "memory" / "prewarm" / "nightly-prewarm-2026-06-04.json", prewarm)
    _write_json(
        workspace / "memory" / "themes.json",
        {
            "themes": {
                "A股:short:AI算力": {
                    "name": "AI算力",
                    "asset_class": "A股",
                    "horizon": "short",
                    "status": "active",
                    "lifecycle": "accelerating",
                    "global_link": "AI基础设施",
                    "score": 82,
                    "updated_at": "2026-06-04",
                }
            }
        },
    )
    _run(
        workspace,
        "portfolio-ops",
        "portfolio-add",
        {"code": "603019", "name": "中科曙光", "quantity": 100, "price": 45},
    )


def run_smoke(workspace: Path) -> dict[str, Any]:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    _seed_workspace(workspace)

    checks: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}

    regime = _run(workspace, "macro-regime", "macro-regime-query", {})
    checks.append(_check(
        "market snapshot produces regime judgment",
        regime.get("ok") is True
        and regime.get("decision_allowed") is False
        and isinstance(regime.get("result", {}).get("risk"), dict),
        regime,
    ))

    theme = _run(workspace, "theme-cycle", "themesurfer-check", {})
    checks.append(_check(
        "regime feeds theme gate",
        theme.get("ok") is True
        and theme.get("decision_allowed") is False
        and theme.get("result", {}).get("status") in {"FULL", "PARTIAL", "LOCKOUT"},
        theme,
    ))

    screening_payload = {
        "candidates": [
            {"name": "中科曙光", "code": "603019", "theme": "AI算力", "net_yi": 8.5, "news_hits": 4, "research_hits": 2},
            {"name": "中芯国际", "code": "688981", "theme": "半导体", "net_yi": 6.2, "news_hits": 3, "research_hits": 2},
        ],
        "min_score": 50,
    }
    screening = _run(workspace, "equity-screening", "stock-screening", screening_payload)
    candidates = screening.get("result", {}).get("candidates", [])
    checks.append(_check(
        "theme evidence produces candidate pool",
        screening.get("ok") is True
        and screening.get("decision_allowed") is False
        and len(candidates) >= 1,
        screening,
    ))

    research_payload = {
        "code": "603019",
        "name": "中科曙光",
        "metrics": {
            "roe": 0.16,
            "net_margin": 0.12,
            "revenue_growth": 0.18,
            "net_profit_growth": 0.22,
            "debt_to_asset": 0.34,
            "operating_cashflow": 80,
            "net_profit": 70,
            "price": 45,
            "eps": 1.8,
            "industry_pe": 35,
            "dividend_yield": 0.01,
        },
        "context": {
            "summary": "AI算力服务器龙头之一，受益于算力基础设施投入。",
            "thesis": "订单景气与国产替代形成中期支撑。",
            "risks": ["估值波动", "行业竞争", "订单兑现不及预期"],
        },
        "news": [{"title": "AI算力政策催化", "content": "算力基础设施政策继续落地"}],
        "narrative_score": 72,
    }
    research = _run(workspace, "equity-research", "stock-analysis", research_payload)
    checks.append(_check(
        "candidate has fundamental narrative valuation research",
        research.get("ok") is True
        and research.get("decision_allowed") is False
        and research.get("result", {}).get("research_complete") is True,
        research,
    ))

    trade_payload = {
        "themesurfer_status": theme.get("result", {}).get("status", "PARTIAL"),
        "risk_level": regime.get("result", {}).get("risk", {}).get("risk_level", "yellow"),
        "themes": [{"name": "AI算力", "strength": 0.82}],
        "candidates": candidates[:1],
        "technical": {"price": 45, "ma20": 42, "ma60": 39, "support": 40, "resistance": 52, "rsi": 58},
    }
    trade = _run(workspace, "trade-planning", "full-investment-plan", trade_payload)
    checks.append(_check(
        "research composes paper trade plan with invalidation boundaries",
        trade.get("ok") is True
        and trade.get("decision_allowed") is False
        and trade.get("requires_human_confirmation") is True
        and trade.get("result", {}).get("plan_complete") is True,
        trade,
    ))

    risk = _run(workspace, "portfolio-ops", "portfolio-risk-check", {"max_single_position_pct": 0.4})
    checks.append(_check(
        "portfolio risk check enters loop",
        risk.get("ok") is True
        and risk.get("decision_allowed") is False,
        risk,
    ))

    advice = _run(
        workspace,
        "advice-lifecycle",
        "investment-advice",
        {
            "recommendations": [
                {
                    "id": "closed-loop-603019",
                    "code": "603019",
                    "name": "中科曙光",
                    "theme": "AI算力",
                    "thesis": "仅作研究跟踪，等待人工确认和风险预算复核。",
                    "entry_price": 45,
                    "valid_until": "2026-07-04",
                    "invalidation": "AI算力景气或订单验证不及预期",
                }
            ]
        },
    )
    checks.append(_check(
        "paper advice is recorded with lifecycle controls",
        advice.get("ok") is True
        and advice.get("decision_allowed") is False
        and advice.get("requires_human_confirmation") is True
        and (workspace / "memory" / "advice" / "advice-ledger.json").exists(),
        advice,
    ))

    report_dir = workspace / "memory" / "reports"
    report_path = report_dir / "nightly-report-20260604-210000.md"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Research-only closed loop\n\n"
        "- Regime, theme, screening, research, trade plan, risk, and advice lifecycle checked.\n"
        "- No executable decision allowed.\n",
        encoding="utf-8",
    )
    _write_json(
        workspace / "memory" / "pipeline_runs" / "nightly-20260604-205900.json",
        {
            "results": [
                {"package": "macro-regime", "command": "macro-regime-query", "output": regime},
                {"package": "theme-cycle", "command": "themesurfer-check", "output": theme},
                {"package": "equity-screening", "command": "stock-screening", "output": screening},
                {"package": "equity-research", "command": "stock-analysis", "output": research},
                {"package": "trade-planning", "command": "full-investment-plan", "output": trade},
                {"package": "advice-lifecycle", "command": "investment-advice", "output": advice},
            ]
        },
    )
    _write_json(
        workspace / "memory" / "pipeline_context" / "nightly-context-20260604-205900.json",
        [
            {"package": "macro-regime", "command": "macro-regime-query", "output": regime},
            {"package": "equity-screening", "command": "stock-screening", "output": screening},
        ],
    )
    capture = _run(workspace, "report-evolution", "capture-report-evidence", {"pipeline_id": "nightly", "snapshot_version": 1})
    align = _run(workspace, "report-evolution", "align-report-outcome", {"pipeline_id": "nightly"})
    checks.append(_check(
        "report evidence capture and outcome alignment create review artifacts",
        capture.get("result", {}).get("ok") is True
        and align.get("result", {}).get("ok") is True,
        {"capture": capture, "align": align},
    ))

    artifacts = {
        "advice_ledger": str(workspace / "memory" / "advice" / "advice-ledger.json"),
        "report": str(report_path),
        "capture": capture.get("result", {}).get("saved_to"),
        "alignment": align.get("result", {}).get("saved_to"),
    }

    failed = [check for check in checks if not check["ok"]]
    return {
        "ok": not failed,
        "workspace": str(workspace),
        "artifacts": artifacts,
        "checks": checks,
        "failed": failed,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Investment Closed-Loop Smoke Results",
        "",
        f"- OK: {result['ok']}",
        f"- Workspace: `{result['workspace']}`",
        "",
        "## Artifacts",
        "",
    ]
    for name, value in result.get("artifacts", {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Checks", "", "| Check | OK |", "|---|---:|"])
    for check in result["checks"]:
        lines.append(f"| {check['name']} | {check['ok']} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("/tmp/aegis-alpha-closed-loop-smoke"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = run_smoke(args.workspace)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "closed-loop-smoke-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.output_dir / "closed-loop-smoke-results.md")
    print(json.dumps({"ok": result["ok"], "failed": len(result["failed"])}, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
