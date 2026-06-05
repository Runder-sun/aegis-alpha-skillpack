from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "trade-planning"


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


def _load_trade_weights() -> dict[str, float]:
    default = {"event": 0.3, "trend": 0.3, "heat": 0.2, "sentiment": 0.2}
    path = _workspace_dir() / "config" / "trade_weights.json"
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    if not isinstance(payload, dict):
        return default
    weights = {key: float(payload.get(key, value)) for key, value in default.items()}
    total = sum(weights.values()) or 1.0
    return {key: round(value / total, 4) for key, value in weights.items()}


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
            "policy": "trade-planning freshness is inherited from supplied candidates, technical inputs, and latest prewarm artifact",
        },
        "ok": True,
        "decision_allowed": False,
        "max_action_level": "paper_plan_only",
        "requires_human_confirmation": True,
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
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Trade plan inputs are incomplete; do not infer an executable plan.",
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


def _snapshot(prewarm: dict[str, Any]) -> dict[str, Any]:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else {}
    if not snapshot and isinstance(prewarm.get("hhxg_snapshot"), dict):
        snapshot = prewarm["hhxg_snapshot"]
    return snapshot if isinstance(snapshot, dict) else {}


def _risk_level_from_snapshot(snapshot: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str]:
    payload_risk = payload.get("risk_level")
    if payload_risk:
        return str(payload_risk), "payload risk level"
    market = snapshot.get("market") if isinstance(snapshot.get("market"), dict) else {}
    sentiment = _float(market.get("sentiment_index"))
    limit_down = _float(market.get("limit_down"))
    fried = _float(market.get("fried"))
    score = 0
    if sentiment is not None:
        if sentiment < 30:
            score += 2
        elif sentiment < 45:
            score += 1
    if limit_down is not None:
        if limit_down >= 30:
            score += 3
        elif limit_down >= 10:
            score += 2
        elif limit_down >= 5:
            score += 1
    if fried is not None and fried >= 30:
        score += 1
    if score >= 4:
        return "red", "market sentiment and limit-down pressure are severe"
    if score >= 3:
        return "orange", "market breadth risk is elevated"
    if score >= 2:
        return "yellow", "market risk is moderate"
    return "green", "no extreme market risk detected"


def _themesurfer_status(prewarm: dict[str, Any], payload: dict[str, Any]) -> str:
    if payload.get("themesurfer_status"):
        status = str(payload["themesurfer_status"]).upper()
        return status if status in {"FULL", "LOCKOUT", "UNKNOWN"} else "UNKNOWN"
    signal = prewarm.get("themesurfer_signal") if isinstance(prewarm.get("themesurfer_signal"), dict) else {}
    data = signal.get("data") if isinstance(signal.get("data"), dict) else {}
    status = str(data.get("status") or "UNKNOWN").upper()
    return status if status in {"FULL", "LOCKOUT"} else "UNKNOWN"


def _payload_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("candidates")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _snapshot_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    hot = snapshot.get("hotmoney") if isinstance(snapshot.get("hotmoney"), dict) else {}
    for item in (hot.get("top_net_buy") or [])[:12]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        candidates.append({
            "name": name,
            "net_yi": item.get("net_yi"),
            "theme": item.get("theme"),
            "reason": f"hot money net buy {item.get('net_yi')}",
            "source": "hotmoney.top_net_buy",
        })
    themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
    for theme in themes[:6]:
        if not isinstance(theme, dict):
            continue
        for stock in (theme.get("top_stocks") or [])[:3]:
            if not isinstance(stock, dict):
                continue
            name = stock.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append({
                "name": name,
                "theme": theme.get("name"),
                "net_yi": stock.get("net_yi") or theme.get("net_yi"),
                "limitup": stock.get("limitup_count") or theme.get("limitup_count"),
                "reason": f"active theme {theme.get('name')}",
                "source": "hot_themes.top_stocks",
            })
    return candidates[:15]


def _candidate_pool(payload: dict[str, Any], prewarm: dict[str, Any]) -> list[dict[str, Any]]:
    return _payload_candidates(payload) or _snapshot_candidates(_snapshot(prewarm))


