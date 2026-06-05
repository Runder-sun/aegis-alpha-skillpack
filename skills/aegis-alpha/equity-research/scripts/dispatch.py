from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "equity-research"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE", "")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_prewarm() -> tuple[dict[str, Any], list[str]]:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return {"_prewarm_missing": True}, []
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {"_prewarm_missing": True}, []
    try:
        return json.loads(files[0].read_text(encoding="utf-8")), [str(files[0])]
    except Exception:
        return {"_prewarm_invalid": True}, [str(files[0])]


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
            "policy": "research freshness is inherited from supplied metrics, evidence, and latest prewarm artifact when used",
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
        "note": "Equity research evidence is incomplete; do not infer an investment conclusion.",
        "missing_critical_inputs": errors,
    }
    return output


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics")
    financials = payload.get("financials")
    merged: dict[str, Any] = {}
    if isinstance(metrics, dict):
        merged.update(metrics)
    if isinstance(financials, dict):
        merged.update(financials)
    for key, value in payload.items():
        if key not in {"metrics", "financials", "news", "reports", "context"}:
            merged.setdefault(key, value)
    return merged


def _grade(value: float, bands: list[tuple[float, str]], default: str) -> str:
    for threshold, label in bands:
        if value >= threshold:
            return label
    return default


def _code_or_name(payload: dict[str, Any]) -> tuple[str, str, str]:
    code = str(payload.get("code") or payload.get("symbol") or payload.get("ts_code") or "").strip()
    name = str(payload.get("name") or payload.get("company") or "").strip()
    query = str(payload.get("query") or code or name or "").strip()
    return code, name, query


