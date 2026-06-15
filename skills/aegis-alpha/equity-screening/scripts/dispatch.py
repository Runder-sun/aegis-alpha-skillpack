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
    path = base / "data" / "theme-chain-template.ai-infrastructure.json"
    if not path.exists():
        path = base / "data" / "global-theme-map.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "theme_chain_map_missing"
    except Exception:
        return {}, "theme_chain_map_invalid_json"
    return (payload if isinstance(payload, dict) else {}), None


def _dynamic_theme_dir() -> Path:
    return _workspace_dir() / "memory" / "dynamic_themes"


def _dynamic_theme_chain_map_path() -> Path:
    return _dynamic_theme_dir() / "theme-chain-map.json"


def _theme_stock_pool_path() -> Path:
    return _workspace_dir() / "memory" / "stock_pool" / "theme-stock-pool.json"


def _coverage_plan_path() -> Path:
    return _dynamic_theme_dir() / "coverage-plan.json"


def _theme_maintenance_review_path() -> Path:
    return _dynamic_theme_dir() / "theme-maintenance-review.json"


def _theme_candidates_path() -> Path:
    return _dynamic_theme_dir() / "theme-candidates.jsonl"


def _evidence_ledger_path() -> Path:
    return _dynamic_theme_dir() / "evidence-ledger.jsonl"


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except Exception:
        return default
    return payload if payload is not None else default


def _read_evidence_ledger() -> list[dict[str, Any]]:
    path = _evidence_ledger_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


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
                    "source": "theme-chain-template" if payload_map is None else "payload.theme_map",
                })
                candidates.append(candidate)
    scored = sorted((_score_theme_chain_candidate(candidate, payload) for candidate in candidates), key=lambda item: item.get("score", 0), reverse=True)
    return scored, ["payload.theme_map"] if payload_map is not None else ["data/theme-chain-template.ai-infrastructure.json"]


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
        "template_only": payload.get("template_only", True),
        "note": "This command uses a bundled chain template/fixture. Do not treat it as a full market scan.",
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


def _load_active_theme_map(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], str | None]:
    if isinstance(payload.get("theme_map"), dict):
        return payload["theme_map"], ["payload.theme_map"], None
    dynamic_map = _read_json_file(_dynamic_theme_chain_map_path(), {})
    if isinstance(dynamic_map, dict) and isinstance(dynamic_map.get("themes"), list) and dynamic_map.get("themes"):
        return dynamic_map, [str(_dynamic_theme_chain_map_path())], None
    return {}, [], "theme_chain_map_missing"


def _normalize_symbol_key(symbol: Any, region: Any = None) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    market = str(region or "").strip().upper()
    if raw.startswith("."):
        return raw
    if "." in raw:
        code, suffix = raw.rsplit(".", 1)
        if suffix in {"US", "HK", "SH", "SZ", "T", "KS", "KQ", "TW"}:
            if suffix in {"SH", "SZ"}:
                market = "CN"
            elif suffix == "T":
                market = "JP"
            elif suffix in {"KS", "KQ"}:
                market = "KR"
            else:
                market = suffix
            if market == "HK" and code.isdigit():
                code = code.zfill(4)
            return f"{market}:{code}"
    if market == "US":
        return f"US:{raw}"
    if market == "HK":
        return f"HK:{raw.zfill(4)}" if raw.isdigit() else f"HK:{raw}"
    if market == "CN":
        return f"CN:{raw}"
    if market == "JP":
        return f"JP:{raw}"
    if market == "KR":
        return f"KR:{raw}"
    if market == "TW":
        return f"TW:{raw}"
    return raw


def _candidate_key(candidate: dict[str, Any]) -> str:
    symbol = candidate.get("symbol") or candidate.get("code")
    if symbol:
        return _normalize_symbol_key(symbol, candidate.get("region") or candidate.get("market_region"))
    theme = str(candidate.get("theme_id") or "").strip().lower()
    name = str(candidate.get("name") or "").strip().upper()
    return f"NAME:{theme}:{name}" if name else ""