def _score_candidate(candidate: dict[str, Any], risk_level: str, weights: dict[str, float]) -> dict[str, Any]:
    event = min(float(candidate.get("news_hits") or candidate.get("research_hits") or 0), 6.0) / 6.0 * 100
    trend = min(max(float(candidate.get("limitup") or candidate.get("trend_score") or 0) / 4.0, 0), 1) * 100
    heat_raw = _float(candidate.get("net_yi"))
    heat = min(max((heat_raw or 0) / 10.0, 0), 1) * 100
    sentiment = float(candidate.get("sentiment_score") or 50)
    risk_penalty = {"red": 20, "orange": 12, "yellow": 6}.get(risk_level, 0)
    score = (
        event * weights["event"]
        + trend * weights["trend"]
        + heat * weights["heat"]
        + sentiment * weights["sentiment"]
        - risk_penalty
    )
    enriched = dict(candidate)
    enriched["score"] = round(max(0, min(100, score)), 2)
    enriched["score_breakdown"] = {
        "event": round(event, 2),
        "trend": round(trend, 2),
        "heat": round(heat, 2),
        "sentiment": round(sentiment, 2),
        "risk_penalty": -risk_penalty,
    }
    return enriched


def _position_caps(risk_level: str, status: str) -> tuple[float, float]:
    total = {"green": 0.6, "yellow": 0.4, "orange": 0.25, "red": 0.0}.get(risk_level, 0.25)
    if status != "FULL":
        total = min(total, 0.15)
    single = min(0.1, total / 3) if total > 0 else 0.0
    return total, round(single, 4)


