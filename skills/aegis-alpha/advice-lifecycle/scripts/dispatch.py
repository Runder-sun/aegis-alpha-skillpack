from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any
import subprocess


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _ensure_repo_src_on_path() -> None:
    # Allow importing ai_invest_openclaw LLM client from repo source
    repo_root = Path(__file__).resolve().parents[5] / "aegis-alpha"
    src_path = repo_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.append(str(src_path))


def _load_env_files(paths: list[Path], override: bool = False) -> None:
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if raw.startswith("export "):
                raw = raw[len("export ") :].strip()
            if "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if value and (value[0] == value[-1]) and value[0] in {"'", '"'}:
                value = value[1:-1]
            if not override and key in os.environ:
                continue
            os.environ[key] = value


def _load_runtime_env() -> None:
    candidates: list[Path] = []
    # Try repo root .env if available
    for parent in Path(__file__).resolve().parents:
        if (parent / "workspace_templates").exists() and (parent / "src").exists():
            candidates.append(parent / ".env")
            break
    candidates.append(_workspace_dir() / ".env")
    _load_env_files(candidates, override=False)


def _read_env(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def _load_latest_prewarm() -> dict:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return dict()
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return dict()
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return dict()


def _load_latest_pipeline_runs(pipeline_id: str, limit: int = 2) -> list[dict]:
    runs_dir = _workspace_dir() / "memory" / "pipeline_runs"
    if not runs_dir.exists():
        return list()
    files = sorted(runs_dir.glob(f"{pipeline_id}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    runs: list[dict] = []
    for path in files[:limit]:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return runs


def _load_theme_store() -> dict:
    path = _workspace_dir() / "memory" / "themes.json"
    if not path.exists():
        return {"global": [], "a_share": [], "resonance": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"global": [], "a_share": [], "resonance": []}
    themes_raw = data.get("themes") if isinstance(data, dict) else None
    if isinstance(themes_raw, dict):
        themes = list(themes_raw.values())
    elif isinstance(themes_raw, list):
        themes = themes_raw
    else:
        themes = []

    def norm_asset(value: Any) -> str:
        if not value:
            return ""
        text = str(value)
        if "A股" in text or text.lower().startswith("a"):
            return "A股"
        if "global" in text.lower() or "全球" in text:
            return "全球"
        return text

    def trim(items: list[dict]) -> list[dict]:
        buckets: dict[str, list] = {}
        for t in items:
            key = f"{t.get('horizon')}"
            buckets.setdefault(key, []).append(t)
        out: list[dict] = []

        def _sort_key(item: dict) -> tuple:
            # Prefer recently updated themes and those with global_link for resonance
            last_seen = item.get("last_seen") or item.get("updated_at") or item.get("started_at") or ""
            score = item.get("score") or 0
            link_boost = 1 if item.get("global_link") else 0
            return (link_boost, last_seen, score)

        for items in buckets.values():
            items.sort(key=_sort_key, reverse=True)
            out.extend(items[:3])
        return out

    global_lines = [t for t in themes if isinstance(t, dict) and norm_asset(t.get("asset_class")) == "全球"]
    a_share_lines = [t for t in themes if isinstance(t, dict) and norm_asset(t.get("asset_class")) == "A股"]

    global_trim = trim(global_lines)
    a_share_trim = trim(a_share_lines)

    def _lifecycle_score(lifecycle: str | None) -> int:
        mapping = {
            "accelerating": 3,
            "peak": 3,
            "emerging": 2,
            "nascent": 1,
            "declining": 0,
        }
        return mapping.get(lifecycle or "", 1)

    resonance: list[dict] = []
    for g in global_trim:
        gname = g.get("name")
        if not gname:
            continue
        related = [a for a in a_share_trim if a.get("global_link") == gname]
        if not related:
            continue
        best = max((_lifecycle_score(a.get("lifecycle")) for a in related), default=1)
        strength = "强" if best >= 3 else "中" if best == 2 else "弱"
        resonance.append({
            "global_mainline": gname,
            "a_share_mainlines": [a.get("name") for a in related if a.get("name")],
            "strength": strength,
        })

    return {"global": global_trim, "a_share": a_share_trim, "resonance": resonance}


def _ensure_theme_store() -> dict:
    return _load_theme_store()


def _resolve_context_path(raw_path: str) -> Path:
    workspace = _workspace_dir().resolve()
    candidate = Path(str(raw_path)).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise SystemExit("context_path_outside_workspace") from exc
    return resolved


def _extract_step_output(results: list[dict], package: str, command: str) -> Any:
    for r in results:
        if r.get("package") == package and r.get("command") == command:
            return r.get("output")
    return None


def _latest_by_month(records: list[dict]) -> dict | None:
    def _month_value(rec: dict) -> str | None:
        for key in ("月份", "month", "日期", "date"):
            value = rec.get(key)
            if value:
                return str(value)
        return None

    def _is_valid(rec: dict) -> bool:
        if "今值" in rec and rec.get("今值") in (None, "", "-", "N/A"):
            return False
        if "nt_val" in rec and rec.get("nt_val") in (None, "", "-", "N/A"):
            return False
        if "ppi_yoy" in rec and rec.get("ppi_yoy") in (None, "", "-", "N/A"):
            return False
        return True

    with_month = [r for r in records if isinstance(r, dict) and _month_value(r)]
    if not with_month:
        return records[-1] if records else None
    ordered = sorted(with_month, key=lambda r: _month_value(r) or "", reverse=True)
    for rec in ordered:
        if _is_valid(rec):
            return rec
    return ordered[0]


def _fmt_ai_summary(summary: object) -> str:
    if isinstance(summary, dict):
        return "；".join([s for s in [
            summary.get("market_state"),
            summary.get("focus_direction"),
            summary.get("theme_focus"),
            summary.get("hotmoney_state"),
            summary.get("news_highlight"),
        ] if s])
    if isinstance(summary, str):
        return summary
    return ""


def _build_data_zone(context_results: list[dict] | None = None) -> dict:
    prewarm = _load_latest_prewarm()
    runs = _load_latest_pipeline_runs("nightly", limit=2)
    current = runs[0] if runs else {}
    previous = runs[1] if len(runs) > 1 else {}

    def _extract_results(run: object) -> list[dict]:
        if not isinstance(run, dict):
            return list()
        if isinstance(run.get("results"), list):
            return run.get("results") or []
        nested = run.get("result") if isinstance(run.get("result"), dict) else {}
        if isinstance(nested.get("results"), list):
            return nested.get("results") or []
        return list()

    results = context_results if isinstance(context_results, list) else _extract_results(current)
    prev_results = _extract_results(previous)

    snapshot = prewarm.get("hhxg_snapshot") if isinstance(prewarm.get("hhxg_snapshot"), dict) else {}
    jin10_extra = prewarm.get("jin10_extra_reports")
    jin10_news = prewarm.get("jin10_important_news")
    theme_store = _ensure_theme_store()
    themesurfer = prewarm.get("themesurfer_signal") if isinstance(prewarm.get("themesurfer_signal"), dict) else {}
    index_daily = prewarm.get("baostock_index_daily")
    index_latest = index_daily[-1] if isinstance(index_daily, list) and index_daily else None

    current_signal = themesurfer.get("data", {}).get("status") if isinstance(themesurfer.get("data"), dict) else None
    prev_signal_raw = _extract_step_output(prev_results, "themesurfer-signal", "signal")
    prev_signal = None
    if isinstance(prev_signal_raw, dict):
        data = prev_signal_raw.get("data") if isinstance(prev_signal_raw.get("data"), dict) else prev_signal_raw
        prev_signal = data.get("status") if isinstance(data, dict) else None

    signal_change = None
    if current_signal and prev_signal and current_signal != prev_signal:
        signal_change = f"ThemeSurfer 信号由 {prev_signal} 变为 {current_signal}"

    def _unwrap(value: Any) -> Any:
        if isinstance(value, dict) and "result" in value:
            return value.get("result")
        return value

    def compact(value: Any) -> Any:
        max_chars = 600
        max_items = 12
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for idx, (k, v) in enumerate(value.items()):
                if idx >= max_items:
                    out["__truncated__"] = True
                    break
                out[k] = compact(v)
            return out
        if isinstance(value, list):
            trimmed = [compact(v) for v in value[:max_items]]
            if len(value) > max_items:
                trimmed.append({"__truncated__": len(value) - max_items})
            return trimmed
        if isinstance(value, str) and len(value) > max_chars:
            return value[:max_chars] + "…"
        return value

    def _month_from_record(rec: dict | None) -> str | None:
        if not isinstance(rec, dict):
            return None
        for key in ("月份", "month", "日期", "date"):
            value = rec.get(key)
            if value:
                return str(value)
        return None

    def _stale_month(month_str: str | None, max_months: int = 18) -> bool:
        if not month_str:
            return True
        import re
        m = re.search(r"(20\\d{2})[^0-9]?([01]?\\d)", month_str)
        if not m:
            return True
        try:
            year = int(m.group(1))
            month = int(m.group(2))
            now = datetime.now()
            delta = (now.year - year) * 12 + (now.month - month)
            return delta > max_months
        except Exception:
            return True

    domestic_macro_raw = _unwrap(_extract_step_output(results, "macro-regime", "domestic-macro"))
    macro_pmi = None
    macro_cpi = None
    macro_ppi = None
    macro_stale = {}
    macro_liquidity = None
    macro_credit = None
    macro_growth = None
    if isinstance(domestic_macro_raw, dict):
        macro_pmi = domestic_macro_raw.get("pmi")
        macro_cpi = domestic_macro_raw.get("cpi")
        macro_ppi = domestic_macro_raw.get("ppi")
        macro_stale = domestic_macro_raw.get("stale") or {}
        macro_liquidity = domestic_macro_raw.get("liquidity")
        macro_credit = domestic_macro_raw.get("credit")
        macro_growth = domestic_macro_raw.get("growth")

    if macro_pmi is None and isinstance(prewarm.get("akshare_macro_pmi_yearly"), list):
        macro_pmi = _latest_by_month(prewarm.get("akshare_macro_pmi_yearly", []))
    if macro_cpi is None and isinstance(prewarm.get("akshare_macro_cpi_monthly"), list):
        macro_cpi = _latest_by_month(prewarm.get("akshare_macro_cpi_monthly", []))
    if macro_ppi is None and isinstance(prewarm.get("akshare_macro_ppi_yearly"), list):
        macro_ppi = _latest_by_month(prewarm.get("akshare_macro_ppi_yearly", []))

    if _stale_month(_month_from_record(macro_pmi)):
        macro_stale.setdefault("pmi", True)
    if _stale_month(_month_from_record(macro_cpi)):
        macro_stale.setdefault("cpi", True)
    if _stale_month(_month_from_record(macro_ppi)):
        macro_stale.setdefault("ppi", True)

    global_macro_raw = _unwrap(_extract_step_output(results, "macro-regime", "global-macro-analysis"))
    if not global_macro_raw:
        global_macro_raw = _unwrap(_extract_step_output(prev_results, "macro-regime", "global-macro-analysis"))

    capital_flow_raw = _unwrap(_extract_step_output(results, "macro-regime", "capital-flow-analysis"))
    if not capital_flow_raw:
        capital_flow_raw = _unwrap(_extract_step_output(prev_results, "macro-regime", "capital-flow-analysis"))

    sector_rotation_raw = _unwrap(_extract_step_output(results, "macro-regime", "sector-rotation"))
    if not sector_rotation_raw:
        sector_rotation_raw = _unwrap(_extract_step_output(prev_results, "macro-regime", "sector-rotation"))

    def _build_mainline_catalog(theme_store_data: dict) -> tuple[dict, dict]:
        if not isinstance(theme_store_data, dict):
            return dict(), dict()

        def _normalize_horizon(line: dict) -> str:
            if not isinstance(line, dict):
                return ""
            horizon = line.get("horizon")
            if horizon in {"long", "medium", "short", "ultra_short"}:
                return horizon
            timeframe = line.get("timeframe") or ""
            mapping = {
                "1-10年": "long",
                "3-12月": "medium",
                "1-3月": "short",
                "1-2周": "ultra_short",
            }
            return mapping.get(timeframe, "")

        def _trim(line: dict) -> dict:
            keep = [
                "name", "horizon", "timeframe", "asset_class", "narrative", "operation",
                "cycle", "lifecycle", "status", "started_at", "start_signal",
                "end_triggers", "end_signal", "evidence", "score", "global_link",
            ]
            return {k: line.get(k) for k in keep if k in line}

        def _group(lines: list[dict]) -> dict:
            buckets: dict[str, list] = {"long": [], "medium": [], "short": [], "ultra_short": []}
            for line in lines:
                horizon = _normalize_horizon(line)
                if not horizon:
                    continue
                buckets[horizon].append(_trim(line))
            # sort by score desc if present
            for key, items in buckets.items():
                items.sort(key=lambda x: x.get("score", 0), reverse=True)
                buckets[key] = items[:3]
            return buckets

        global_lines = theme_store_data.get("global") if isinstance(theme_store_data.get("global"), list) else []
        a_share_lines = theme_store_data.get("a_share") if isinstance(theme_store_data.get("a_share"), list) else []
        catalog = {
            "global": _group(global_lines),
            "a_share": _group(a_share_lines),
            "resonance": theme_store_data.get("resonance") or [],
        }

        def _summarize(lines: list[dict]) -> list[dict]:
            out = []
            for item in lines:
                if not isinstance(item, dict):
                    continue
                out.append({
                    "name": item.get("name"),
                    "narrative": item.get("narrative"),
                    "operation": item.get("operation"),
                    "cycle": item.get("cycle"),
                    "status": item.get("status"),
                    "risk_mode": item.get("risk_mode"),
                    "started_at": item.get("started_at"),
                    "start_signal": item.get("start_signal"),
                    "end_triggers": item.get("end_triggers"),
                    "end_signal": item.get("end_signal"),
                })
            return out

        summary = {"global": {}, "a_share": {}}
        for horizon, lines in (catalog.get("global") or {}).items():
            summary["global"][horizon] = _summarize(lines if isinstance(lines, list) else [])
        for horizon, lines in (catalog.get("a_share") or {}).items():
            summary["a_share"][horizon] = _summarize(lines if isinstance(lines, list) else [])
        summary["resonance"] = catalog.get("resonance") or []
        return catalog, summary

    mainline_catalog, mainline_summary = _build_mainline_catalog(theme_store)

    equity_screening_raw = _unwrap(_extract_step_output(results, "equity-screening", "stock-screening-v2"))
    equity_narrative_raw = _unwrap(_extract_step_output(results, "equity-research", "narrative-analysis"))
    equity_short_term_raw = _unwrap(_extract_step_output(results, "trade-planning", "short-term-analysis"))
    equity_position_raw = _unwrap(_extract_step_output(results, "position-ops", "position-management-v2"))

    def _trim_mainlines(summary: dict, limit: int = 2) -> dict:
        out: dict[str, dict] = {"global": {}, "a_share": {}}
        if not isinstance(summary, dict):
            return out
        for scope in ("global", "a_share"):
            scope_map = summary.get(scope) if isinstance(summary.get(scope), dict) else {}
            if not isinstance(scope_map, dict):
                continue
            for horizon, items in scope_map.items():
                if isinstance(items, list):
                    out[scope][horizon] = items[:limit]
        return out

    def _top_candidates() -> list[dict]:
        pool: list[dict] = []
        if isinstance(equity_short_term_raw, dict):
            pool = equity_short_term_raw.get("candidates") or []
        if not pool and isinstance(equity_screening_raw, dict):
            pool = equity_screening_raw.get("candidates") or []
        def _score_key(item: dict) -> tuple:
            score = item.get("score") if isinstance(item.get("score"), (int, float)) else 0
            net_yi = item.get("net_yi") if isinstance(item.get("net_yi"), (int, float)) else 0
            return (score, net_yi)
        sorted_pool = sorted([p for p in pool if isinstance(p, dict)], key=_score_key, reverse=True)
        out = []
        for item in sorted_pool[:5]:
            out.append({
                "name": item.get("name"),
                "net_yi": item.get("net_yi"),
                "score": item.get("score"),
                "theme": item.get("theme") or item.get("theme_name"),
                "reason": item.get("reason") or item.get("source"),
            })
        return out

    def _top_positions() -> list[dict]:
        positions = []
        if isinstance(equity_position_raw, dict):
            positions = equity_position_raw.get("positions") or []
        clean = [p for p in positions if isinstance(p, dict) and p.get("name")]
        clean.sort(key=lambda x: x.get("pnl_pct") if isinstance(x.get("pnl_pct"), (int, float)) else 0)
        out = []
        for item in clean[:5]:
            out.append({
                "code": item.get("code"),
                "name": item.get("name"),
                "pnl_pct": item.get("pnl_pct"),
                "buy_price": item.get("buy_price"),
                "current_price": item.get("current_price"),
            })
        return out

    market_intel_block = {
        "black_swan_monitor": compact(_unwrap(_extract_step_output(results, "market-intel", "black-swan-monitor"))),
        "daily_news_scan": compact(_unwrap(_extract_step_output(results, "market-intel", "daily-news-scan"))),
        "forum_sentiment": compact(_unwrap(_extract_step_output(results, "market-intel", "forum-sentiment"))),
        "market_sentiment_index": compact(_unwrap(_extract_step_output(results, "market-intel", "market-sentiment-index"))),
        "global_sentiment_scan": compact(_unwrap(_extract_step_output(results, "market-intel", "global-sentiment-scan"))),
        "global_event_scan": compact(_unwrap(_extract_step_output(results, "market-intel", "global-event-scan"))),
        "kol_tracker": compact(_unwrap(_extract_step_output(results, "market-intel", "kol-tracker"))),
        "research_reports": compact(_unwrap(_extract_step_output(results, "market-intel", "research-reports"))),
        "event_calendar_scan": compact(_unwrap(_extract_step_output(results, "market-intel", "event-calendar-scan"))),
        "policy_analysis": compact(_unwrap(_extract_step_output(results, "market-intel", "policy-analysis"))),
    }

    macro_regime_block = {
        "domestic": compact(domestic_macro_raw),
        "global": compact(global_macro_raw),
        "capital_flow": compact(capital_flow_raw),
        "sector_rotation": compact(sector_rotation_raw),
    }

    # Fill global_news from market-intel if macro-regime lacks it
    global_block = macro_regime_block.get("global")
    if isinstance(global_block, dict) and not global_block.get("global_news"):
        merged = []
        event_scan = market_intel_block.get("global_event_scan")
        if isinstance(event_scan, dict):
            for item in (event_scan.get("events") or []):
                if not isinstance(item, dict):
                    continue
                merged.append({
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "datetime": item.get("datetime"),
                    "source": item.get("source") or "market-intel.global-event-scan",
                    "scope": item.get("scope") or "global",
                })
        sent_scan = market_intel_block.get("global_sentiment_scan")
        if isinstance(sent_scan, dict):
            for item in (sent_scan.get("items") or []):
                if not isinstance(item, dict):
                    continue
                merged.append({
                    "title": item.get("text") or item.get("title"),
                    "summary": item.get("text"),
                    "datetime": item.get("time") or item.get("created_at"),
                    "source": item.get("source") or "market-intel.global-sentiment-scan",
                    "scope": "global",
                })
        if merged:
            # de-dup by title
            seen = set()
            uniq = []
            for item in merged:
                key = str(item.get("title") or "")[:80]
                if not key or key in seen:
                    continue
                seen.add(key)
                uniq.append(item)
            global_block = dict(global_block)
            global_block["global_news"] = uniq[:20]
            macro_regime_block["global"] = global_block

    return {
        "snapshot": compact(snapshot),
        "snapshot_summary": _fmt_ai_summary(snapshot.get("ai_summary")),
        "themesurfer_signal": compact(themesurfer),
        "macro": {
            "pmi": macro_pmi,
            "cpi": macro_cpi,
            "ppi": macro_ppi,
            "stale": macro_stale,
            "liquidity": macro_liquidity,
            "credit": macro_credit,
            "growth": macro_growth,
            "jin10_extra": jin10_extra,
        },
        "jin10": {
            "important_news": compact(jin10_news),
        },
        "index_daily": index_latest,
        "market_intel": market_intel_block,
        "macro_regime": macro_regime_block,
        "theme_store": compact(theme_store),
        "mainline_catalog": compact(mainline_catalog),
        "mainline_summary": mainline_summary,
        "mainline_summary_trim": _trim_mainlines(mainline_summary, limit=2),
        "a_share_candidates_top5": _top_candidates(),
        "a_share_positions_top5": _top_positions(),
        "theme_cycle": {
            "discover_themes": compact(_unwrap(_extract_step_output(results, "theme-cycle", "discover-themes"))),
            "sector_cycle_panorama": compact(_unwrap(_extract_step_output(results, "theme-cycle", "sector-cycle-panorama"))),
        },
        "equity": {
            "screening": compact(equity_screening_raw),
            "narrative": compact(equity_narrative_raw),
            "short_term": compact(equity_short_term_raw),
            "position": compact(equity_position_raw),
        },
        "signal_change": signal_change,
    }


def _compute_data_gaps(data_zone: dict) -> list[dict]:
    data_gaps: list[dict] = []

    def _add_gap(field: str, reason: str, sources: list[str]) -> None:
        data_gaps.append({
            "field": field,
            "reason": reason,
            "sources": sources,
        })

    screening = data_zone.get("equity", {}).get("screening") or {}
    global_block = data_zone.get("macro_regime", {}).get("global") if isinstance(data_zone.get("macro_regime"), dict) else None
    domestic_macro = data_zone.get("macro_regime", {}).get("domestic") or {}

    macro_pmi = domestic_macro.get("pmi") if isinstance(domestic_macro, dict) else None
    macro_cpi = domestic_macro.get("cpi") if isinstance(domestic_macro, dict) else None
    macro_ppi = domestic_macro.get("ppi") if isinstance(domestic_macro, dict) else None

    if not isinstance(global_block, dict):
        _add_gap("macro_regime.global", "missing", ["macro-regime::global-macro-analysis"])
    else:
        if not global_block.get("risk_mode"):
            _add_gap("macro_regime.global.risk_mode", "missing", ["macro-regime::global-macro-analysis"])
        if not global_block.get("global_assets"):
            _add_gap("macro_regime.global.global_assets", "missing", ["macro-regime::global-macro-analysis"])
        if not global_block.get("macro_cycle"):
            _add_gap("macro_regime.global.macro_cycle", "missing", ["macro-regime::global-macro-analysis"])
        global_news = global_block.get("global_news")
        event_scan = data_zone.get("market_intel", {}).get("global_event_scan") if isinstance(data_zone.get("market_intel"), dict) else {}
        sentiment_scan = data_zone.get("market_intel", {}).get("global_sentiment_scan") if isinstance(data_zone.get("market_intel"), dict) else {}
        has_event = isinstance(event_scan, dict) and bool(event_scan.get("events"))
        has_sentiment = isinstance(sentiment_scan, dict) and bool(sentiment_scan.get("items"))
        if not global_news and not has_event and not has_sentiment:
            _add_gap("macro_regime.global.global_news", "missing", ["macro-regime::global-macro-analysis (qveris/agent-reach/jin10/tushare)"])
        if not global_block.get("risk_budget"):
            _add_gap("macro_regime.global.risk_budget", "missing", ["macro-regime::global-macro-analysis"])
        if not global_block.get("asset_trends"):
            _add_gap("macro_regime.global.asset_trends", "missing", ["macro-regime::global-macro-analysis (yahoo chart)"])

    if not macro_pmi:
        _add_gap("macro_regime.domestic.pmi", "missing_or_stale", ["macro-regime::domestic-macro (Jin10/Tushare)"])
    if not macro_cpi:
        _add_gap("macro_regime.domestic.cpi", "missing_or_stale", ["macro-regime::domestic-macro (Jin10/Tushare)"])
    if not macro_ppi:
        _add_gap("macro_regime.domestic.ppi", "missing_or_stale", ["macro-regime::domestic-macro (Jin10/Tushare)"])
    if not (domestic_macro.get("liquidity") if isinstance(domestic_macro, dict) else None):
        _add_gap("macro_regime.domestic.liquidity", "missing", ["tushare::macro-cn-m2/macro-cn-shibor/macro-cn-lpr"])
    if not (domestic_macro.get("credit") if isinstance(domestic_macro, dict) else None):
        _add_gap("macro_regime.domestic.credit", "missing", ["tushare::macro-cn-sf"])
    if not (domestic_macro.get("growth") if isinstance(domestic_macro, dict) else None):
        _add_gap("macro_regime.domestic.growth", "missing", ["tushare::macro-cn-gdp"])

    theme_store_global = data_zone.get("theme_store", {}).get("global") if isinstance(data_zone.get("theme_store"), dict) else None
    theme_store_a = data_zone.get("theme_store", {}).get("a_share") if isinstance(data_zone.get("theme_store"), dict) else None
    if not theme_store_global:
        _add_gap("theme_store.global", "missing", ["theme-cycle::mainline-update"])
    if not theme_store_a:
        _add_gap("theme_store.a_share", "missing", ["theme-cycle::mainline-update"])
    if not data_zone.get("theme_store", {}).get("resonance"):
        _add_gap("theme_store.resonance", "missing", ["theme-cycle::mainline-update"])
    if not data_zone.get("mainline_summary"):
        _add_gap("mainline_summary", "missing", ["theme-cycle::mainline-update"])
    else:
        global_catalog = (data_zone.get("mainline_summary") or {}).get("global") if isinstance(data_zone.get("mainline_summary"), dict) else {}
        for horizon in ("long", "medium", "short", "ultra_short"):
            items = global_catalog.get(horizon) if isinstance(global_catalog, dict) else None
            if not items:
                _add_gap(f"mainline_summary.global.{horizon}", "missing", ["theme-cycle::mainline-update"])

    if not data_zone.get("themesurfer_signal"):
        _add_gap("themesurfer_signal", "missing", ["themesurfer-signal::signal"])

    if isinstance(screening, dict) and not screening.get("candidates"):
        _add_gap("equity.screening.candidates", "empty", ["equity-screening::stock-screening-v2", "market-data::snapshot-full"])
    if not data_zone.get("equity", {}).get("narrative"):
        _add_gap("equity.narrative", "missing", ["equity-research::narrative-analysis"])
    if isinstance(data_zone.get("equity", {}).get("position"), dict):
        if (data_zone.get("equity", {}).get("position") or {}).get("count", 0) == 0:
            _add_gap("equity.position", "empty", ["position-ops::position-management-v2 (positions.json/ia-memory)"])

    if not data_zone.get("market_intel", {}).get("market_sentiment_index"):
        _add_gap("market_intel.market_sentiment_index", "missing", ["market-intel::market-sentiment-index"])
    if not data_zone.get("market_intel", {}).get("policy_analysis"):
        _add_gap("market_intel.policy_analysis", "missing", ["market-intel::policy-analysis"])
    if not data_zone.get("market_intel", {}).get("global_sentiment_scan"):
        _add_gap("market_intel.global_sentiment_scan", "missing", ["market-intel::global-sentiment-scan"])
    if not data_zone.get("market_intel", {}).get("global_event_scan"):
        _add_gap("market_intel.global_event_scan", "missing", ["market-intel::global-event-scan"])
    if not data_zone.get("jin10", {}).get("important_news"):
        _add_gap("jin10.important_news", "missing", ["jin10-feed::jin10-snapshot"])

    return data_gaps


def _build_llm_prompt(data_zone: dict) -> tuple[str, str]:
    def _to_text(label: str, value: Any, limit: int = 300) -> str:
        if value is None or value == {} or value == []:
            return f"{label}: 无数据"
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
        if len(text) > limit:
            text = text[:limit] + "…"
        return f"{label}: {text}"

    def _themesurfer_core(raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        if not isinstance(data, dict):
            return raw
        keys = ["symbol", "status", "close", "ma20", "delta", "ma20_ratio", "recent_lockout_days", "recent_full_days"]
        return {k: data.get(k) for k in keys if k in data}

    screening = data_zone.get("equity", {}).get("screening") or {}
    candidates = []
    if isinstance(screening, dict):
        candidates = screening.get("candidates") or []
    candidate_names = [c.get("name") for c in candidates if isinstance(c, dict) and c.get("name")]
    if len(candidate_names) > 8:
        candidate_names = candidate_names[:8]
    candidates_top5 = data_zone.get("a_share_candidates_top5") or []
    positions_top5 = data_zone.get("a_share_positions_top5") or []
    mainline_summary_trim = data_zone.get("mainline_summary_trim") or data_zone.get("mainline_summary")

    global_risk_level = None
    global_block = data_zone.get("macro_regime", {}).get("global")
    if isinstance(global_block, dict):
        global_risk_level = global_block.get("risk_level")
        if not global_risk_level:
            risk_mode = global_block.get("risk_mode")
            if risk_mode == "risk_on":
                global_risk_level = "🟢低"
            elif risk_mode == "risk_off":
                global_risk_level = "🟠高"
            else:
                global_risk_level = "🟡中"
    global_prompt_block = global_block if isinstance(global_block, dict) else {}

    risk_signal = data_zone.get("market_intel", {}).get("black_swan_monitor")
    a_share_risk_level = None
    if isinstance(risk_signal, dict):
        a_share_risk_level = risk_signal.get("risk_level") or risk_signal.get("level")

    domestic_macro = data_zone.get("macro_regime", {}).get("domestic") or {}
    macro_pmi = domestic_macro.get("pmi")
    macro_cpi = domestic_macro.get("cpi")
    macro_ppi = domestic_macro.get("ppi")
    macro_stale = domestic_macro.get("stale") if isinstance(domestic_macro, dict) else {}
    data_gaps = data_zone.get("data_gaps") or []

    data_block = "\n".join([
        _to_text("A股盘后快照摘要(仅限Section5-7)", data_zone.get("snapshot_summary")),
        _to_text("ThemeSurfer", _themesurfer_core(data_zone.get("themesurfer_signal"))),
        _to_text("全球风险等级", global_risk_level or "🟡中"),
        _to_text("全球风险模式", global_prompt_block.get("risk_mode")),
        _to_text("全球宏观周期", global_prompt_block.get("macro_cycle")),
        _to_text("全球资产快照", global_prompt_block.get("global_assets"), limit=500),
        _to_text("全球风险预算", global_prompt_block.get("risk_budget")),
        _to_text("全球资产趋势", global_prompt_block.get("asset_trends"), limit=500),
        _to_text("跨资产组动量", global_prompt_block.get("asset_groups"), limit=400),
        _to_text("全球新闻(仅全球)", global_prompt_block.get("global_news"), limit=800),
        _to_text("全球事件扫描", data_zone.get("market_intel", {}).get("global_event_scan"), limit=800),
        _to_text("主线目录(全球/多周期-摘要, Section3必须使用)", mainline_summary_trim, limit=1800),
        _to_text("主线共振", data_zone.get("theme_store", {}).get("resonance"), limit=600),
        _to_text("A股黑天鹅风险等级(仅限Section5-7)", a_share_risk_level or "无数据"),
        _to_text("A股情绪指数(仅限Section5-7)", data_zone.get("market_intel", {}).get("market_sentiment_index")),
        _to_text("A股新闻扫描(仅限Section5-7)", (data_zone.get("market_intel", {}).get("daily_news_scan") or {}).get("a_share"), limit=600),
        _to_text("候选池名单", candidate_names),
        _to_text("候选Top5(结构化, Section5/7必须优先使用)", candidates_top5, limit=800),
        _to_text("持仓Top5(结构化, Section6必须优先使用)", positions_top5, limit=600),
        _to_text("叙事分析", data_zone.get("equity", {}).get("narrative"), limit=500),
        _to_text("短线分析", data_zone.get("equity", {}).get("short_term"), limit=600),
        _to_text("持仓管理", data_zone.get("equity", {}).get("position"), limit=500),
        _to_text("宏观PMI", macro_pmi),
        _to_text("宏观CPI", macro_cpi),
        _to_text("宏观PPI", macro_ppi),
        _to_text("宏观数据是否过期", macro_stale),
        _to_text("上证指数日线", data_zone.get("index_daily"), limit=400),
        _to_text("信号变化", data_zone.get("signal_change") or "无明显变化"),
        _to_text("数据缺口清单", data_gaps, limit=600),
    ])

    system_prompt = (
        "你是一位机构级投资策略师+短线实战交易员, 负责输出晚间策略报告。"
        "Section 1-4 只允许全球中长线与宏观配置观点, 禁止写A股短线交易建议。"
        "Section 5-7 只允许A股短线交易相关内容。"
        "必须严格基于【数据区】给出的信息, 不能编造任何价格/评分/结论。"
        "A股属于全球权益的一部分, 可在Section 1-4作为区域分支提及,"
        "但严禁使用A股情绪/价格/资金数据去判断全球风险偏好;"
        "全球判断仅使用宏观(全球)/全球资产/全球主线。"
        "主线必须来自【数据区】的投资主线追踪, 禁止自行编造主线。"
        "若关键数据缺失, 必须明确写“数据不足/无数据”, 并列出缺失字段与潜在补充来源。"
        "若数据区包含“候选Top5(结构化)”与“持仓Top5(结构化)”, 必须优先使用它们。"
    )
    user_prompt = f"""请输出晚间策略报告, 格式必须严格按 7 个章节输出, 使用中文。
**必须使用以下标题格式, 且顺序固定:**
### Section 1: 🎯 核心判断（基调 + 关键变量 + 信号变化）
### Section 2: ⚠️ 风险环境（风险等级 + 仓位上限：硬约束）
### Section 3: 🌍 经济环境与配置策略（最核心）
### Section 4: 🌐 全球中长线资产信号（变化驱动 + 配置比例）
### Section 5: 🔍 A股短线扫描（ThemeSurfer + 候选评估）
### Section 6: 📂 推荐持仓管理（按紧迫度）
### Section 7: 📊 次日A股最优持仓（系统执行建议）

**重要定位**:
- Section 1-4 只能写全球中长线与宏观配置, 禁止写A股短线交易建议。
- Section 5-7 只写A股短线交易相关内容。

### Section 1: 🎯 核心判断（基调 + 关键变量 + 信号变化）
- 基调: 一句话总结 (全球风险偏好 + 全球主线 + A股主线(仅作分支参考) + 仓位倾向)
- 关键变量: 1-2 个影响明日决策的变量
- 信号变化: 若有变化用⚠️标注; 若无变化写"无明显变化"

### Section 2: ⚠️ 风险环境（风险等级 + 仓位上限: 硬约束）
- 先给全球风险等级(🟢🟡🟠🔴☠️)及仓位上限
- 若数据区给出风险等级, **必须按以下映射输出仓位上限**:
  🟢≤80% / 🟡≤60% / 🟠≤40% / 🔴≤30% / ☠️=0%
- 若风险等级缺失, 默认🟡并给出保守执行建议
- 可补充A股短线风险提示(不作为全球风险定级依据)
- 明确执行纪律: 是否允许新开仓 / 需要减仓 / 何时解除

### Section 3: 🌍 经济环境与配置策略（最核心）
3.1 环境定位（如: 滞胀/复苏/通缩/过热）+ 证据
3.2 全球主线分层（必须覆盖四个期限, 且必须引用“主线目录(全球/多周期-摘要)”）:
- 长期(1-10年)主线
- 中期(3-12月)主线
- 短期(1-3月)主线
- 超短期(1-2周)主线
每条主线必须包含: 叙事/操作建议/周期判断/起始时间/结束触发
必须使用【数据区】中的“主线目录(全球/多周期-摘要)”，禁止引用原始存档字段
 若某个期限存在>=2条主线，必须输出前2条。
3.3 全球-A股共振: 给出共振强度+仓位建议（共振必须基于主线层级）
3.4 超短期轮动(Theme/板块周期): 萌芽/高潮/退潮

### Section 4: 🌐 全球中长线资产信号（变化驱动 + 配置比例）
- 需要说明配置比例 (总和=100%)
- 若数据区给出 `macro_regime.global.risk_mode`，使用以下模板之一:
  - risk_on: 权益45% / 债券20% / 黄金10% / 商品10% / 现金15%
  - neutral: 权益35% / 债券25% / 黄金10% / 商品10% / 现金20%
  - risk_off: 权益15% / 债券30% / 黄金20% / 商品5% / 现金30%
- 若 risk_mode 缺失, 默认使用 neutral 模板
（提示：risk_mode 在【数据区】的“全球风险模式/宏观(全球)”字段中）

### Section 5: 🔍 A股短线扫描（ThemeSurfer + 候选评估，不给入场价）
- ThemeSurfer 状态解释
- 候选标的评估(最多5只, 若无给出“空仓观望”)
- 若【数据区】中存在“候选Top5(结构化)”，必须以它为准输出；仅当为空才退回“候选池名单”

### Section 6: 📂 推荐持仓管理（按紧迫度）
- 若无持仓数据, 明确写"无持仓数据, 暂不输出"并给出原则
- 若【数据区】中存在“持仓Top5(结构化)”，必须基于其输出

### Section 7: 📊 次日A股最优持仓（系统执行建议）
- 仅基于【数据区】中的持仓/候选池
- 若风险等级为🔴/☠️或LOCKOUT, 明确“不新增标的”
- 若【数据区】中存在“候选Top5(结构化)”且ThemeSurfer=FULL，优先从中选出最多3只
- 若候选池中包含 `net_yi` 字段，优先按 `net_yi` 从高到低排序

【数据区】
{data_block}
"""
    return system_prompt, user_prompt


def _build_section_prompt(section_id: int, data_zone: dict) -> tuple[str, str]:
    section_titles = {
        1: "🎯 核心判断（基调 + 关键变量 + 信号变化）",
        2: "⚠️ 风险环境（风险等级 + 仓位上限：硬约束）",
        3: "🌍 经济环境与配置策略（最核心）",
        4: "🌐 全球中长线资产信号（变化驱动 + 配置比例）",
        5: "🔍 A股短线扫描（ThemeSurfer + 候选评估）",
        6: "📂 推荐持仓管理（按紧迫度）",
        7: "📊 次日A股最优持仓（系统执行建议）",
    }
    title = section_titles.get(section_id, "📋 报告章节")
    system_prompt = (
        "你是机构级投资策略师。你必须严格基于【数据区】给出的信息, 不能编造任何价格/评分/结论。"
        "严禁使用A股数据判断全球风险偏好。"
        "若关键数据缺失, 必须明确写“数据不足/无数据”, 并列出缺失字段与潜在补充来源。"
    )
    section_rules = (
        "Section 1-4 只能写全球中长线与宏观配置, 禁止写A股短线交易建议。\n"
        "Section 5-7 只写A股短线交易相关内容。\n"
        "必须输出单个章节, 格式严格为: ### Section {n}: {title}\n"
    ).format(n=section_id, title=title)
    if section_id == 3:
        section_rules += (
            "Section 3 必须覆盖四个期限的主线判断: 长期(1-10年)、中期(3-12月)、"
            "短期(1-3月)、超短期(1-2周)，并给出全球-A股共振强度。\n"
            "每条主线必须包含: 叙事/操作建议/周期判断/起始时间/结束触发。\n"
            "必须只使用【数据区】中的“主线目录(全球/多周期-摘要)”与主线共振。\n"
            "禁止引用“投资主线追踪(全球-原始存档)”字段。\n"
            "若某一周期主线少于2条, 必须说明原因并指向数据缺口清单。\n"
        )
    if section_id == 2:
        section_rules += (
            "风险等级若存在, 必须按映射给仓位上限: 🟢≤80% / 🟡≤60% / 🟠≤40% / 🔴≤30% / ☠️=0%。\n"
            "若风险等级缺失, 默认🟡并给出保守执行建议。\n"
            "优先使用全球风险等级/全球风险模式作为定级依据; A股黑天鹅仅作短线补充。\n"
        )
    if section_id == 1:
        section_rules += (
            "基调需包含: 全球风险偏好 + 全球主线 + A股主线(仅作分支参考) + 仓位倾向。\n"
        )
    if section_id == 4:
        section_rules += (
            "若数据区给出 macro_regime.global.risk_mode, 使用模板:\n"
            "risk_on: 权益45%/债券20%/黄金10%/商品10%/现金15%\n"
            "neutral: 权益35%/债券25%/黄金10%/商品10%/现金20%\n"
            "risk_off: 权益15%/债券30%/黄金20%/商品5%/现金30%\n"
            "若 risk_mode 缺失, 默认使用 neutral 模板。\n"
        )
    if section_id == 7:
        section_rules += (
            "若候选池中包含 net_yi 字段, 优先按 net_yi 从高到低排序输出最多3只。\n"
        )
    # build compact data block for section prompt
    def _to_text(label: str, value: Any, limit: int = 300) -> str:
        if value is None or value == {} or value == []:
            return f"{label}: 无数据"
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
        if len(text) > limit:
            text = text[:limit] + "…"
        return f"{label}: {text}"

    def _themesurfer_core(raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        if not isinstance(data, dict):
            return raw
        keys = ["symbol", "status", "close", "ma20", "delta", "ma20_ratio", "recent_lockout_days", "recent_full_days"]
        return {k: data.get(k) for k in keys if k in data}

    screening = data_zone.get("equity", {}).get("screening") or {}
    candidates = []
    if isinstance(screening, dict):
        candidates = screening.get("candidates") or []
    candidate_names = [c.get("name") for c in candidates if isinstance(c, dict) and c.get("name")]
    if len(candidate_names) > 8:
        candidate_names = candidate_names[:8]

    global_block = data_zone.get("macro_regime", {}).get("global")
    global_risk_level = None
    if isinstance(global_block, dict):
        global_risk_level = global_block.get("risk_level")
        if not global_risk_level:
            risk_mode = global_block.get("risk_mode")
            if risk_mode == "risk_on":
                global_risk_level = "🟢低"
            elif risk_mode == "risk_off":
                global_risk_level = "🟠高"
            else:
                global_risk_level = "🟡中"
    global_prompt_block = global_block if isinstance(global_block, dict) else {}

    risk_signal = data_zone.get("market_intel", {}).get("black_swan_monitor")
    a_share_risk_level = None
    if isinstance(risk_signal, dict):
        a_share_risk_level = risk_signal.get("risk_level") or risk_signal.get("level")

    domestic_macro = data_zone.get("macro_regime", {}).get("domestic") or {}
    macro_pmi = domestic_macro.get("pmi")
    macro_cpi = domestic_macro.get("cpi")
    macro_ppi = domestic_macro.get("ppi")
    macro_stale = domestic_macro.get("stale") if isinstance(domestic_macro, dict) else {}

    data_block = "\n".join([
        _to_text("A股盘后快照摘要(仅限Section5-7)", data_zone.get("snapshot_summary")),
        _to_text("ThemeSurfer", _themesurfer_core(data_zone.get("themesurfer_signal"))),
        _to_text("全球风险等级", global_risk_level or "🟡中"),
        _to_text("全球风险模式", global_prompt_block.get("risk_mode")),
        _to_text("全球宏观周期", global_prompt_block.get("macro_cycle")),
        _to_text("全球资产快照", global_prompt_block.get("global_assets"), limit=500),
        _to_text("全球资产趋势", global_prompt_block.get("asset_trends"), limit=500),
        _to_text("全球新闻(仅全球)", global_prompt_block.get("global_news"), limit=600),
        _to_text("全球事件扫描", data_zone.get("market_intel", {}).get("global_event_scan"), limit=600),
        _to_text("主线目录(全球/多周期-摘要)", data_zone.get("mainline_summary"), limit=1200),
        _to_text("主线共振", data_zone.get("theme_store", {}).get("resonance"), limit=600),
        _to_text("A股黑天鹅风险等级(仅限Section5-7)", a_share_risk_level or "无数据"),
        _to_text("A股情绪指数(仅限Section5-7)", data_zone.get("market_intel", {}).get("market_sentiment_index")),
        _to_text("A股新闻扫描(仅限Section5-7)", (data_zone.get("market_intel", {}).get("daily_news_scan") or {}).get("a_share"), limit=600),
        _to_text("候选池名单", candidate_names),
        _to_text("叙事分析", data_zone.get("equity", {}).get("narrative"), limit=600),
        _to_text("短线分析", data_zone.get("equity", {}).get("short_term"), limit=600),
        _to_text("持仓管理", data_zone.get("equity", {}).get("position"), limit=600),
        _to_text("宏观PMI", macro_pmi),
        _to_text("宏观CPI", macro_cpi),
        _to_text("宏观PPI", macro_ppi),
        _to_text("宏观数据是否过期", macro_stale),
        _to_text("上证指数日线", data_zone.get("index_daily"), limit=400),
        _to_text("信号变化", data_zone.get("signal_change") or "无明显变化"),
        _to_text("数据缺口清单", data_zone.get("data_gaps") or [], limit=600),
    ])
    user_prompt = f"""请只输出一个章节内容。
{section_rules}
### Section {section_id}: {title}
要求: 内容凝练但完整, 条理清晰, 不要输出其他章节。

【数据区】
{data_block}
"""
    return system_prompt, user_prompt


def _build_morning_prompt(data_zone: dict) -> tuple[str, str]:
    system_prompt = (
        "你是一位实战盘前交易员, 负责输出盘前计划。"
        "必须严格基于【数据区】, 不得编造价格与结论。"
        "严禁使用A股数据判断全球风险偏好。"
    )
    user_prompt = f"""请输出盘前计划, 使用中文, 标题必须包含以下章节顺序:
### Section 1: 🌐 隔夜全球速览
### Section 2: 🧭 今日A股大盘预判
### Section 3: 🧩 中长期主线与共振
### Section 4: 🎯 A股短线计划与风险红线

要求:
- Section 1-3 以全球宏观/资产与中长线为主。
- Section 4 才写A股短线交易计划。
- 若关键数据缺失, 明确写“数据不足/无数据”, 并列出缺失字段与潜在补充来源。

【数据区】
{json.dumps(data_zone, ensure_ascii=False)}
"""
    return system_prompt, user_prompt


def _build_weekly_prompt(data_zone: dict) -> tuple[str, str]:
    system_prompt = (
        "你是一位机构级宏观与资产配置分析师, 负责周度资产报告。"
        "必须严格基于【数据区】, 不得编造价格与结论。"
        "严禁使用A股数据判断全球风险偏好。"
    )
    user_prompt = f"""请输出周报, 使用中文, 标题必须包含以下章节顺序:
### Section 1: 🌍 全球宏观与风险偏好
### Section 2: 🧭 资产配置建议（总和=100%）
### Section 3: 🧩 中期主线与行业方向
### Section 4: 🇨🇳 A股策略与观察池

要求:
- Section 1-3 以全球中长线为主。
- Section 4 仅写A股中期与短线观察。
- 若关键数据缺失, 明确写“数据不足/无数据”, 并列出缺失字段与潜在补充来源。

【数据区】
{json.dumps(data_zone, ensure_ascii=False)}
"""
    return system_prompt, user_prompt


def _build_market_review_prompt(data_zone: dict) -> tuple[str, str]:
    system_prompt = (
        "你是一位盘后复盘分析师, 负责输出盘后复盘报告。"
        "必须严格基于【数据区】, 不得编造价格与结论。"
    )
    user_prompt = f"""请输出盘后复盘, 使用中文, 标题必须包含以下章节顺序:
### Section 1: 🧾 盘后快照与情绪
### Section 2: 🧱 资金与板块结构
### Section 3: 🧭 风险与事件回顾
### Section 4: 🔭 次日关注与策略提示

要求:
- 若关键数据缺失, 明确写“数据不足/无数据”, 并列出缺失字段与潜在补充来源。

【数据区】
{json.dumps(data_zone, ensure_ascii=False)}
"""
    return system_prompt, user_prompt


def _build_prompt_bundle(payload: dict | None = None, section_id: int | None = None, report_kind: str = "nightly") -> dict:
    _load_runtime_env()
    context_results = None
    if isinstance(payload, dict):
        context_results = payload.get("context_results")
        context_path = payload.get("context_path")
        if context_path and not context_results:
            try:
                resolved_context_path = _resolve_context_path(str(context_path))
                raw = json.loads(resolved_context_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    context_results = raw
                elif isinstance(raw, dict):
                    if isinstance(raw.get("result"), dict):
                        context_results = (raw.get("result") or {}).get("results")
                    if context_results is None:
                        context_results = raw.get("results")
                if not isinstance(context_results, list):
                    context_results = None
            except SystemExit:
                raise
            except Exception:
                context_results = None
    data_zone = _build_data_zone(context_results=context_results)
    # compute data gaps once for all prompt variants
    try:
        data_zone["data_gaps"] = _compute_data_gaps(data_zone)
    except Exception:
        data_zone["data_gaps"] = []
    if section_id is not None:
        system_prompt, user_prompt = _build_section_prompt(section_id, data_zone)
    else:
        if report_kind == "morning":
            system_prompt, user_prompt = _build_morning_prompt(data_zone)
        elif report_kind == "weekly":
            system_prompt, user_prompt = _build_weekly_prompt(data_zone)
        elif report_kind == "market-review":
            system_prompt, user_prompt = _build_market_review_prompt(data_zone)
        else:
            system_prompt, user_prompt = _build_llm_prompt(data_zone)
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "data_zone": data_zone,
    }


def _generate_report(bundle: dict, model_override: str | None = None) -> tuple[str | None, str | None]:
    _ensure_repo_src_on_path()
    try:
        from ai_invest_openclaw.agent_runtime.llm_client import generate_report
    except Exception as exc:
        return None, f"llm_import_failed:{exc}"
    system_prompt = bundle.get("system_prompt") or ""
    user_prompt = bundle.get("user_prompt") or ""
    if not system_prompt or not user_prompt:
        return None, "prompt_missing"
    res = generate_report(system_prompt, user_prompt, model_override=model_override)
    if res.ok and res.content:
        return res.content, None
    return None, res.error or "llm_failed"


def load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding='utf-8'))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "advice-lifecycle",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "workspace ledger and supplied payload are current only at command runtime; market freshness is inherited from source artifacts.",
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
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["freshness"]["status"] = "unavailable"
    output["result"] = {
        "note": "Advice lifecycle evidence is incomplete; do not infer, execute, or refresh investment advice.",
        "missing_critical_inputs": errors,
    }
    return output


def _ledger_path() -> Path:
    return _workspace_dir() / "memory" / "advice" / "advice-ledger.json"


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_ledger() -> tuple[dict[str, Any] | None, str | None]:
    path = _ledger_path()
    if not path.exists():
        return None, "advice_ledger_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, "advice_ledger_invalid_json"
    if not isinstance(payload, dict) or not isinstance(payload.get("advices"), list):
        return None, "advice_ledger_invalid_schema"
    payload.setdefault("version", 1)
    return payload, None


def _write_ledger(ledger: dict[str, Any]) -> Path:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = _now()
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _payload_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("recommendations") or payload.get("advices")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    single = payload.get("advice") or payload.get("recommendation")
    if isinstance(single, dict):
        return [single]
    return list()


def _advice_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("code") or item.get("symbol") or item.get("name") or item.get("title") or "").strip()


def _make_advice_id(item: dict[str, Any], index: int) -> str:
    base = _advice_key(item) or f"advice-{index + 1}"
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in base).strip("-").lower()[:40] or f"advice-{index + 1}"
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{stamp}-{index + 1}-{cleaned}"


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        try:
            return datetime.strptime(value.strip()[:10], "%Y-%m-%d")
        except Exception:
            return None


def _investment_advice(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    recommendations = _payload_recommendations(payload)
    if not recommendations:
        raise ValueError("recommendations_required")
    ledger, error = _read_ledger()
    if error == "advice_ledger_missing":
        ledger = {"version": 1, "created_at": _now(), "advices": []}
    elif error:
        raise ValueError(error)
    assert ledger is not None
    existing_ids = {str(item.get("id")) for item in ledger.get("advices", []) if isinstance(item, dict)}
    created = []
    warnings: list[str] = []
    for index, item in enumerate(recommendations):
        key = _advice_key(item)
        thesis = item.get("thesis") or item.get("reason") or item.get("summary")
        if not key and not thesis:
            raise ValueError("recommendation_identity_or_thesis_required")
        advice_id = str(item.get("id") or _make_advice_id(item, index))
        if advice_id in existing_ids:
            warnings.append(f"duplicate_advice_id:{advice_id}")
            continue
        created_at = _now()
        entry_price = _float_or_none(item.get("entry_price") or item.get("price"))
        advice = {
            "id": advice_id,
            "created_at": created_at,
            "updated_at": created_at,
            "status": item.get("status") or "active",
            "code": item.get("code") or item.get("symbol"),
            "name": item.get("name") or item.get("title"),
            "theme": item.get("theme"),
            "thesis": thesis,
            "action_label": item.get("action") or item.get("stance") or "research_watch",
            "entry_price": entry_price,
            "current_price": _float_or_none(item.get("current_price")) or entry_price,
            "valid_until": item.get("valid_until"),
            "invalidation": item.get("invalidation") or item.get("stop_condition"),
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
            "paper_only": True,
            "decision_allowed": False,
            "requires_human_confirmation": True,
            "history": [{
                "at": created_at,
                "event": "created",
                "note": "recorded from explicit payload",
            }],
        }
        ledger["advices"].append(advice)
        existing_ids.add(advice_id)
        created.append(advice)
    path = _write_ledger(ledger)
    return {
        "created": created,
        "created_count": len(created),
        "ledger_count": len(ledger.get("advices", [])),
        "ledger_path": str(path),
    }, [str(path)], warnings, ["payload.recommendations"]


def _advice_history(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    ledger, error = _read_ledger()
    if error:
        raise ValueError(error)
    assert ledger is not None
    advices = [item for item in ledger.get("advices", []) if isinstance(item, dict)]
    status_filter = payload.get("status")
    if status_filter:
        advices = [item for item in advices if item.get("status") == status_filter]
    limit = int(payload.get("limit") or 50)
    return {
        "advices": advices[-limit:],
        "count": len(advices),
        "ledger_path": str(_ledger_path()),
    }, [str(_ledger_path())], [], ["advice-ledger"]


def _advice_update_prices(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    ledger, error = _read_ledger()
    if error:
        raise ValueError(error)
    assert ledger is not None
    prices = payload.get("prices")
    if isinstance(prices, dict):
        price_map = {str(key): value for key, value in prices.items()}
    elif isinstance(prices, list):
        price_map = {}
        for item in prices:
            if isinstance(item, dict):
                key = _advice_key(item)
                if key:
                    price_map[key] = item.get("price") or item.get("current_price")
    else:
        raise ValueError("prices_required")
    updated = []
    unmatched = []
    for advice in ledger.get("advices", []):
        if not isinstance(advice, dict):
            continue
        keys = [str(advice.get(k) or "") for k in ("id", "code", "name")]
        matched_key = next((key for key in keys if key and key in price_map), None)
        if not matched_key:
            continue
        price = _float_or_none(price_map[matched_key])
        if price is None:
            unmatched.append(matched_key)
            continue
        advice["current_price"] = price
        advice["price_updated_at"] = _now()
        advice["updated_at"] = _now()
        history = advice.setdefault("history", [])
        if isinstance(history, list):
            history.append({"at": _now(), "event": "price_update", "price": price})
        updated.append({"id": advice.get("id"), "price": price})
    if not updated:
        raise ValueError("no_matching_advice_for_prices")
    path = _write_ledger(ledger)
    warnings = [f"unmatched_price:{key}" for key in unmatched]
    return {"updated": updated, "updated_count": len(updated), "ledger_path": str(path)}, [str(path)], warnings, ["payload.prices"]


def _update_daily_advice(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    ledger, error = _read_ledger()
    if error:
        raise ValueError(error)
    assert ledger is not None
    updates = payload.get("updates")
    if isinstance(updates, dict):
        updates = [updates]
    if not isinstance(updates, list):
        raise ValueError("updates_required")
    by_id = {str(item.get("id")): item for item in ledger.get("advices", []) if isinstance(item, dict) and item.get("id")}
    applied = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        advice_id = str(update.get("id") or "")
        advice = by_id.get(advice_id)
        if not advice:
            continue
        if update.get("status"):
            advice["status"] = update["status"]
        if update.get("note"):
            history = advice.setdefault("history", [])
            if isinstance(history, list):
                history.append({"at": _now(), "event": "daily_update", "note": update.get("note")})
        advice["updated_at"] = _now()
        applied.append({"id": advice_id, "status": advice.get("status")})
    if not applied:
        raise ValueError("no_matching_advice_for_updates")
    path = _write_ledger(ledger)
    return {"applied": applied, "applied_count": len(applied), "ledger_path": str(path)}, [str(path)], [], ["payload.updates"]


def _advice_expire_check(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    ledger, error = _read_ledger()
    if error:
        raise ValueError(error)
    assert ledger is not None
    now = datetime.utcnow()
    expired = []
    for advice in ledger.get("advices", []):
        if not isinstance(advice, dict):
            continue
        expiry = _parse_date(advice.get("valid_until"))
        if expiry and expiry.replace(tzinfo=None) < now and advice.get("status") == "active":
            expired.append(advice)
            if payload.get("apply"):
                advice["status"] = "expired"
                advice["updated_at"] = _now()
                history = advice.setdefault("history", [])
                if isinstance(history, list):
                    history.append({"at": _now(), "event": "expired"})
    artifacts = []
    if payload.get("apply") and expired:
        artifacts = [str(_write_ledger(ledger))]
    return {
        "expired": expired,
        "expired_count": len(expired),
        "applied": bool(payload.get("apply")),
    }, artifacts, [], ["advice-ledger"]


def _advice_track_report(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    ledger, error = _read_ledger()
    if error:
        raise ValueError(error)
    assert ledger is not None
    rows = []
    for advice in ledger.get("advices", []):
        if not isinstance(advice, dict):
            continue
        entry = _float_or_none(advice.get("entry_price"))
        current = _float_or_none(advice.get("current_price"))
        ret = None
        if entry not in (None, 0) and current is not None:
            ret = round((current / entry - 1) * 100, 2)
        rows.append({
            "id": advice.get("id"),
            "name": advice.get("name"),
            "code": advice.get("code"),
            "status": advice.get("status"),
            "entry_price": entry,
            "current_price": current,
            "return_pct": ret,
            "valid_until": advice.get("valid_until"),
        })
    return {"rows": rows, "count": len(rows), "ledger_path": str(_ledger_path())}, [str(_ledger_path())], [], ["advice-ledger"]


def _advice_track_stats(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str], list[str]]:
    report, artifacts, warnings, sources = _advice_track_report(payload)
    rows = report.get("rows", [])
    returns = [row.get("return_pct") for row in rows if isinstance(row.get("return_pct"), (int, float))]
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    stats = {
        "count": len(rows),
        "status_counts": status_counts,
        "priced_count": len(returns),
        "avg_return_pct": round(sum(returns) / len(returns), 2) if returns else None,
        "positive_count": len([value for value in returns if value > 0]),
        "negative_count": len([value for value in returns if value < 0]),
    }
    return stats, artifacts, warnings, sources


def _wrap_result(command: str, payload: dict[str, Any], result: dict[str, Any], artifacts: list[str] | None = None, warnings: list[str] | None = None, sources: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return _fail(command, payload, ["result_missing"])
    output = _base_output(command, payload)
    output["result"] = result
    output["artifacts"] = artifacts or []
    output["warnings"] = warnings or []
    output["sources"] = sources or []
    output["source"] = sources or []
    data_gaps = []
    prompt = result.get("prompt") if isinstance(result.get("prompt"), dict) else {}
    data_zone = prompt.get("data_zone") if isinstance(prompt.get("data_zone"), dict) else {}
    if isinstance(data_zone.get("data_gaps"), list):
        data_gaps = data_zone.get("data_gaps") or []
    if data_gaps:
        output["warnings"] = sorted(set(output["warnings"] + ["critical_data_gaps_present"]))
        output["missing_critical_inputs"] = data_gaps
        output["freshness"]["status"] = "partial"
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--command', required=True)
    parser.add_argument('--payload', default='{}')
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(package_root)
    available = {c['name'] for c in manifest.get('commands', [])}
    if args.command not in available:
        raise SystemExit(f'unknown command: {args.command}')

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
        artifacts: list[str] = []
        warnings: list[str] = []
        sources: list[str] = []

        if args.command == "investment-advice":
            result, artifacts, warnings, sources = _investment_advice(payload)
        elif args.command == "advice-history":
            result, artifacts, warnings, sources = _advice_history(payload)
        elif args.command == "advice-update-prices":
            result, artifacts, warnings, sources = _advice_update_prices(payload)
        elif args.command == "update-daily-advice":
            result, artifacts, warnings, sources = _update_daily_advice(payload)
        elif args.command == "advice-expire-check":
            result, artifacts, warnings, sources = _advice_expire_check(payload)
        elif args.command == "advice-track-report":
            result, artifacts, warnings, sources = _advice_track_report(payload)
        elif args.command == "advice-track-stats":
            result, artifacts, warnings, sources = _advice_track_stats(payload)
        elif args.command == "nightly-strategy":
            bundle = _build_prompt_bundle(payload, report_kind="nightly")
            report = None
            llm_error = None
            if payload.get("enable_llm"):
                model_override = payload.get("model") or payload.get("llm_model")
                report, llm_error = _generate_report(bundle, model_override=model_override)
            result = {
                "title": "🌙 晚间策略报告",
                "prompt": bundle,
                "report": report,
                "llm_error": llm_error,
            }
            sources = ["pipeline-runs/prewarm/theme-store"]
        elif args.command == "nightly-section":
            section_id = payload.get("section_id")
            if not isinstance(section_id, int):
                raise ValueError("section_id_required")
            bundle = _build_prompt_bundle(payload, section_id=section_id)
            report = None
            llm_error = None
            if payload.get("enable_llm"):
                model_override = payload.get("model") or payload.get("llm_model")
                report, llm_error = _generate_report(bundle, model_override=model_override)
            result = {
                "title": f"🌙 晚间策略 Section {section_id}",
                "prompt": bundle,
                "report": report,
                "llm_error": llm_error,
            }
            sources = ["pipeline-runs/prewarm/theme-store"]
        elif args.command == "morning-briefing":
            bundle = _build_prompt_bundle(payload, report_kind="morning")
            result = {
                "title": "🌅 盘前计划",
                "prompt": bundle,
            }
            sources = ["pipeline-runs/prewarm/theme-store"]
        elif args.command == "weekly-asset-report":
            bundle = _build_prompt_bundle(payload, report_kind="weekly")
            result = {
                "title": "📆 周报资产配置",
                "prompt": bundle,
            }
            sources = ["pipeline-runs/prewarm/theme-store"]
        elif args.command == "market-review":
            bundle = _build_prompt_bundle(payload, report_kind="market-review")
            result = {
                "title": "🧾 盘后复盘",
                "prompt": bundle,
            }
            sources = ["pipeline-runs/prewarm/theme-store"]
        else:
            raise ValueError(f"unknown_command:{args.command}")
        output = _wrap_result(args.command, payload, result, artifacts=artifacts, warnings=warnings, sources=sources)
    except ValueError as exc:
        output = _fail(args.command, payload, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