def _list_add_unique(values: list[Any], additions: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for value in values + additions:
        if value in (None, ""):
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _merge_candidate_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        merged = dict(incoming)
    else:
        old_score = _float(existing.get("score")) or 0.0
        new_score = _float(incoming.get("score")) or 0.0
        primary, secondary = (incoming, existing) if new_score >= old_score else (existing, incoming)
        merged = dict(secondary)
        merged.update(primary)
        for key in ("verified_by", "market_data_verified", "verification_status", "verification_scope", "quote_source_url", "quote_source_name"):
            if incoming.get(key) not in (None, "", []):
                merged[key] = incoming.get(key)
            elif existing.get(key) not in (None, "", []):
                merged[key] = existing.get(key)
    aliases = []
    for item in (existing, incoming):
        aliases.extend(item.get("aliases") if isinstance(item.get("aliases"), list) else [])
        for key in ("symbol", "code", "name"):
            if item.get(key):
                aliases.append(item.get(key))
    merged["aliases"] = _list_add_unique([], aliases)
    node_ids = []
    for item in (existing, incoming):
        node_ids.extend(item.get("chain_node_ids") if isinstance(item.get("chain_node_ids"), list) else [])
        node = item.get("chain_node_id") or item.get("node_id")
        if node:
            node_ids.append(node)
    merged["chain_node_ids"] = _list_add_unique([], node_ids)
    evidence_ids = []
    for item in (existing, incoming):
        evidence_ids.extend(item.get("evidence_ids") if isinstance(item.get("evidence_ids"), list) else [])
    merged["evidence_ids"] = _list_add_unique([], evidence_ids)
    providers = []
    for item in (existing, incoming):
        providers.extend(item.get("provider_route") if isinstance(item.get("provider_route"), list) else [])
        verified_by = item.get("verified_by")
        if isinstance(verified_by, list):
            providers.extend(verified_by)
        elif verified_by:
            providers.append(verified_by)
    if providers:
        merged["provider_route"] = _list_add_unique([], providers)
    return merged


def _is_equity_candidate_node(node: dict[str, Any]) -> bool:
    mode = str(node.get("coverage_mode") or node.get("candidate_mode") or "").lower()
    if mode in {"evidence_only", "demand_driver", "non_equity"}:
        return False
    role = str(node.get("role") or "").lower()
    if role in {"demand_driver", "macro_driver", "customer_budget", "capex_driver"}:
        return False
    node_id = str(node.get("id") or "").lower()
    if "hyperscaler" in node_id or node_id.endswith("-capex") or "capex" in node_id:
        return False
    return True


def _theme_nodes_from_map(theme_map: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    themes = theme_map.get("themes") if isinstance(theme_map.get("themes"), list) else []
    theme_filter = {str(item) for item in payload.get("theme_ids", [])} if isinstance(payload.get("theme_ids"), list) else set()
    nodes: list[dict[str, Any]] = []
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        theme_id = str(theme.get("id") or "")
        if theme_filter and theme_id not in theme_filter:
            continue
        for node in theme.get("nodes") or []:
            if isinstance(node, dict):
                item = dict(node)
                item["theme_id"] = theme_id
                item["theme"] = theme.get("name")
                nodes.append(item)
    return nodes


def _candidate_regions(candidates: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("region") or item.get("market_region") or "").upper() for item in candidates if item.get("region") or item.get("market_region")}


def _normalize_candidate(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    item = dict(candidate)
    default_theme_id = payload.get("theme_id")
    if default_theme_id is None and isinstance(payload.get("theme_ids"), list) and payload.get("theme_ids"):
        default_theme_id = payload["theme_ids"][0]
    item.setdefault("theme_id", default_theme_id)
    item.setdefault("source", candidate.get("source") or "agent_supplied")
    item.setdefault("candidate_source_type", candidate.get("candidate_source_type") or "agent_native_research")
    item.setdefault("discovered_at", now)
    item.setdefault("last_seen_at", now)
    item.setdefault("state", "candidate")
    return item


def _plan_theme_coverage(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    theme_map, sources, error = _load_active_theme_map(payload)
    if error and not isinstance(payload.get("theme_map"), dict):
        return _fail(command, payload, [error], ["write theme registry first or provide payload.theme_map"])
    nodes = _theme_nodes_from_map(theme_map, payload)
    if not nodes:
        return _fail(command, payload, ["theme_nodes_missing"], ["write theme registry with chain nodes first"])

    required_markets = [str(item).upper() for item in payload.get("required_markets", [])] if isinstance(payload.get("required_markets"), list) else ["CN", "HK", "US", "JP", "KR", "TW"]
    candidate_rows = _read_jsonl(_theme_candidates_path())
    node_plans = []
    for node in nodes:
        node_id = str(node.get("id") or "")
        equity_candidate_node = _is_equity_candidate_node(node)
        node_candidates = [
            item for item in candidate_rows
            if isinstance(item, dict)
            and str(item.get("theme_id") or "") == str(node.get("theme_id") or "")
            and (not node_id or str(item.get("chain_node_id") or item.get("node_id") or "") == node_id)
        ]
        covered = sorted(_candidate_regions(node_candidates))
        gaps = [market for market in required_markets if market not in covered] if equity_candidate_node else []
        node_plans.append({
            "theme_id": node.get("theme_id"),
            "node_id": node_id,
            "node_name": node.get("name"),
            "coverage_kind": "equity_candidates" if equity_candidate_node else "demand_driver_evidence",
            "candidate_count": len(node_candidates),
            "covered_markets": covered,
            "coverage_gaps": gaps,
            "recommended_expansion": _recommended_expansion(gaps) if equity_candidate_node else [
                "track_customer_capex_guidance",
                "track_cloud_budget_commentary",
                "bind demand evidence; do not force market-by-market stock candidates",
            ],
        })

    plan = {
        "version": 1,
        "updated_at": _now(),
        "theme_ids": payload.get("theme_ids") if isinstance(payload.get("theme_ids"), list) else [],
        "required_markets": required_markets,
        "nodes": node_plans,
        "coverage_complete": all(not node.get("coverage_gaps") for node in node_plans),
        "policy": "Coverage planning is advisory. Agent chooses research tools based on user scope and gaps.",
    }
    _coverage_plan_path().parent.mkdir(parents=True, exist_ok=True)
    _coverage_plan_path().write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    output = _base_output(command, payload)
    output["sources"] = sources + [str(_theme_candidates_path())]
    output["artifacts"] = [str(_coverage_plan_path())]
    output["warnings"] = [] if plan["coverage_complete"] else ["coverage_gaps_present"]
    output["result"] = plan
    return output


def _recommended_expansion(gaps: list[str]) -> list[str]:
    recs = []
    if any(market in gaps for market in ("CN", "HK")):
        recs.append("agent_native_research")
    if "CN" in gaps:
        recs.append("tushare_verify")
    if "HK" in gaps:
        recs.append("longbridge_verify")
    if "US" in gaps:
        recs.append("agent_native_research")
        recs.append("longbridge_or_public_quote_verify")
    if any(market in gaps for market in ("JP", "KR", "TW")):
        recs.append("agent_native_research")
        recs.append("official_exchange_or_company_ir_verify")
        recs.append("public_web_delayed_quote_verify")
        recs.append("optional_region_specific_market_data_provider")
    return sorted(set(recs))


def _record_theme_candidates(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    normalized = [_normalize_candidate(item, payload) for item in candidates if isinstance(item, dict)]
    if not normalized:
        plan = _read_json_file(_coverage_plan_path(), {})
        output = _fail(command, payload, ["theme_candidates_missing"], ["provide agent-discovered candidates or run coverage planning"])
        output["result"]["coverage_plan"] = plan if isinstance(plan, dict) else {}
        return output
    _append_jsonl(_theme_candidates_path(), normalized)
    output = _base_output(command, payload)
    output["sources"] = ["payload.candidates"]
    output["artifacts"] = [str(_theme_candidates_path())]
    output["result"] = {
        "recorded": normalized,
        "recorded_count": len(normalized),
        "candidate_ledger_path": str(_theme_candidates_path()),
    }
    return output


def _candidate_rows_for_refresh(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    payload_candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    if payload_candidates:
        return [_normalize_candidate(item, payload) for item in payload_candidates if isinstance(item, dict)], ["payload.candidates"]
    rows = _read_jsonl(_theme_candidates_path())
    theme_filter = {str(item) for item in payload.get("theme_ids", [])} if isinstance(payload.get("theme_ids"), list) else set()
    node_filter = {str(item) for item in payload.get("node_ids", [])} if isinstance(payload.get("node_ids"), list) else set()
    region_filter = {str(item).upper() for item in payload.get("regions", [])} if isinstance(payload.get("regions"), list) else set()
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if theme_filter and str(row.get("theme_id") or "") not in theme_filter:
            continue
        node_id = str(row.get("chain_node_id") or row.get("node_id") or "")
        if node_filter and node_id not in node_filter:
            continue
        region = str(row.get("region") or row.get("market_region") or "").upper()
        if region_filter and region not in region_filter:
            continue
        filtered.append(row)
    return filtered, [str(_theme_candidates_path())]


def _score_theme_candidate(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if any(key in candidate for key in ("ai_infra_exposure", "bottleneck_score", "model_shift_score", "forward_pe")):
        return _score_theme_chain_candidate(candidate, payload)
    evidence_quality = _float(candidate.get("evidence_quality")) or 0.0
    exposure = _float(candidate.get("theme_exposure")) or _float(candidate.get("ai_infra_exposure")) or 50.0
    verification = 80.0 if candidate.get("verified_by") or candidate.get("market_data_verified") else 45.0
    confidence = (_float(candidate.get("confidence")) or 0.5) * 100
    score = exposure * 0.35 + evidence_quality * 0.25 + verification * 0.2 + confidence * 0.2
    enriched = dict(candidate)
    enriched["score"] = round(max(0, min(100, score)), 2)
    enriched["score_breakdown"] = {
        "theme_exposure": round(exposure, 2),
        "evidence_quality": round(evidence_quality, 2),
        "verification": round(verification, 2),
        "confidence": round(confidence, 2),
    }
    return enriched


def _refresh_theme_stock_pool(command: str, payload: dict[str, Any], base: Path) -> dict[str, Any]:
    del base
    candidates, sources = _candidate_rows_for_refresh(payload)
    min_score = float(payload.get("min_score", 0))
    max_candidates = int(payload.get("max_candidates", 120))
    scored = sorted((_score_theme_candidate(candidate, payload) for candidate in candidates), key=lambda item: item.get("score", 0), reverse=True)
    filtered = [candidate for candidate in scored if candidate.get("score", 0) >= min_score]
    if not filtered:
        return _fail(command, payload, ["theme_stock_pool_candidates_missing"], ["record theme candidates first; do not infer an empty opportunity set"])

    existing_doc = _read_json_file(_theme_stock_pool_path(), {"candidates": []})
    if not isinstance(existing_doc, dict) or not isinstance(existing_doc.get("candidates"), list):
        return _fail(command, payload, ["theme_stock_pool_invalid_schema"])
    existing_by_key: dict[str, dict[str, Any]] = {}
    for item in existing_doc.get("candidates", []):
        if not isinstance(item, dict):
            continue
        key = _candidate_key(item)
        if not key:
            continue
        existing_by_key[key] = _merge_candidate_records(existing_by_key.get(key, {}), item)
    additions = []
    now = _now()
    for candidate in filtered[:max_candidates]:
        key = _candidate_key(candidate)
        if not key:
            continue
        was_new = key not in existing_by_key
        enriched = _merge_candidate_records(existing_by_key.get(key, {}), candidate)
        enriched.setdefault("first_seen_at", now)
        enriched["last_seen_at"] = now
        if candidate.get("state") in {"core", "watchlist", "rejected", "stale"}:
            enriched["state"] = candidate.get("state")
        elif candidate.get("score", 0) >= 75:
            enriched["state"] = "core"
        elif candidate.get("score", 0) >= 55:
            enriched["state"] = "watchlist"
        else:
            enriched["state"] = "candidate"
        enriched["canonical_key"] = key
        if was_new:
            additions.append(enriched)
        existing_by_key[key] = enriched

    pool = {
        "version": 1,
        "updated_at": now,
        "source_candidates": sources,
        "candidates": sorted(existing_by_key.values(), key=lambda item: item.get("score", 0), reverse=True),
        "policy": "Research-only theme stock pool. Send candidates to equity-research before paper trade planning.",
    }
    _theme_stock_pool_path().parent.mkdir(parents=True, exist_ok=True)
    _theme_stock_pool_path().write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    output = _base_output(command, payload)
    output["sources"] = sources
    output["artifacts"] = [str(_theme_stock_pool_path())]
    output["result"] = {
        "added": additions,
        "added_count": len(additions),
        "pool_count": len(pool["candidates"]),
        "top_candidates": pool["candidates"][:20],
    }
    return output


def _batch_theme_research(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    pool = _read_json_file(_theme_stock_pool_path(), {})
    if not isinstance(pool, dict) or not isinstance(pool.get("candidates"), list):
        return _fail(command, payload, ["theme_stock_pool_missing"])
    states = {str(item) for item in payload.get("states", [])} if isinstance(payload.get("states"), list) else {"core", "watchlist"}
    limit = int(payload.get("limit", 12))
    candidates = [
        item for item in pool.get("candidates", [])
        if isinstance(item, dict) and str(item.get("state") or "") in states
    ]
    candidates = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:limit]
    if not candidates:
        return _fail(command, payload, ["theme_research_candidates_missing"])
    prompts = []
    for candidate in candidates:
        prompts.append({
            "package": "equity-research",
            "command": "narrative-analysis",
            "symbol": candidate.get("symbol") or candidate.get("code"),
            "name": candidate.get("name"),
            "theme_id": candidate.get("theme_id"),
            "chain_node_id": candidate.get("chain_node_id"),
            "prompt": (
                "Read valuation-model-router.md. Validate theme exposure, evidence, "
                "old/new valuation model, sensitivity, and invalidation conditions."
            ),
        })
    output = _base_output(command, payload)
    output["sources"] = [str(_theme_stock_pool_path())]
    output["result"] = {
        "research_batch": prompts,
        "count": len(prompts),
        "note": "This command prepares research prompts; it does not execute valuation or authorize trades.",
    }
    return output


def _theme_stock_pool_audit(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    pool = _read_json_file(_theme_stock_pool_path(), {})
    if not isinstance(pool, dict) or not isinstance(pool.get("candidates"), list):
        return _fail(command, payload, ["theme_stock_pool_missing"])
    ledger = _read_evidence_ledger()
    evidence_ids = {str(item.get("id")) for item in ledger if isinstance(item, dict) and item.get("id")}
    stale_days = int(payload.get("stale_days", 45))
    now = datetime.now(timezone.utc)
    failures = []
    warnings = []
    for candidate in pool.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        key = _candidate_key(candidate)
        ids = [str(item) for item in candidate.get("evidence_ids", [])] if isinstance(candidate.get("evidence_ids"), list) else []
        missing_ids = [item for item in ids if item not in evidence_ids]
        if candidate.get("state") in {"core", "watchlist"} and not (ids or candidate.get("evidence_quality")):
            failures.append({"candidate": key, "reason": "evidence_missing"})
        if missing_ids:
            warnings.append({"candidate": key, "reason": "evidence_ids_not_in_ledger", "ids": missing_ids})
        last_seen = candidate.get("last_seen_at")
        try:
            last_dt = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
            if (now - last_dt).days > stale_days:
                warnings.append({"candidate": key, "reason": "stale_candidate", "last_seen_at": last_seen})
        except Exception:
            warnings.append({"candidate": key, "reason": "last_seen_at_missing_or_invalid"})
    output = _base_output(command, payload)
    output["sources"] = [str(_theme_stock_pool_path()), str(_evidence_ledger_path())]
    output["warnings"] = [json.dumps(item, ensure_ascii=False) for item in warnings[:20]]
    output["result"] = {
        "ok_to_use_pool": not failures,
        "candidate_count": len(pool.get("candidates", [])),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures[:20],
        "warnings": warnings[:20],
    }
    if failures:
        output["ok"] = False
        output["errors"] = ["theme_stock_pool_audit_failed"]
        output["missing_critical_inputs"] = ["theme_stock_pool_audit_failed"]
        output["freshness"]["status"] = "unavailable"
    return output


def _candidate_score(candidate: dict[str, Any]) -> float:
    return _float(candidate.get("score")) or 0.0


def _days_since(value: Any) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def _market_query_label(market: str) -> str:
    return {
        "CN": "A-share China",
        "HK": "Hong Kong listed",
        "US": "US listed",
        "JP": "Japan listed",
        "KR": "Korea listed",
        "TW": "Taiwan listed",
    }.get(market, market)


def _coverage_search_tasks(plan: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    max_tasks = int(payload.get("max_gap_tasks", 30))
    theme_filter = {str(item) for item in payload.get("theme_ids", [])} if isinstance(payload.get("theme_ids"), list) else set()
    tasks: list[dict[str, Any]] = []
    for node in plan.get("nodes", []) if isinstance(plan.get("nodes"), list) else []:
        if not isinstance(node, dict) or node.get("coverage_kind") != "equity_candidates":
            continue
        if theme_filter and str(node.get("theme_id") or "") not in theme_filter:
            continue
        node_id = str(node.get("node_id") or "")
        node_name = str(node.get("node_name") or node_id)
        for market in node.get("coverage_gaps", []) or []:
            market = str(market).upper()
            tasks.append({
                "theme_id": node.get("theme_id"),
                "node_id": node_id,
                "node_name": node_name,
                "market": market,
                "query": f"AI infrastructure {node_name} {_market_query_label(market)} suppliers revenue orders listed companies",
                "preferred_verification": _recommended_expansion([market]),
                "expected_output": "candidate rows with symbol, region, chain_node_id, claim, source_url, verified_by, verification_scope",
            })
            if len(tasks) >= max_tasks:
                return tasks
    return tasks


def _status_review(candidates: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    stale_days = int(payload.get("stale_days", 45))
    downgrade_score = float(payload.get("downgrade_score", 55))
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        key = _candidate_key(candidate)
        score = _candidate_score(candidate)
        state = str(candidate.get("state") or "candidate")
        evidence_quality = _float(candidate.get("evidence_quality")) or 0.0
        last_days = _days_since(candidate.get("last_seen_at"))
        reasons = []
        suggested = state
        if last_days is None:
            reasons.append("last_seen_at_missing")
            suggested = "candidate" if state in {"core", "watchlist"} else state
        elif last_days > stale_days:
            reasons.append(f"stale>{stale_days}d")
            suggested = "stale"
        if state in {"core", "watchlist"} and evidence_quality <= 0 and not candidate.get("evidence_ids"):
            reasons.append("evidence_missing")
            suggested = "candidate"
        if score < downgrade_score and state in {"core", "watchlist"}:
            reasons.append("score_below_threshold")
            suggested = "candidate"
        if str(candidate.get("relationship_type") or "") == "tourist":
            reasons.append("tourist_exposure")
            suggested = "rejected"
        if reasons:
            items.append({
                "canonical_key": key,
                "name": candidate.get("name"),
                "symbol": candidate.get("symbol") or candidate.get("code"),
                "region": candidate.get("region"),
                "chain_node_id": candidate.get("chain_node_id"),
                "current_state": state,
                "suggested_state": suggested,
                "score": score,
                "reasons": reasons,
            })
    return sorted(items, key=lambda item: (item.get("suggested_state") != "rejected", item.get("score", 0)))


def _layer_score(candidate: dict[str, Any], layer: str) -> float:
    score = _candidate_score(candidate)
    exposure = _float(candidate.get("theme_exposure")) or _float(candidate.get("ai_infra_exposure")) or 0.0
    evidence = _float(candidate.get("evidence_quality")) or 0.0
    bottleneck = _float(candidate.get("bottleneck_score")) or 0.0
    model_shift = _float(candidate.get("model_shift_score")) or 0.0
    forward_pe = _float(candidate.get("forward_pe"))
    relationship = str(candidate.get("relationship_type") or "")
    verified = 10.0 if candidate.get("verified_by") or candidate.get("market_data_verified") else 0.0
    if layer == "valuation_rewrite":
        pe_bonus = 20.0 if forward_pe is not None and forward_pe <= 20 else 8.0 if forward_pe is not None and forward_pe <= 35 else 0.0
        return score * 0.35 + model_shift * 0.25 + evidence * 0.2 + pe_bonus + verified
    if layer == "bottleneck_scarcity":
        rel_bonus = 15.0 if relationship == "bottleneck_supplier" else 8.0 if relationship == "core_beneficiary" else 0.0
        return score * 0.35 + bottleneck * 0.25 + exposure * 0.2 + evidence * 0.1 + rel_bonus
    if layer == "platform_quality":
        rel_bonus = 18.0 if relationship == "platform" else 8.0 if relationship == "core_beneficiary" else 0.0
        return score * 0.45 + exposure * 0.25 + evidence * 0.15 + rel_bonus + verified
    if layer == "diffusion_catchup":
        rel_bonus = 16.0 if relationship in {"derivative_beneficiary", "adjacent"} else 6.0
        return score * 0.3 + exposure * 0.25 + evidence * 0.25 + rel_bonus
    if layer == "cycle_to_infrastructure":
        node = str(candidate.get("chain_node_id") or "")
        node_bonus = 16.0 if any(token in node for token in ("hbm", "dram", "nand", "storage", "pcb", "mlcc", "packaging")) else 0.0
        return score * 0.35 + model_shift * 0.2 + evidence * 0.2 + exposure * 0.15 + node_bonus
    return score


def _layered_theme_rankings(candidates: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    limit = int(payload.get("layer_limit", 10))
    layers = {
        "valuation_rewrite": "dynamic valuation still has room while AI infrastructure exposure is being reclassified",
        "bottleneck_scarcity": "scarce components, materials, capacity, or qualification barriers",
        "platform_quality": "high-quality platform or ecosystem control with strong evidence",
        "diffusion_catchup": "second-order beneficiaries where evidence is improving",
        "cycle_to_infrastructure": "cyclical businesses being repriced as infrastructure bottlenecks",
    }
    ranked: dict[str, list[dict[str, Any]]] = {}
    usable = [item for item in candidates if str(item.get("state") or "") in {"core", "watchlist", "candidate", "validated"}]
    for layer, description in layers.items():
        rows = []
        for candidate in usable:
            rows.append({
                "canonical_key": candidate.get("canonical_key") or _candidate_key(candidate),
                "name": candidate.get("name"),
                "symbol": candidate.get("symbol") or candidate.get("code"),
                "region": candidate.get("region"),
                "chain_node_id": candidate.get("chain_node_id"),
                "state": candidate.get("state"),
                "base_score": _candidate_score(candidate),
                "layer_score": round(_layer_score(candidate, layer), 2),
                "description": description,
            })
        ranked[layer] = sorted(rows, key=lambda item: item.get("layer_score", 0), reverse=True)[:limit]
    return ranked


def _verification_tasks(candidates: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(payload.get("verification_limit", 30))
    tasks: list[dict[str, Any]] = []
    for candidate in candidates:
        gaps = []
        if not candidate.get("verified_by"):
            gaps.append("identity_or_quote_verification")
        if not candidate.get("source_url"):
            gaps.append("source_url")
        if (_float(candidate.get("evidence_quality")) or 0.0) < 60:
            gaps.append("direct_exposure_evidence")
        if not candidate.get("verification_scope"):
            gaps.append("verification_scope")
        if gaps:
            tasks.append({
                "canonical_key": candidate.get("canonical_key") or _candidate_key(candidate),
                "name": candidate.get("name"),
                "symbol": candidate.get("symbol") or candidate.get("code"),
                "region": candidate.get("region"),
                "chain_node_id": candidate.get("chain_node_id"),
                "gaps": gaps,
                "query": f"{candidate.get('name') or candidate.get('symbol')} AI infrastructure revenue orders customer segment disclosure",
            })
            if len(tasks) >= limit:
                break
    return tasks


def _theme_maintenance_review(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    pool = _read_json_file(_theme_stock_pool_path(), {})
    if not isinstance(pool, dict) or not isinstance(pool.get("candidates"), list):
        return _fail(command, payload, ["theme_stock_pool_missing"])
    plan = _read_json_file(_coverage_plan_path(), {})
    if not isinstance(plan, dict) or not plan.get("nodes"):
        return _fail(command, payload, ["coverage_plan_missing"], ["run plan-theme-coverage first"])
    theme_filter = {str(item) for item in payload.get("theme_ids", [])} if isinstance(payload.get("theme_ids"), list) else set()
    candidates = [
        item for item in pool.get("candidates", [])
        if isinstance(item, dict) and (not theme_filter or str(item.get("theme_id") or "") in theme_filter)
    ]
    if not candidates:
        return _fail(command, payload, ["theme_candidates_missing"], ["refresh theme stock pool first"])
    report = {
        "version": 1,
        "updated_at": _now(),
        "theme_ids": sorted(theme_filter) if theme_filter else sorted({str(item.get("theme_id") or "") for item in candidates if item.get("theme_id")}),
        "summary": {
            "candidate_count": len(candidates),
            "coverage_gap_task_count": 0,
            "status_review_count": 0,
            "verification_task_count": 0,
        },
        "coverage_gap_tasks": _coverage_search_tasks(plan, payload),
        "status_review": _status_review(candidates, payload),
        "layered_rankings": _layered_theme_rankings(candidates, payload),
        "verification_tasks": _verification_tasks(candidates, payload),
        "policy": "Research-only maintenance review. It proposes discovery, verification, and status-review tasks; it does not authorize trades or silently mutate candidate states.",
    }
    report["summary"]["coverage_gap_task_count"] = len(report["coverage_gap_tasks"])
    report["summary"]["status_review_count"] = len(report["status_review"])
    report["summary"]["verification_task_count"] = len(report["verification_tasks"])
    _theme_maintenance_review_path().parent.mkdir(parents=True, exist_ok=True)
    _theme_maintenance_review_path().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output = _base_output(command, payload)
    output["sources"] = [str(_theme_stock_pool_path()), str(_coverage_plan_path())]
    output["artifacts"] = [str(_theme_maintenance_review_path())]
    output["warnings"] = [] if not report["status_review"] else ["status_review_actions_present"]
    output["result"] = report
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
    if command == "plan-theme-coverage":
        return _plan_theme_coverage(command, payload)
    if command == "record-theme-candidates":
        return _record_theme_candidates(command, payload)
    if command == "refresh-theme-stock-pool":
        return _refresh_theme_stock_pool(command, payload, base)
    if command == "batch-theme-research":
        return _batch_theme_research(command, payload)
    if command == "theme-stock-pool-audit":
        return _theme_stock_pool_audit(command, payload)
    if command == "theme-maintenance-review":
        return _theme_maintenance_review(command, payload)
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