def _short_term_analysis(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    snapshot = _snapshot(prewarm)
    candidates = _candidate_pool(payload, prewarm)
    if not candidates:
        return _fail(command, payload, ["candidates_missing"], ["provide candidates or run market prewarm"])
    risk_level, risk_reason = _risk_level_from_snapshot(snapshot, payload)
    status = _themesurfer_status(prewarm, payload)
    weights = _load_trade_weights()
    scored = [_score_candidate(candidate, risk_level, weights) for candidate in candidates]
    scored_sorted = sorted(scored, key=lambda item: item.get("score", 0), reverse=True)
    total_cap, single_cap = _position_caps(risk_level, status)
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.candidates"] if _payload_candidates(payload) else [])
    output["warnings"] = [] if status == "FULL" else ["new_positions_restricted_by_market_filter"]
    output["result"] = {
        "themesurfer_status": status,
        "allow_new_positions": status == "FULL" and total_cap > 0,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "position_cap": total_cap,
        "single_position_cap": single_cap,
        "candidates": scored_sorted[:10],
        "score_schema": weights | {"risk_penalty": "depends on risk_level"},
        "note": "paper plan only; human confirmation required",
    }
    return output


def _theme_identification(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    themes = payload.get("themes") if isinstance(payload.get("themes"), list) else []
    if not themes:
        snapshot = _snapshot(prewarm)
        themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
    if not themes:
        return _fail(command, payload, ["themes_missing"], ["provide themes or run market prewarm"])
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.themes"] if payload.get("themes") else [])
    output["result"] = {
        "themes": themes[:10],
        "count": min(len(themes), 10),
    }
    return output


def _theme_targets(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    candidates = _candidate_pool(payload, prewarm)
    if not candidates:
        return _fail(command, payload, ["candidates_missing"], ["provide candidates or run market prewarm"])
    by_theme: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        theme = str(candidate.get("theme") or candidate.get("source") or "unclassified")
        by_theme.setdefault(theme, []).append(candidate)
    targets = [
        {"theme": theme, "targets": sorted(items, key=lambda item: item.get("score", 0), reverse=True)[:5]}
        for theme, items in by_theme.items()
    ]
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.candidates"] if _payload_candidates(payload) else [])
    output["result"] = {"theme_targets": targets, "theme_count": len(targets)}
    return output


def _stock_technical_scan(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    price = _float(payload.get("price"))
    ma20 = _float(payload.get("ma20"))
    ma60 = _float(payload.get("ma60"))
    support = _float(payload.get("support"))
    resistance = _float(payload.get("resistance"))
    rsi = _float(payload.get("rsi"))
    if price is None or ma20 is None:
        return _fail(command, payload, ["price_and_ma20_required"])
    trend = "uptrend" if price >= ma20 and (ma60 is None or price >= ma60) else "weak_or_range"
    flags: list[str] = []
    if rsi is not None and rsi > 75:
        flags.append("overbought_rsi")
    if rsi is not None and rsi < 30:
        flags.append("oversold_rsi")
    entry_zone = [round(price * 0.98, 4), round(price * 1.01, 4)] if trend == "uptrend" else []
    stop_loss = support if support is not None and support < price else round(price * 0.93, 4)
    take_profit_reference = resistance if resistance is not None and resistance > price else round(price * 1.12, 4)
    output = _base_output(command, payload)
    output["result"] = {
        "trend": trend,
        "flags": flags,
        "entry_zone": entry_zone,
        "stop_loss_reference": stop_loss,
        "take_profit_reference": take_profit_reference,
        "invalid_if": [
            "price closes below stop_loss_reference",
            "market filter enters LOCKOUT",
        ],
    }
    return output


def _strategy_advisor(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    short = _short_term_analysis("short-term-analysis", payload, prewarm, sources)
    if not short["ok"]:
        return short
    result = short["result"]
    allow_new = result.get("allow_new_positions") is True
    strategy = "observe"
    if allow_new:
        strategy = "pilot_then_scale"
    elif result.get("risk_level") == "red":
        strategy = "risk_off"
    output = _base_output(command, payload)
    output["sources"] = short.get("sources", [])
    output["warnings"] = short.get("warnings", [])
    output["result"] = {
        "strategy": strategy,
        "rules": [
            "Start with pilot size only after human confirmation.",
            "Scale only after thesis confirmation and market filter remains FULL.",
            "Cut exposure when invalidation trigger is hit.",
        ],
        "risk_level": result.get("risk_level"),
        "themesurfer_status": result.get("themesurfer_status"),
        "position_cap": result.get("position_cap"),
        "single_position_cap": result.get("single_position_cap"),
        "top_candidates": result.get("candidates", [])[:5],
    }
    return output


def _full_investment_plan(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    short = _short_term_analysis("short-term-analysis", payload, prewarm, sources)
    themes = _theme_identification("theme-identification", payload, prewarm, sources)
    targets = _theme_targets("theme-targets", payload, prewarm, sources)
    strategy = _strategy_advisor("strategy-advisor", payload, prewarm, sources)
    technical_payload = payload.get("technical") if isinstance(payload.get("technical"), dict) else payload
    technical = _stock_technical_scan("stock-technical-scan", technical_payload)
    sections = {
        "short_term": short,
        "themes": themes,
        "targets": targets,
        "strategy": strategy,
        "technical": technical,
    }
    missing = [name for name, section in sections.items() if not section["ok"]]
    output = _base_output(command, payload)
    output["sources"] = sorted({src for section in sections.values() for src in section.get("sources", [])})
    output["warnings"] = [f"{name}_incomplete" for name in missing]
    output["result"] = {
        "plan_complete": not missing,
        "missing_sections": missing,
        "sections": {name: section["result"] for name, section in sections.items()},
        "execution_policy": {
            "decision_allowed": False,
            "requires_human_confirmation": True,
            "max_action_level": "paper_plan_only",
        },
    }
    return output


def _trading_strategy_v2(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    plan = _full_investment_plan("full-investment-plan", payload, prewarm, sources)
    output = _base_output(command, payload)
    output["sources"] = plan.get("sources", [])
    output["warnings"] = plan.get("warnings", [])
    output["errors"] = plan.get("errors", [])
    output["ok"] = plan.get("ok", False)
    output["result"] = {
        "schema_version": 2,
        "plan": plan.get("result", {}),
    }
    return output


def _run(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    if command == "full-investment-plan":
        return _full_investment_plan(command, payload, prewarm, sources)
    if command == "short-term-analysis":
        return _short_term_analysis(command, payload, prewarm, sources)
    if command == "stock-technical-scan":
        return _stock_technical_scan(command, payload)
    if command == "strategy-advisor":
        return _strategy_advisor(command, payload, prewarm, sources)
    if command == "theme-identification":
        return _theme_identification(command, payload, prewarm, sources)
    if command == "theme-targets":
        return _theme_targets(command, payload, prewarm, sources)
    if command == "trading-strategy-v2":
        return _trading_strategy_v2(command, payload, prewarm, sources)
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
