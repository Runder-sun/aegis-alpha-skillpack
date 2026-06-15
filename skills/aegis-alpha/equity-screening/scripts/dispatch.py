from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "equity-screening"


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


def _load_global_theme_map(base: Path) -> tuple[dict[str, Any], str | None]:
    path = base / "data" / "global-theme-map.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "theme_chain_map_missing"
    except Exception:
        return {}, "theme_chain_map_invalid_json"
    return (payload if isinstance(payload, dict) else {}), None


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


def _has_prewarm_data(prewarm: dict[str, Any]) -> bool:
    return not (prewarm.get("_prewarm_missing") or prewarm.get("_prewarm_invalid"))


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
            "policy": "screening freshness is inherited from supplied candidates or the latest prewarm artifact",
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
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Screening evidence is incomplete; do not infer an empty opportunity set.",
        "missing_critical_inputs": errors,
    }
    return output


def _snapshot(prewarm: dict[str, Any]) -> dict[str, Any]:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    snapshot = prewarm.get("hhxg_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else {}
    return snapshot if isinstance(snapshot, dict) else {}


def _payload_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("candidates")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _iter_items(prewarm: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    news_surface = prewarm.get("news_sentiment") if isinstance(prewarm.get("news_sentiment"), dict) else {}
    for source in (prewarm, market_data, news_surface):
        for key in keys:
            value = source.get(key)
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
    return items


def _count_hits(name: str, items: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    if not name:
        return 0
    count = 0
    for item in items:
        text = " ".join(str(item.get(field) or "") for field in fields)
        if name in text:
            count += 1
    return count


def _snapshot_candidates(snapshot: dict[str, Any], prewarm: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    reports = _iter_items(prewarm, ["tushare_research_report", "research_reports"])
    news = _iter_items(prewarm, ["tushare_news", "tushare_major_news", "news"])
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
            "code": item.get("code") or item.get("ts_code"),
            "theme": item.get("theme"),
            "net_yi": item.get("net_yi"),
            "reason": f"hot money net buy {item.get('net_yi')}",
            "research_hits": _count_hits(name, reports, ("title", "summary")),
            "news_hits": _count_hits(name, news, ("title", "content", "summary")),
            "source": "hotmoney.top_net_buy",
        })
    sectors = snapshot.get("sectors") if isinstance(snapshot.get("sectors"), list) else []
    for group in sectors:
        if not isinstance(group, dict):
            continue
        label = group.get("label") or ""
        for item in group.get("strong", []) or []:
            if not isinstance(item, dict):
                continue
            leader = item.get("leader")
            if not leader or leader in seen:
                continue
            seen.add(leader)
            candidates.append({
                "name": leader,
                "theme": item.get("name"),
                "reason": f"{label}{item.get('name')} leader",
                "net_yi": item.get("net_yi"),
                "limitup": item.get("limitup_count"),
                "research_hits": _count_hits(leader, reports, ("title", "summary")),
                "news_hits": _count_hits(leader, news, ("title", "content", "summary")),
                "source": "sectors.strong",
            })
    themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
    for theme in themes[:8]:
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
                "code": stock.get("code") or stock.get("ts_code"),
                "theme": theme.get("name"),
                "reason": f"active theme {theme.get('name')}",
                "net_yi": stock.get("net_yi") or theme.get("net_yi"),
                "limitup": stock.get("limitup_count") or theme.get("limitup_count"),
                "research_hits": _count_hits(name, reports, ("title", "summary")),
                "news_hits": _count_hits(name, news, ("title", "content", "summary")),
                "source": "hot_themes.top_stocks",
            })
    return candidates[:30]