def _iter_prewarm_items(prewarm: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    for source in (prewarm, market_data):
        for key in keys:
            value = source.get(key)
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
    return items


def _matches(item: dict[str, Any], code: str, name: str, query: str) -> bool:
    haystack = " ".join(str(item.get(k) or "") for k in (
        "code", "ts_code", "symbol", "name", "title", "summary", "content", "org", "author"
    ))
    needles = [n for n in (code, name, query) if n]
    if not needles:
        return True
    return any(needle in haystack for needle in needles)


def _stock_news(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    code, name, query = _code_or_name(payload)
    explicit_news = payload.get("news") if isinstance(payload.get("news"), list) else []
    prewarm_news = _iter_prewarm_items(prewarm, ["tushare_news", "tushare_major_news", "stock_news", "news"])
    news = [item for item in [*explicit_news, *prewarm_news] if isinstance(item, dict) and _matches(item, code, name, query)]
    if not news and not (code or name or query):
        return _fail(command, payload, ["code_name_or_query_required"])
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.news"] if explicit_news else [])
    output["warnings"] = [] if news else ["no_matching_news_found"]
    output["result"] = {
        "code": code,
        "name": name,
        "query": query,
        "items": news[:20],
        "count": min(len(news), 20),
        "total_found": len(news),
    }
    return output


def _financial_diagnosis(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    m = _metrics(payload)
    required_any = ["roe", "net_margin", "revenue_growth", "net_profit_growth", "debt_to_asset", "operating_cashflow", "net_profit"]
    present = {key: _float(m.get(key)) for key in required_any if _float(m.get(key)) is not None}
    if len(present) < 3:
        return _fail(command, payload, ["insufficient_financial_metrics"], ["provide at least 3 core metrics"])

    flags: list[dict[str, Any]] = []
    strengths: list[str] = []
    risks: list[str] = []

    roe = _float(m.get("roe"))
    if roe is not None:
        (strengths if roe >= 0.15 else risks).append("roe_strong" if roe >= 0.15 else "roe_below_institutional_bar")
        if roe < 0.08:
            flags.append({"metric": "roe", "risk": "low_profitability", "value": roe})

    net_margin = _float(m.get("net_margin"))
    if net_margin is not None and net_margin < 0.05:
        flags.append({"metric": "net_margin", "risk": "thin_margin", "value": net_margin})
        risks.append("thin_net_margin")
    elif net_margin is not None:
        strengths.append("healthy_net_margin")

    revenue_growth = _float(m.get("revenue_growth"))
    net_profit_growth = _float(m.get("net_profit_growth"))
    if revenue_growth is not None and revenue_growth > 0.1:
        strengths.append("revenue_growth_positive")
    if net_profit_growth is not None and net_profit_growth < 0:
        flags.append({"metric": "net_profit_growth", "risk": "profit_decline", "value": net_profit_growth})
        risks.append("profit_decline")

    debt_to_asset = _float(m.get("debt_to_asset"))
    if debt_to_asset is not None and debt_to_asset > 0.7:
        flags.append({"metric": "debt_to_asset", "risk": "high_leverage", "value": debt_to_asset})
        risks.append("high_leverage")

    ocf = _float(m.get("operating_cashflow"))
    net_profit = _float(m.get("net_profit"))
    cashflow_quality = None
    if ocf is not None and net_profit not in (None, 0):
        cashflow_quality = ocf / net_profit
        if cashflow_quality < 0.8:
            flags.append({"metric": "cashflow_quality", "risk": "profit_cashflow_mismatch", "value": cashflow_quality})
            risks.append("profit_cashflow_mismatch")
        else:
            strengths.append("cashflow_supports_profit")

    score = 50 + 8 * len(set(strengths)) - 10 * len(flags)
    score = max(0, min(100, score))
    output = _base_output(command, payload)
    output["result"] = {
        "metrics_used": sorted(present.keys()),
        "cashflow_quality": cashflow_quality,
        "strengths": sorted(set(strengths)),
        "risks": sorted(set(risks)),
        "flags": flags,
        "financial_quality_score": score,
        "grade": _grade(score, [(75, "strong"), (55, "mixed")], "weak"),
    }
    return output


def _valuation_check(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    m = _metrics(payload)
    price = _float(m.get("price"))
    eps = _float(m.get("eps"))
    pe = _float(m.get("pe"))
    if pe is None and price is not None and eps not in (None, 0):
        pe = price / eps
    pb = _float(m.get("pb"))
    industry_pe = _float(m.get("industry_pe"))
    growth = _float(m.get("earnings_growth") or m.get("net_profit_growth") or m.get("growth_rate"))
    dividend_yield = _float(m.get("dividend_yield"))
    fcf_yield = _float(m.get("fcf_yield"))

    if pe is None and pb is None and dividend_yield is None and fcf_yield is None:
        return _fail(command, payload, ["valuation_metrics_missing"], ["provide pe/pb/dividend_yield/fcf_yield or price+eps"])

    valuation_flags: list[dict[str, Any]] = []
    positives: list[str] = []
    peg = None
    if pe is not None and industry_pe is not None:
        relative = pe / industry_pe if industry_pe else None
        if relative is not None and relative > 1.3:
            valuation_flags.append({"metric": "pe_vs_industry", "risk": "valuation_premium", "value": relative})
        elif relative is not None and relative < 0.8:
            positives.append("pe_discount_to_industry")
    if pe is not None and growth not in (None, 0):
        peg = pe / (growth * 100 if growth < 1 else growth)
        if peg > 2:
            valuation_flags.append({"metric": "peg", "risk": "growth_not_covering_multiple", "value": peg})
        elif peg < 1:
            positives.append("growth_supports_multiple")
    if dividend_yield is not None and dividend_yield >= 0.03:
        positives.append("shareholder_return_support")
    if fcf_yield is not None and fcf_yield >= 0.04:
        positives.append("free_cash_flow_yield_support")

    score = 60 + 8 * len(positives) - 12 * len(valuation_flags)
    score = max(0, min(100, score))
    output = _base_output(command, payload)
    output["result"] = {
        "pe": pe,
        "pb": pb,
        "peg": peg,
        "industry_pe": industry_pe,
        "dividend_yield": dividend_yield,
        "fcf_yield": fcf_yield,
        "positives": positives,
        "valuation_flags": valuation_flags,
        "valuation_score": score,
        "grade": _grade(score, [(75, "attractive"), (55, "fair")], "expensive_or_unproven"),
    }
    return output


def _narrative_analysis(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else prewarm.get("hhxg_snapshot", {})
    summary = snapshot.get("ai_summary") if isinstance(snapshot, dict) else None
    themes = context.get("themes") or (snapshot.get("themes") if isinstance(snapshot, dict) else None)
    if not context and not snapshot:
        return _fail(command, payload, ["narrative_context_missing"], ["provide context or run nightly prewarm"])
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.context"] if context else [])
    output["result"] = {
        "summary": summary or context.get("summary"),
        "themes": themes or [],
        "thesis": context.get("thesis"),
        "risks": context.get("risks", []),
        "source": "payload.context + prewarm.hhxg_snapshot",
    }
    return output


def _fundamental_analysis(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    diagnosis = _financial_diagnosis("financial-diagnosis", payload)
    if not diagnosis["ok"]:
        return diagnosis
    result = diagnosis["result"]
    output = _base_output(command, payload)
    output["warnings"] = ["fundamental_analysis_requires_industry_context_for_institutional_depth"]
    output["result"] = {
        "quality": result,
        "business_model": payload.get("business_model"),
        "competitive_position": payload.get("competitive_position"),
        "key_questions": [
            "Can growth persist without margin erosion?",
            "Is cash flow quality consistent across cycles?",
            "Does balance-sheet risk constrain strategy?",
        ],
    }
    return output


def _stock_score(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    financial = _financial_diagnosis("financial-diagnosis", payload)
    valuation = _valuation_check("valuation-check", payload)
    components: dict[str, float] = {}
    warnings: list[str] = []
    if financial["ok"]:
        components["financial_quality"] = financial["result"]["financial_quality_score"]
    else:
        warnings.append("financial_quality_missing")
    if valuation["ok"]:
        components["valuation"] = valuation["result"]["valuation_score"]
    else:
        warnings.append("valuation_missing")
    narrative_score = _float(payload.get("narrative_score"))
    if narrative_score is not None:
        components["narrative"] = max(0, min(100, narrative_score))
    if not components:
        return _fail(command, payload, ["score_inputs_missing"], warnings)

    weights = {"financial_quality": 0.45, "valuation": 0.35, "narrative": 0.2}
    used_weight = sum(weights[key] for key in components)
    score = sum(components[key] * weights[key] for key in components) / used_weight
    risk_penalty = 0
    if financial["ok"]:
        risk_penalty += 5 * len(financial["result"].get("flags", []))
    score = max(0, min(100, score - risk_penalty))
    output = _base_output(command, payload)
    output["sources"] = sources
    output["warnings"] = warnings
    output["result"] = {
        "score": round(score, 2),
        "components": components,
        "weights": {key: weights[key] for key in components},
        "risk_penalty": risk_penalty,
        "grade": _grade(score, [(80, "research_candidate"), (60, "watchlist")], "reject_or_insufficient"),
    }
    return output


def _stock_analysis(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    sections = {
        "news": _stock_news("stock-news", payload, prewarm, sources),
        "narrative": _narrative_analysis("narrative-analysis", payload, prewarm, sources),
        "fundamental": _fundamental_analysis("fundamental-analysis", payload),
        "valuation": _valuation_check("valuation-check", payload),
        "score": _stock_score("stock-score", payload, prewarm, sources),
    }
    missing = [name for name, section in sections.items() if not section["ok"]]
    output = _base_output(command, payload)
    output["sources"] = sorted({src for section in sections.values() for src in section.get("sources", [])})
    output["warnings"] = [f"{name}_incomplete" for name in missing]
    output["result"] = {
        "sections": {name: section["result"] for name, section in sections.items()},
        "missing_sections": missing,
        "research_complete": not missing,
        "decision_allowed": False,
    }
    return output


def _run(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    if command == "financial-diagnosis":
        return _financial_diagnosis(command, payload)
    if command == "fundamental-analysis":
        return _fundamental_analysis(command, payload)
    if command == "narrative-analysis":
        return _narrative_analysis(command, payload, prewarm, sources)
    if command == "stock-analysis":
        return _stock_analysis(command, payload, prewarm, sources)
    if command == "stock-news":
        return _stock_news(command, payload, prewarm, sources)
    if command == "stock-score":
        return _stock_score(command, payload, prewarm, sources)
    if command == "valuation-check":
        return _valuation_check(command, payload)
    raise ValueError(f"unknown_command:{command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = _load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", [])}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
        prewarm, sources = _latest_prewarm()
        output = _run(args.command, payload, prewarm, sources)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
