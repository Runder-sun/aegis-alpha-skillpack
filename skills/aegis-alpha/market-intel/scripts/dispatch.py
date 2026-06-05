from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.request
import shutil
import subprocess


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    env_path = _workspace_dir() / ".env"
    if not env_path.exists():
        env_path = Path.home() / ".aegis-alpha" / "workspace" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _tavily_search(query: str, limit: int = 5) -> list[dict]:
    api_keys = os.environ.get("TAVILY_API_KEYS") or ""
    if not api_keys:
        return []
    key = api_keys.split(",")[0].strip()
    if not key:
        return []
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "max_results": limit,
    }
    try:
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    results = data.get("results") or []
    out = []
    for item in results:
        if not isinstance(item, dict):
            continue
        out.append({
            "title": item.get("title"),
            "summary": _compact_text(item.get("content"), 200),
            "datetime": item.get("published_date") or "",
            "source": "tavily",
            "url": item.get("url"),
        })
    return out


def _load_latest_prewarm() -> dict:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return {}
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "market-intel",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "market intelligence freshness is inherited from latest prewarm artifact and explicit provider result timestamps",
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
        "note": "Market intelligence evidence is incomplete; do not infer sentiment, event impact, or trading action.",
        "missing_critical_inputs": errors,
    }
    return output


def _normalize_sources(source: Any) -> list[str]:
    if isinstance(source, str) and source:
        return [source]
    if isinstance(source, list):
        return [str(item) for item in source if item]
    return []


def _compact_text(value: str | None, max_len: int = 180) -> str | None:
    if not value:
        return None
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= max_len else text[:max_len] + "…"


def _risk_level_from_snapshot(snapshot: dict) -> tuple[str, str]:
    market = snapshot.get("market") if isinstance(snapshot, dict) else {}
    if not isinstance(market, dict):
        market = {}
    sentiment = market.get("sentiment_index")
    limit_down = market.get("limit_down")
    fried = market.get("fried")

    score = 0
    if isinstance(sentiment, (int, float)):
        if sentiment < 30:
            score += 2
        elif sentiment < 45:
            score += 1
    if isinstance(limit_down, int):
        if limit_down >= 30:
            score += 3
        elif limit_down >= 10:
            score += 2
        elif limit_down >= 5:
            score += 1
    if isinstance(fried, int) and fried >= 30:
        score += 1

    if score >= 4:
        return "🔴严重", "跌停/情绪指标显示风险升温"
    if score >= 3:
        return "🟠高", "跌停/情绪指标偏高"
    if score >= 2:
        return "🟡中", "情绪或跌停指标偏弱"
    return "🟢低", "未见极端风险指标"


def _summarize_sectors(snapshot: dict) -> dict:
    sectors = snapshot.get("sectors") if isinstance(snapshot, dict) else None
    strong = []
    weak = []
    if isinstance(sectors, list):
        for group in sectors:
            if not isinstance(group, dict):
                continue
            label = group.get("label") or ""
            for item in group.get("strong", []) or []:
                if isinstance(item, dict):
                    strong.append({"label": label, **item})
            for item in group.get("weak", []) or []:
                if isinstance(item, dict):
                    weak.append({"label": label, **item})
    return {
        "strong": strong[:10],
        "weak": weak[:10],
    }


def _summarize_hotmoney(snapshot: dict) -> dict:
    hot = snapshot.get("hotmoney") if isinstance(snapshot, dict) else {}
    if not isinstance(hot, dict):
        return {}
    seats = []
    for seat in hot.get("seats", []) or []:
        if not isinstance(seat, dict):
            continue
        stocks = seat.get("stocks") or []
        if isinstance(stocks, list):
            stocks = stocks[:5]
        seats.append({
            "name": seat.get("name"),
            "stocks": stocks,
        })
    return {
        "date": hot.get("date"),
        "total_net_yi": hot.get("total_net_yi"),
        "top_net_buy": hot.get("top_net_buy") or [],
        "seats": seats[:5],
    }