def _candidate_pool(payload: dict[str, Any], prewarm: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    payload_items = _payload_candidates(payload)
    if payload_items:
        return payload_items, ["payload.candidates"]
    snapshot = _snapshot(prewarm)
    items = _snapshot_candidates(snapshot, prewarm)
    return items, []


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_candidate(candidate: dict[str, Any], sentiment_index: float | None) -> dict[str, Any]:
    net_yi = _float(candidate.get("net_yi")) or 0.0
    capital = min(max(net_yi / 10.0, 0), 1) * 100
    theme_match = 100 if candidate.get("theme") else 50
    info = min((_float(candidate.get("news_hits")) or 0) + (_float(candidate.get("research_hits")) or 0), 6) / 6 * 100
    sentiment = 50.0
    if sentiment_index is not None:
        sentiment = max(min((sentiment_index - 30) / 40.0, 1), 0) * 100
    score = capital * 0.35 + theme_match * 0.2 + info * 0.25 + sentiment * 0.2
    risk_penalty = 0
    if sentiment_index is not None and sentiment_index < 40:
        risk_penalty = 8
        score -= risk_penalty
    enriched = dict(candidate)
    enriched["score"] = round(max(0, min(100, score)), 2)
    enriched["score_breakdown"] = {
        "capital": round(capital, 2),
        "theme_match": round(theme_match, 2),
        "info": round(info, 2),
        "sentiment": round(sentiment, 2),
        "risk_penalty": -risk_penalty,
    }
    return enriched


def _score_theme_chain_candidate(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    forward_pe = _float(candidate.get("forward_pe"))
    ai_exposure = _float(candidate.get("ai_infra_exposure")) or 0.0
    bottleneck = _float(candidate.get("bottleneck_score")) or 0.0
    model_shift = _float(candidate.get("model_shift_score")) or 0.0
    evidence = _float(candidate.get("evidence_quality")) or 0.0
    max_forward_pe = _float(payload.get("max_forward_pe"))
    if forward_pe is None:
        valuation = 35.0
    elif max_forward_pe is not None and max_forward_pe > 0:
        valuation = max(min((max_forward_pe - forward_pe) / max_forward_pe, 1), 0) * 100
    else:
        valuation = 100 if forward_pe <= 12 else 80 if forward_pe <= 18 else 60 if forward_pe <= 25 else 35 if forward_pe <= 40 else 15
    score = valuation * 0.3 + ai_exposure * 0.2 + bottleneck * 0.2 + model_shift * 0.2 + evidence * 0.1
    risks = candidate.get("risk_flags") if isinstance(candidate.get("risk_flags"), list) else []
    risk_penalty = 0
    if "already_rerated" in risks:
        risk_penalty += 10
    if "governance_or_accounting_risk" in risks:
        risk_penalty += 12
    enriched = dict(candidate)
    enriched["score"] = round(max(0, min(100, score - risk_penalty)), 2)
    enriched["score_breakdown"] = {
        "valuation": round(valuation, 2),
        "ai_infra_exposure": round(ai_exposure, 2),
        "bottleneck": round(bottleneck, 2),
        "model_shift": round(model_shift, 2),
        "evidence_quality": round(evidence, 2),
        "risk_penalty": -risk_penalty,
    }
    return enriched


def _theme_chain_candidates(theme_map: dict[str, Any], payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    payload_map = payload.get("theme_map") if isinstance(payload.get("theme_map"), dict) else None
    active_map = payload_map or theme_map
    themes = active_map.get("themes") if isinstance(active_map.get("themes"), list) else []
    theme_filter = {str(item) for item in payload.get("theme_ids", [])} if isinstance(payload.get("theme_ids"), list) else set()
    node_filter = {str(item) for item in payload.get("node_ids", [])} if isinstance(payload.get("node_ids"), list) else set()
    region_filter = {str(item).upper() for item in payload.get("regions", [])} if isinstance(payload.get("regions"), list) else set()
    max_forward_pe = _float(payload.get("max_forward_pe"))
    candidates: list[dict[str, Any]] = []
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        theme_id = str(theme.get("id") or "")
        if theme_filter and theme_id not in theme_filter:
            continue
        nodes = theme.get("nodes") if isinstance(theme.get("nodes"), list) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            if node_filter and node_id not in node_filter:
                continue
            for item in node.get("candidates") or []:
                if not isinstance(item, dict):
                    continue
                region = str(item.get("region") or "").upper()
                if region_filter and region not in region_filter:
                    continue
                forward_pe = _float(item.get("forward_pe"))
                if max_forward_pe is not None and forward_pe is not None and forward_pe > max_forward_pe:
                    continue
                candidate = dict(item)
                candidate.update({
                    "theme": theme.get("name"),
                    "theme_id": theme_id,
                    "theme_thesis": theme.get("thesis"),
                    "chain_node": node.get("name"),
                    "chain_node_id": node_id,
                    "chain_role": node.get("role"),
                    "repricing_model": node.get("repricing_model"),
                    "valuation_models": node.get("valuation_models") if isinstance(node.get("valuation_models"), list) else [],
                    "reason": f"{node.get('name')} / {node.get('repricing_model')}",
                    "source": "global-theme-map" if payload_map is None else "payload.theme_map",
                })
                candidates.append(candidate)
    scored = sorted((_score_theme_chain_candidate(candidate, payload) for candidate in candidates), key=lambda item: item.get("score", 0), reverse=True)
    return scored, ["payload.theme_map"] if payload_map is not None else ["data/global-theme-map.json"]


def _score_candidates(candidates: list[dict[str, Any]], prewarm: dict[str, Any]) -> list[dict[str, Any]]:
    market = _snapshot(prewarm).get("market")
    sentiment = _float(market.get("sentiment_index")) if isinstance(market, dict) else None
    return sorted((_score_candidate(candidate, sentiment) for candidate in candidates), key=lambda item: item.get("score", 0), reverse=True)


def _screen(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str], layered: bool = False) -> dict[str, Any]:
    candidates, local_sources = _candidate_pool(payload, prewarm)
    if not candidates:
        return _fail(command, payload, ["candidates_missing"], ["provide candidates or run market prewarm"])
    scored = _score_candidates(candidates, prewarm)
    min_score = float(payload.get("min_score", 0))
    filtered = [candidate for candidate in scored if candidate.get("score", 0) >= min_score]
    if layered:
        result = {
            "layers": {
                "core": [c for c in filtered if c.get("score", 0) >= 75],
                "watchlist": [c for c in filtered if 55 <= c.get("score", 0) < 75],
                "reject": [c for c in scored if c.get("score", 0) < 55],
            }
        }
    else:
        result = {"candidates": filtered}
    result.update({
        "count": len(filtered),
        "total_input": len(candidates),
        "score_schema": {
            "capital": 0.35,
            "theme_match": 0.2,
            "info": 0.25,
            "sentiment": 0.2,
        },
    })
    output = _base_output(command, payload)
    output["sources"] = sources + local_sources
    output["warnings"] = [] if filtered else ["no_candidates_passed_filter"]
    output["result"] = result
    return output


def _theme_chain_screen(command: str, payload: dict[str, Any], base: Path) -> dict[str, Any]:
    theme_map, error = _load_global_theme_map(base)
    if error and not isinstance(payload.get("theme_map"), dict):
        return _fail(command, payload, [error])
    candidates, local_sources = _theme_chain_candidates(theme_map, payload)
    if not candidates:
        return _fail(command, payload, ["theme_chain_candidates_missing"], ["adjust node_ids, regions, or max_forward_pe"])
    min_score = float(payload.get("min_score", 0))
    filtered = [candidate for candidate in candidates if candidate.get("score", 0) >= min_score]
    layers = {
        "core": [c for c in filtered if c.get("score", 0) >= 75],
        "watchlist": [c for c in filtered if 55 <= c.get("score", 0) < 75],
        "expensive_or_risk": [c for c in filtered if c.get("score", 0) < 55],
    }
    node_summary: dict[str, dict[str, Any]] = {}
    for candidate in filtered:
        node_id = str(candidate.get("chain_node_id") or "unknown")
        bucket = node_summary.setdefault(node_id, {
            "chain_node": candidate.get("chain_node"),
            "count": 0,
            "top_score": 0,
        })
        bucket["count"] += 1
        bucket["top_score"] = max(bucket["top_score"], candidate.get("score", 0))
    output = _base_output(command, payload)
    output["sources"] = local_sources
    output["warnings"] = [] if filtered else ["no_candidates_passed_filter"]
    output["result"] = {
        "theme": "AI Infrastructure",
        "candidates": filtered,
        "layers": layers,
        "node_summary": list(node_summary.values()),
        "count": len(filtered),
        "total_input": len(candidates),
        "score_schema": {
            "valuation": 0.3,
            "ai_infra_exposure": 0.2,
            "bottleneck": 0.2,
            "model_shift": 0.2,
            "evidence_quality": 0.1,
        },
    }
    return output


def _stock_rating(command: str, payload: dict[str, Any], prewarm: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else dict(payload)
    if not candidate.get("name") and not candidate.get("code"):
        return _fail(command, payload, ["candidate_required"])
    scored = _score_candidates([candidate], prewarm)[0]
    grade = "core" if scored["score"] >= 75 else "watchlist" if scored["score"] >= 55 else "reject"
    output = _base_output(command, payload)
    output["result"] = {"candidate": scored, "grade": grade}
    return output


def _pool_path() -> Path:
    return _workspace_dir() / "memory" / "stock_pool" / "screening-pool.json"


def _read_pool() -> tuple[list[dict[str, Any]], str | None]:
    path = _pool_path()
    if not path.exists():
        return [], None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [], "stock_pool_invalid_json"
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        return [item for item in payload["candidates"] if isinstance(item, dict)], None
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], None
    return [], "stock_pool_invalid_schema"


def _write_pool(candidates: list[dict[str, Any]]) -> Path:
    path = _pool_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _stock_pool_update(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str], session: str) -> dict[str, Any]:
    screen = _screen(command, payload, prewarm, sources)
    if not screen["ok"]:
        return screen
    existing, pool_error = _read_pool()
    if pool_error:
        return _fail(command, payload, [pool_error])
    seen = {str(item.get("code") or item.get("name")) for item in existing}
    additions = []
    for candidate in screen["result"].get("candidates", []):
        key = str(candidate.get("code") or candidate.get("name"))
        if key in seen:
            continue
        candidate = dict(candidate)
        candidate["session"] = session
        additions.append(candidate)
        existing.append(candidate)
        seen.add(key)
    path = _write_pool(existing)
    output = _base_output(command, payload)
    output["sources"] = screen.get("sources", [])
    output["artifacts"] = [str(path)]
    output["warnings"] = screen.get("warnings", [])
    output["result"] = {
        "added": additions,
        "added_count": len(additions),
        "pool_count": len(existing),
    }
    return output


def _board_universe_sync(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    boards = payload.get("boards") if isinstance(payload.get("boards"), list) else []
    if not boards:
        snapshot = _snapshot(prewarm)
        themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
        boards = [{"name": theme.get("name"), "source": "hot_themes"} for theme in themes if isinstance(theme, dict) and theme.get("name")]
    if not boards:
        return _fail(command, payload, ["boards_or_themes_missing"])
    path = _workspace_dir() / "memory" / "universe" / "board-universe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"updated_at": datetime.now(timezone.utc).isoformat(), "boards": boards}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    output = _base_output(command, payload)
    output["sources"] = sources + (["payload.boards"] if payload.get("boards") else [])
    output["artifacts"] = [str(path)]
    output["result"] = {"boards": boards, "count": len(boards)}
    return output


def _leader_source_harvest(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    candidates, local_sources = _candidate_pool(payload, prewarm)
    leaders = [c for c in _score_candidates(candidates, prewarm) if c.get("score", 0) >= float(payload.get("min_score", 55))]
    if not leaders:
        return _fail(command, payload, ["leaders_missing"], ["provide candidates or lower min_score"])
    output = _base_output(command, payload)
    output["sources"] = sources + local_sources
    output["result"] = {"leaders": leaders[:20], "count": min(len(leaders), 20)}
    return output


def _company_evidence_collect(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    name = str(payload.get("name") or payload.get("query") or "").strip()
    code = str(payload.get("code") or payload.get("symbol") or "").strip()
    if not name and not code:
        return _fail(command, payload, ["code_or_name_required"])
    payload_reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []
    payload_news = payload.get("news") if isinstance(payload.get("news"), list) else []
    if not payload_reports and not payload_news and not _has_prewarm_data(prewarm):
        return _fail(command, payload, ["evidence_source_missing"], ["provide reports/news payload or run market prewarm"])
    reports = [item for item in payload_reports if isinstance(item, dict)] or _iter_items(prewarm, ["tushare_research_report", "research_reports"])
    news = [item for item in payload_news if isinstance(item, dict)] or _iter_items(prewarm, ["tushare_news", "tushare_major_news", "news"])
    def match(item: dict[str, Any]) -> bool:
        text = " ".join(str(item.get(field) or "") for field in ("title", "summary", "content", "ts_code", "code", "name"))
        return bool((name and name in text) or (code and code in text))
    evidence = {
        "reports": [item for item in reports if match(item)][:20],
        "news": [item for item in news if match(item)][:20],
    }
    output = _base_output(command, payload)
    payload_sources = []
    if payload_reports:
        payload_sources.append("payload.reports")
    if payload_news:
        payload_sources.append("payload.news")
    output["sources"] = sources + payload_sources
    output["warnings"] = [] if evidence["reports"] or evidence["news"] else ["no_matching_evidence_found"]
    output["result"] = evidence | {"code": code, "name": name}
    return output


def _run(command: str, payload: dict[str, Any], prewarm: dict[str, Any], sources: list[str], base: Path) -> dict[str, Any]:
    if command == "board-universe-sync":
        return _board_universe_sync(command, payload, prewarm, sources)
    if command == "company-evidence-collect":
        return _company_evidence_collect(command, payload, prewarm, sources)
    if command == "theme-chain-screening":
        return _theme_chain_screen(command, payload, base)
    if command == "layered-stock-screening":
        return _screen(command, payload, prewarm, sources, layered=True)
    if command == "leader-source-harvest":
        return _leader_source_harvest(command, payload, prewarm, sources)
    if command == "stock-pool-incremental-am":
        return _stock_pool_update(command, payload, prewarm, sources, "am")
    if command == "stock-pool-incremental-pm":
        return _stock_pool_update(command, payload, prewarm, sources, "pm")
    if command == "stock-pool-maintenance":
        return _stock_pool_update(command, payload, prewarm, sources, "maintenance")
    if command == "stock-rating":
        return _stock_rating(command, payload, prewarm)
    if command in {"stock-screening", "stock-screening-v2"}:
        return _screen(command, payload, prewarm, sources)
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
        output = _run(args.command, payload, prewarm, sources, package_root)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