def _next_trading_day(calendar: dict) -> str | None:
    trading_days = calendar.get("trading_days") if isinstance(calendar, dict) else None
    if not isinstance(trading_days, list):
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    for day in trading_days:
        if isinstance(day, str) and day >= today:
            return day
    return None


def _build_result(command: str, prewarm: dict) -> dict:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    news_surface = prewarm.get("news_sentiment") if isinstance(prewarm.get("news_sentiment"), dict) else {}

    snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else {}
    if not snapshot:
        snapshot = prewarm.get("hhxg_snapshot") if isinstance(prewarm.get("hhxg_snapshot"), dict) else {}

    news = news_surface.get("hhxg_news") if isinstance(news_surface.get("hhxg_news"), list) else []
    if not news:
        news = prewarm.get("hhxg_news") if isinstance(prewarm.get("hhxg_news"), list) else []

    calendar = market_data.get("hhxg_calendar") if isinstance(market_data.get("hhxg_calendar"), dict) else {}
    if not calendar:
        calendar = prewarm.get("hhxg_calendar") if isinstance(prewarm.get("hhxg_calendar"), dict) else {}

    tushare_news = news_surface.get("tushare_news") if isinstance(news_surface.get("tushare_news"), list) else []
    if not tushare_news:
        tushare_news = prewarm.get("tushare_news") if isinstance(prewarm.get("tushare_news"), list) else []

    tushare_major_news = news_surface.get("tushare_major_news") if isinstance(news_surface.get("tushare_major_news"), list) else []
    if not tushare_major_news:
        tushare_major_news = prewarm.get("tushare_major_news") if isinstance(prewarm.get("tushare_major_news"), list) else []

    tushare_policy = news_surface.get("tushare_policy") if isinstance(news_surface.get("tushare_policy"), list) else []
    if not tushare_policy:
        tushare_policy = prewarm.get("tushare_policy") if isinstance(prewarm.get("tushare_policy"), list) else []

    tushare_reports = news_surface.get("tushare_research_report") if isinstance(news_surface.get("tushare_research_report"), list) else []
    if not tushare_reports:
        tushare_reports = prewarm.get("tushare_research_report") if isinstance(prewarm.get("tushare_research_report"), list) else []

    tushare_events = news_surface.get("tushare_eco_cal") if isinstance(news_surface.get("tushare_eco_cal"), list) else []
    if not tushare_events:
        tushare_events = prewarm.get("tushare_eco_cal") if isinstance(prewarm.get("tushare_eco_cal"), list) else []

    jin10_news = news_surface.get("jin10_important_news") if isinstance(news_surface.get("jin10_important_news"), list) else []
    if not jin10_news:
        jin10_news = prewarm.get("jin10_important_news") if isinstance(prewarm.get("jin10_important_news"), list) else []

    def _classify_scope(title: str | None, summary: str | None, source: str | None) -> str:
        if source and source.startswith("hhxg"):
            return "a_share"
        text = f"{title or ''} {summary or ''}"
        if not text.strip():
            return "unknown"
        text_l = text.lower()
        a_share_keywords = [
            "a股", "沪深", "上证", "深证", "创业板", "科创板", "北向", "沪股通", "深股通",
            "龙虎榜", "涨停", "跌停", "情绪", "板块", "题材", "游资",
        ]
        china_keywords = [
            "中国", "人民币", "央行", "pboC", "pbc", "国务院", "发改委", "财政部",
            "社融", "m2", "lpr", "shibor", "cpi", "ppi", "pmi", "出口", "进口", "外贸",
            "两会", "人大", "政协", "全国",
        ]
        global_keywords = [
            "美国", "美联储", "fed", "fomc", "非农", "失业", "就业", "cpi", "ppi", "gdp",
            "欧元区", "ecb", "欧洲央行", "日本央行", "boj", "英国央行", "boe",
            "opec", "原油", "wti", "brent", "黄金", "美元指数", "dxy", "国债", "收益率",
            "vix", "risk on", "risk off", "recession", "inflation",
        ]

        def _hit(keywords: list[str]) -> int:
            score = 0
            for kw in keywords:
                if kw.lower() in text_l:
                    score += 1
            return score

        a_share_score = _hit(a_share_keywords)
        china_score = _hit(china_keywords)
        global_score = _hit(global_keywords)

        if a_share_score > 0:
            return "a_share"
        if global_score > china_score and global_score > 0:
            return "global"
        if china_score > 0:
            return "china_macro"
        return "unknown"

    def _classify_region(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["china", "中国", "人民币", "pbo", "pbc", "lpr", "shibor"]):
            return "CN"
        if any(k in t for k in ["united states", "us ", "美国", "fed", "fomc", "treasury"]):
            return "US"
        if any(k in t for k in ["euro", "欧元区", "ecb", "欧洲央行"]):
            return "EU"
        if any(k in t for k in ["japan", "日本", "boj", "tokyo"]):
            return "JP"
        if any(k in t for k in ["uk", "英国", "boe"]):
            return "UK"
        return "Global"

    def _classify_category(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["rate", "利率", "降息", "加息", "fomc", "fed", "央行", "ecb", "boj", "boe"]):
            return "monetary"
        if any(k in t for k in ["cpi", "ppi", "inflation", "通胀", "价格"]):
            return "inflation"
        if any(k in t for k in ["gdp", "pmi", "retail", "消费", "工业", "growth", "增长"]):
            return "growth"
        if any(k in t for k in ["jobs", "payroll", "unemployment", "就业", "失业"]):
            return "labor"
        if any(k in t for k in ["opec", "oil", "原油", "能源", "gas", "commodity", "gold", "黄金"]):
            return "commodities"
        if any(k in t for k in ["war", "conflict", "sanction", "冲突", "制裁", "中东", "地缘"]):
            return "geopolitics"
        if any(k in t for k in ["earnings", "results", "guidance", "财报", "业绩"]):
            return "earnings"
        return "macro"

    def _normalize_news(items: list[dict], source: str) -> list[dict]:
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("headline")
            content = item.get("content") or item.get("summary")
            dt = item.get("datetime") or item.get("issue_date") or item.get("date")
            scope = _classify_scope(title, content, source)
            out.append({
                "title": title,
                "summary": _compact_text(content),
                "datetime": dt,
                "source": source,
                "scope": scope,
            })
        return out

    def _qveris_search(query: str, limit: int = 5) -> dict | None:
        api_key = os.environ.get("QVERIS_API_KEY") or ""
        if not api_key:
            return None
        try:
            req = urllib.request.Request(
                "https://qveris.ai/api/v1/search",
                data=json.dumps({"query": query, "limit": limit}).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _qveris_execute(tool_id: str, params: dict) -> dict | None:
        api_key = os.environ.get("QVERIS_API_KEY") or ""
        if not api_key:
            return None
        try:
            url = f"https://qveris.ai/api/v1/tools/execute?tool_id={tool_id}"
            req = urllib.request.Request(
                url,
                data=json.dumps({"parameters": params, "max_response_size": 8000}).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None
        result = payload.get("result") or {}
        full_url = result.get("full_content_file_url")
        if full_url:
            try:
                with urllib.request.urlopen(full_url, timeout=20) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                return json.loads(content)
            except Exception:
                return None
        return result if isinstance(result, dict) else None

    def _qveris_news_fallback(query: str) -> list[dict]:
        search = _qveris_search(query, limit=5)
        if not isinstance(search, dict):
            return []
        results = search.get("results") or []
        # pick top tool by success_rate
        best = None
        best_score = -1.0
        for tool in results:
            if not isinstance(tool, dict):
                continue
            stats = tool.get("stats") or {}
            score = stats.get("success_rate") or 0
            if score > best_score:
                best = tool
                best_score = score
        if not best:
            return []
        tool_id = best.get("tool_id")
        params = (best.get("examples") or {}).get("sample_parameters") or {}
        if not isinstance(params, dict):
            params = {}
        # try to inject query
        for key in ("query", "q", "keyword", "search", "text"):
            if key in params or key in (best.get("required") or []):
                params[key] = query
                break
        result = _qveris_execute(tool_id, params)
        if not isinstance(result, dict):
            return []
        for key in ("articles", "items", "data", "results"):
            items = result.get(key)
            if isinstance(items, list):
                out = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    out.append({
                        "title": item.get("title") or item.get("headline"),
                        "summary": _compact_text(item.get("summary") or item.get("content") or item.get("description")),
                        "datetime": item.get("published_at") or item.get("datetime") or item.get("date"),
                        "source": "qveris",
                    })
                return out
        return []

    def _xreach_available() -> bool:
        return shutil.which("xreach") is not None

    def _xreach_search(query: str, limit: int = 20) -> list[dict]:
        if not _xreach_available():
            return []
        cmd = ["xreach", "search", query, "-n", str(limit), "--json"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        raw = (proc.stdout or "").strip()
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if isinstance(data, dict) and "tweets" in data:
            data = data.get("tweets")
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append({
                "text": item.get("text") or item.get("content"),
                "author": item.get("author") or item.get("user"),
                "created_at": item.get("created_at") or item.get("time"),
                "url": item.get("url"),
                "source": "xreach",
            })
        return out

    if command == "black-swan-monitor":
        level, reason = _risk_level_from_snapshot(snapshot)
        market = snapshot.get("market") if isinstance(snapshot, dict) else {}
        if not isinstance(market, dict):
            market = {}
        return {
            "risk_level": level,
            "reason": reason,
            "signals": {
                "sentiment_index": market.get("sentiment_index"),
                "limit_down": market.get("limit_down"),
                "fried": market.get("fried"),
                "limit_up": market.get("limit_up"),
            },
            "headlines": (snapshot.get("focus_news") or news)[:5],
            "scope": "A股",
            "source": "hhxg_snapshot",
        }

    if command == "daily-news-scan":
        raw_items = (
            _normalize_news(jin10_news, "jin10.important")
            + _normalize_news(tushare_major_news, "tushare.major_news")
            + _normalize_news(tushare_news, "tushare.news")
        )
        a_share_items = _normalize_news(news, "hhxg_news")
        global_items = [i for i in raw_items if i.get("scope") == "global"]
        china_items = [i for i in raw_items if i.get("scope") == "china_macro"]
        if not global_items:
            global_items = _tavily_search("global macro market news today", limit=6)
        if not global_items:
            global_items = _qveris_news_fallback("global markets news today")
        for item in global_items:
            if isinstance(item, dict):
                item.setdefault("scope", "global")
        return {
            "count": len(a_share_items) + len(global_items),
            "a_share": a_share_items[:20],
            "global": global_items[:20],
            "china_macro": china_items[:20],
            "source": ["hhxg_news", "jin10", "tushare.news", "tushare.major_news", "tavily", "qveris"],
        }

    if command == "forum-sentiment":
        sectors = _summarize_sectors(snapshot)
        return {
            "strong": sectors.get("strong", []),
            "weak": sectors.get("weak", []),
            "source": "hhxg_snapshot.sectors",
        }

    if command == "market-sentiment-index":
        market = snapshot.get("market") if isinstance(snapshot, dict) else {}
        if not isinstance(market, dict):
            market = {}
        return {
            "date": market.get("date"),
            "sentiment_index": market.get("sentiment_index"),
            "sentiment_label": market.get("sentiment_label"),
            "limit_up": market.get("limit_up"),
            "limit_down": market.get("limit_down"),
            "fried": market.get("fried"),
            "promotion_rate": market.get("promotion_rate"),
            "source": "hhxg_snapshot.market",
        }

    if command == "kol-tracker":
        return {
            "hotmoney": _summarize_hotmoney(snapshot),
            "source": "hhxg_snapshot.hotmoney",
        }

    if command == "research-reports":
        reports = []
        for item in tushare_reports:
            if not isinstance(item, dict):
                continue
            reports.append({
                "title": item.get("title"),
                "org": item.get("org_name"),
                "author": item.get("author"),
                "issue_date": item.get("issue_date"),
                "summary": _compact_text(item.get("summary"), 200),
                "ts_code": item.get("ts_code"),
            })
        return {
            "focus_news": (snapshot.get("focus_news") or [])[:10],
            "macro_news": (snapshot.get("macro_news") or [])[:10],
            "research_reports": reports[:20],
            "source": "hhxg_snapshot.focus_news/macro_news + tushare.research_report",
        }

    if command == "event-calendar-scan":
        next_day = _next_trading_day(calendar)
        events = []
        for item in tushare_events:
            if not isinstance(item, dict):
                continue
            events.append({
                "country": item.get("country"),
                "event": item.get("event"),
                "importance": item.get("importance"),
                "report_date": item.get("report_date"),
                "actual": item.get("actual"),
                "forecast": item.get("forecast"),
                "previous": item.get("previous"),
            })
        return {
            "next_trading_day": next_day,
            "has_calendar": bool(calendar),
            "a_share_calendar": calendar,
            "global_events": events[:30],
            "source": "hhxg_calendar + tushare.eco_cal",
        }

    if command == "global-sentiment-scan":
        x_items = _xreach_search("risk off OR recession OR inflation OR rate cut OR rate hike", limit=20)
        q_items = []
        if not x_items:
            for item in _qveris_news_fallback("global macro sentiment risk on risk off"):
                if not isinstance(item, dict):
                    continue
                q_items.append({
                    "text": item.get("title") or item.get("summary"),
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "time": item.get("datetime"),
                    "source": "qveris",
                })
        items = x_items if x_items else q_items
        keyword_hits = {"risk_off": 0, "risk_on": 0, "recession": 0, "inflation": 0}
        for item in items:
            text = (item.get("text") or item.get("title") or "").lower()
            if "risk off" in text or "risk-off" in text:
                keyword_hits["risk_off"] += 1
            if "risk on" in text or "risk-on" in text:
                keyword_hits["risk_on"] += 1
            if "recession" in text:
                keyword_hits["recession"] += 1
            if "inflation" in text:
                keyword_hits["inflation"] += 1
        return {
            "platform": "xreach" if x_items else "qveris",
            "count": len(items),
            "keywords": keyword_hits,
            "items": items[:10],
            "source": "xreach" if x_items else "qveris",
            "note": "no data" if not items else "",
        }

    if command == "global-event-scan":
        events: list[dict] = []
        seen = set()

        def _push_event(title: str | None, summary: str | None, dt: str | None, source: str, scope: str) -> None:
            if scope == "a_share":
                return
            text = f"{title or ''} {summary or ''}".strip()
            if not text:
                return
            key = (title or text)[:80] + "|" + (dt or "")
            if key in seen:
                return
            seen.add(key)
            events.append({
                "title": title or text[:80],
                "summary": _compact_text(summary, 200),
                "datetime": dt,
                "scope": scope,
                "region": _classify_region(text),
                "category": _classify_category(text),
                "source": source,
            })

        # QVeris primary (macro/event search)
        for query in [
            "global macro events calendar this week",
            "central bank meeting schedule",
            "inflation data release date",
            "geopolitical risk events market impact",
        ]:
            for item in _qveris_news_fallback(query):
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                summary = item.get("summary")
                scope = _classify_scope(title, summary, "qveris")
                _push_event(title, summary, item.get("datetime"), "qveris", scope)

        # Agent-reach social signals (macro chatter)
        x_items = _xreach_search("FOMC OR CPI OR payroll OR recession OR rate hike OR rate cut", limit=20)
        for item in x_items:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not text:
                continue
            scope = _classify_scope(text, text, "xreach")
            _push_event(text[:80], text, item.get("time") or item.get("created_at"), "xreach", scope)

        # Jin10 important news (secondary)
        for item in jin10_news[:30]:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            summary = item.get("content")
            scope = _classify_scope(title, summary, "jin10.important")
            _push_event(title, summary, item.get("time"), "jin10.important", scope)

        # Tushare eco calendar (scheduled events, secondary)
        for item in tushare_events:
            if not isinstance(item, dict):
                continue
            title = item.get("event")
            summary = f"{item.get('country') or ''} {item.get('event') or ''} 实际:{item.get('actual')} 预期:{item.get('forecast')} 前值:{item.get('previous')}"
            dt = item.get("report_date")
            _push_event(title, summary, dt, "tushare.eco_cal", "global")

        return {
            "count": len(events),
            "events": events[:30],
            "by_category": {k: len([e for e in events if e.get("category") == k]) for k in {e.get("category") for e in events}},
            "by_region": {k: len([e for e in events if e.get("region") == k]) for k in {e.get("region") for e in events}},
            "source": ["qveris", "xreach", "jin10", "tushare.eco_cal"],
            "note": "no data" if not events else "",
        }

    if command == "policy-analysis":
        policies = []
        for item in tushare_policy:
            if not isinstance(item, dict):
                continue
            policies.append({
                "title": item.get("title"),
                "issue_date": item.get("issue_date"),
                "doc_type": item.get("doc_type"),
                "source": item.get("source"),
                "summary": _compact_text(item.get("content"), 200),
            })
        return {
            "policies": policies[:20],
            "source": "tushare.npr",
        }

    raise ValueError(f"unknown_command:{command}")


def _incomplete_reasons(command: str, result: dict[str, Any]) -> list[str]:
    if command == "black-swan-monitor":
        signals = result.get("signals") if isinstance(result.get("signals"), dict) else {}
        if not any(value is not None for value in signals.values()) and not result.get("headlines"):
            return ["black_swan_inputs_missing"]
    if command == "daily-news-scan":
        if not result.get("count"):
            return ["market_news_missing"]
    if command == "forum-sentiment":
        if not result.get("strong") and not result.get("weak"):
            return ["sector_sentiment_missing"]
    if command == "market-sentiment-index":
        if not any(result.get(key) is not None for key in ("sentiment_index", "limit_up", "limit_down", "fried", "promotion_rate")):
            return ["market_sentiment_inputs_missing"]
    if command == "kol-tracker":
        hotmoney = result.get("hotmoney") if isinstance(result.get("hotmoney"), dict) else {}
        if not hotmoney.get("top_net_buy") and hotmoney.get("total_net_yi") is None and not hotmoney.get("seats"):
            return ["hotmoney_inputs_missing"]
    if command == "research-reports":
        if not result.get("focus_news") and not result.get("macro_news") and not result.get("research_reports"):
            return ["research_report_inputs_missing"]
    if command == "event-calendar-scan":
        if not result.get("has_calendar") and not result.get("global_events"):
            return ["event_calendar_inputs_missing"]
    if command == "global-sentiment-scan":
        if not result.get("count"):
            return ["global_sentiment_inputs_missing"]
    if command == "global-event-scan":
        if not result.get("count"):
            return ["global_event_inputs_missing"]
    if command == "policy-analysis":
        if not result.get("policies"):
            return ["policy_inputs_missing"]
    return []


def _wrap_result(command: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors = _incomplete_reasons(command, result)
    if errors:
        return _fail(command, payload, errors)
    output = _base_output(command, payload)
    output["sources"] = _normalize_sources(result.get("source"))
    output["warnings"] = [result["note"]] if result.get("note") else []
    output["result"] = result
    return output


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
        _load_env()
        prewarm = _load_latest_prewarm()
        result = _build_result(args.command, prewarm)
        output = _wrap_result(args.command, payload, result)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
