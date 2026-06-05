from __future__ import annotations

import argparse
import json
import os
import time
import contextlib
import io
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
import urllib.error


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _macro_cache_path() -> Path:
    return _workspace_dir() / "memory" / "macro_cache.json"


def _global_macro_cache_path() -> Path:
    return _workspace_dir() / "memory" / "global_macro_cache.json"


def _load_macro_cache() -> dict | None:
    path = _macro_cache_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_macro_cache(payload: dict) -> None:
    path = _macro_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _load_global_macro_cache(max_age_sec: int = 6 * 3600) -> dict | None:
    path = _global_macro_cache_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = payload.get("_ts")
    if isinstance(ts, (int, float)) and (time.time() - ts) <= max_age_sec:
        return payload.get("data")
    return None


def _save_global_macro_cache(payload: dict) -> None:
    path = _global_macro_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps({"_ts": time.time(), "data": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return

def _load_env():
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


def _http_get(url: str, timeout: int = 12) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def _qveris_search(query: str, limit: int = 5) -> dict | None:
    api_key = os.environ.get("QVERIS_API_KEY") or ""
    if not api_key:
        return None
    payload = {
        "query": query,
        "limit": limit,
        "toolType": "news",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://qveris.ai/api/v1/search",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def _qveris_execute_legacy(tool_id: str, params: dict) -> dict | None:
    api_key = os.environ.get("QVERIS_API_KEY") or ""
    if not api_key:
        return None
    payload = {"params": params}
    data = json.dumps(payload).encode("utf-8")
    url = f"https://qveris.ai/api/v1/tools/execute?tool_id={tool_id}"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def _qveris_news_fallback(query: str) -> list[dict]:
    search = _qveris_search(query, limit=5)
    if not isinstance(search, dict):
        return []
    tools = search.get("tools") or []
    if not tools:
        return []
    tool_id = tools[0].get("tool_id") or tools[0].get("id")
    if not tool_id:
        return []
    params = {"query": query, "limit": 10}
    result = _qveris_execute_legacy(tool_id, params)
    if not isinstance(result, dict):
        return []
    items = result.get("data") or result.get("result") or result.get("items")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append({
            "title": item.get("title") or item.get("headline"),
            "summary": item.get("summary") or item.get("content"),
            "datetime": item.get("datetime") or item.get("time"),
            "source": "qveris",
        })
    return out


def _xreach_available() -> bool:
    return shutil.which("xreach") is not None


def _xreach_search(query: str, limit: int = 20) -> list[dict]:
    if not _xreach_available():
        return []
    cmd = ["xreach", "search", query, "-n", str(limit), "--json"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False, timeout=20)
    except Exception:
        return []
    if res.returncode != 0:
        return []
    try:
        payload = json.loads(res.stdout.strip())
    except Exception:
        return []
    if isinstance(payload, list):
        return payload
    return payload.get("data") if isinstance(payload, dict) else []


def _finnhub_candles(symbol: str, days: int = 120, timeout: int = 12) -> list[float]:
    api_key = os.environ.get("FINNHUB_API_KEY") or ""
    if not api_key:
        return []
    to_ts = int(time.time())
    from_ts = to_ts - days * 24 * 3600
    if symbol.startswith("BINANCE:"):
        url = f"https://finnhub.io/api/v1/crypto/candle?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}&token={api_key}"
    else:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}&token={api_key}"
    status, body = _http_get(url, timeout=timeout)
    if status != 200:
        return []
    try:
        payload = json.loads(body)
    except Exception:
        return []
    if payload.get("s") != "ok":
        return []
    closes = payload.get("c") or []
    return [float(x) for x in closes if isinstance(x, (int, float))]


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _calc_change(latest: float | None, prev: float | None) -> tuple[float | None, float | None]:
    if latest is None or prev in (None, 0):
        return None, None
    change = latest - prev
    pct = change / prev * 100 if prev else None
    return change, pct


def _quote_from_df(df, value_col: str) -> dict | None:
    if df is None or getattr(df, "empty", True):
        return None
    if value_col not in df.columns:
        return None
    tail = df.tail(2)
    if tail.shape[0] < 2:
        return None
    latest = _safe_float(tail[value_col].iloc[-1])
    prev = _safe_float(tail[value_col].iloc[-2])
    if latest is None or prev is None:
        return None
    change, pct = _calc_change(latest, prev)
    return {
        "price": latest,
        "change": change,
        "pct": pct,
        "prev_close": prev,
    }


def _akshare_index_us(symbol: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.index_us_stock_sina(symbol=symbol)
    except Exception:
        return None
    return _quote_from_df(df, "close")


def _akshare_index_global_sina(name: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.index_global_hist_sina(symbol=name)
    except Exception:
        return None
    return _quote_from_df(df, "close")


def _akshare_index_global_em(name: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.index_global_hist_em(symbol=name)
    except Exception:
        return None
    # EM uses 最新价
    return _quote_from_df(df, "最新价")


def _akshare_hk_index(symbol: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.stock_hk_index_daily_sina(symbol=symbol)
    except Exception:
        return None
    return _quote_from_df(df, "close")


def _akshare_forex(symbol: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.forex_hist_em(symbol=symbol)
    except Exception:
        return None
    return _quote_from_df(df, "最新价")


def _akshare_futures_foreign(symbol: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.futures_foreign_hist(symbol=symbol)
    except Exception:
        return None
    return _quote_from_df(df, "close")


def _akshare_bond_us(tenor: str) -> dict | None:
    try:
        import akshare as ak
    except Exception:
        return None
    col_map = {
        "10Y": "美国国债收益率10年",
        "5Y": "美国国债收益率5年",
    }
    col = col_map.get(tenor)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.bond_zh_us_rate()
    except Exception:
        return None
    if col not in df.columns:
        return None
    return _quote_from_df(df, col)

def _qveris_execute_v2(tool_id: str, params: dict, timeout: int = 20) -> dict | None:
    api_key = os.environ.get("QVERIS_API_KEY") or ""
    if not api_key:
        return None
    url = f"https://qveris.ai/api/v1/tools/execute?tool_id={tool_id}"
    body = {"parameters": params, "max_response_size": 4000}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    result = payload.get("result") or {}
    full_url = result.get("full_content_file_url")
    if full_url:
        try:
            with urllib.request.urlopen(full_url, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            return json.loads(content)
        except Exception:
            return None
    return result if isinstance(result, dict) else None


def _extract_latest(series: list[dict]) -> tuple[str | None, float | None]:
    for row in series:
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        if value in (None, ".", ""):
            continue
        try:
            return str(row.get("date") or row.get("timestamp") or ""), float(value)
        except Exception:
            continue
    return None, None


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "→"
    last = values[0]
    prev = values[1]
    if last > prev * 1.002:
        return "↑"
    if last < prev * 0.998:
        return "↓"
    return "→"


def _build_global_macro() -> dict:
    cached = _load_global_macro_cache()
    if cached:
        return cached

    _load_env()
    data: dict[str, dict] = {}
    # Alphavantage via QVeris
    tool_map = {
        "us_cpi": ("alphavantage.economic.cpi.retrieve.v1.7aca3c4a", {"interval": "monthly"}),
        "us_unemployment": ("alphavantage.unemployment.retrieve.v1.7aca3c4a", {"function": "UNEMPLOYMENT"}),
        "us_nonfarm": ("alphavantage.nonfarm_payroll.retrieve.v1.7aca3c4a", {"function": "NONFARM_PAYROLL"}),
        "us_retail_sales": ("alphavantage.retail_sales.retrieve.v1.7aca3c4a", {"function": "RETAIL_SALES"}),
        "us_10y_yield": ("alphavantage.economic.treasury_yield.retrieve.v1.7aca3c4a", {"function": "TREASURY_YIELD", "interval": "daily", "maturity": "10year"}),
        "global_commodities": ("alphavantage.commodities.all_commodities.retrieve.v1.7aca3c4a", {"function": "ALL_COMMODITIES", "interval": "monthly"}),
    }

    for key, (tool_id, params) in tool_map.items():
        result = _qveris_execute_v2(tool_id, params)
        if not isinstance(result, dict):
            continue
        series = result.get("data")
        if not isinstance(series, list):
            continue
        latest_date, latest_value = _extract_latest(series)
        trend = _trend([float(r.get("value")) for r in series[:3] if isinstance(r, dict) and r.get("value") not in (None, ".", "")])
        data[key] = {
            "latest_date": latest_date,
            "latest": latest_value,
            "trend": trend,
            "unit": result.get("unit"),
        }

    # AkShare fallback for US macro series when QVeris is missing/unavailable
    def _akshare_macro_series(func_name: str) -> dict | None:
        try:
            import akshare as ak
        except Exception:
            return None
        func = getattr(ak, func_name, None)
        if not callable(func):
            return None
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                df = func()
        except Exception:
            return None
        if df is None or getattr(df, "empty", True):
            return None
        date_col = None
        for col in df.columns:
            if col in ("日期", "时间", "date"):
                date_col = col
                break
        if not date_col:
            date_col = df.columns[0]
        value_col = None
        for col in df.columns:
            if col in ("今值", "现值", "最新值", "value", "值"):
                value_col = col
                break
        if not value_col and len(df.columns) > 1:
            value_col = df.columns[1]
        if not value_col:
            return None
        series_df = df[[date_col, value_col]].dropna()
        if series_df.empty:
            return None
        tail = series_df.tail(3)
        values = [ _safe_float(v) for v in tail[value_col].tolist() ]
        values = [v for v in values if v is not None]
        if not values:
            return None
        values = list(reversed(values))
        latest_date = str(tail[date_col].iloc[-1])
        latest_value = values[0]
        trend = _trend(values)
        return {
            "latest_date": latest_date,
            "latest": latest_value,
            "trend": trend,
            "unit": None,
            "source": f"akshare.{func_name}",
        }

    if "us_cpi" not in data:
        rec = _akshare_macro_series("macro_usa_cpi_monthly")
        if rec:
            data["us_cpi"] = rec
    if "us_unemployment" not in data:
        rec = _akshare_macro_series("macro_usa_unemployment_rate")
        if rec:
            data["us_unemployment"] = rec
    if "us_10y_yield" not in data:
        rec = _akshare_bond_us("10Y")
        if rec:
            data["us_10y_yield"] = {
                "latest_date": datetime.now().strftime("%Y-%m-%d"),
                "latest": rec.get("price"),
                "trend": "↑" if (rec.get("pct") or 0) > 0.05 else "↓" if (rec.get("pct") or 0) < -0.05 else "→",
                "unit": "%",
                "source": "akshare.bond_zh_us_rate",
            }

    _save_global_macro_cache(data)
    return data


def _jin10_report(attr_id: str, symbol: str, timeout: int = 10) -> list[dict]:
    url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = {
        "category": "ec",
        "attr_id": attr_id,
        "max_date": "",
        "_": str(int(datetime.now().timestamp() * 1000)),
    }
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={
            "user-agent": "Mozilla/5.0",
            "x-app-id": "rU6QIu7JHe2gOUeR",
            "x-csrf-token": "x-csrf-token",
            "x-version": "1.0.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    values = data.get("data", {}).get("values") or []
    records = []
    for row in values:
        if not isinstance(row, list) or len(row) < 4:
            continue
        date = str(row[0])
        month = date[:7] if len(date) >= 7 else date
        records.append({
            "月份": month,
            "日期": date,
            "今值": row[1],
            "预测值": row[2],
            "前值": row[3],
            "商品": symbol,
        })
    return records


def _finnhub_quote(symbol: str) -> dict | None:
    api_key = os.environ.get("FINNHUB_API_KEY") or ""
    if not api_key:
        return None
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
    status, body = _http_get(url)
    if status != 200:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("c") in (None, 0):
        return None
    return data


def _yahoo_quotes(symbols: list[str], timeout: int = 12) -> dict[str, dict]:
    if not symbols:
        return {}
    url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + ",".join(symbols)
    status, body = _http_get(url, timeout=timeout)
    if status != 200:
        return {}
    try:
        payload = json.loads(body)
    except Exception:
        return {}
    results = payload.get("quoteResponse", {}).get("result") or []
    out: dict[str, dict] = {}
    for row in results:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol")
        if not symbol:
            continue
        price = row.get("regularMarketPrice")
        prev = row.get("regularMarketPreviousClose")
        change = row.get("regularMarketChange")
        pct = row.get("regularMarketChangePercent")
        if price in (None, 0):
            continue
        out[symbol] = {
            "price": price,
            "prev_close": prev,
            "change": change,
            "pct": pct,
        }
    return out


def _classify_scope(title: str | None, summary: str | None, source: str | None) -> str:
    text = f"{title or ''} {summary or ''}"
    if not text.strip():
        return "unknown"
    text_l = text.lower()
    a_share_keywords = [
        "a股", "沪深", "上证", "深证", "创业板", "科创板", "北向", "沪股通", "深股通",
        "龙虎榜", "涨停", "跌停", "题材", "板块", "游资",
    ]
    china_keywords = [
        "中国", "人民币", "央行", "pboC", "pbc", "国务院", "发改委", "财政部",
        "社融", "m2", "lpr", "shibor", "cpi", "ppi", "pmi", "出口", "进口", "外贸",
        "两会", "人大", "政协", "全国",
    ]
    global_keywords = [
        "美国", "美联储", "fed", "fomc", "非农", "失业", "就业", "cpi", "ppi", "gdp",
        "欧元区", "欧洲", "ecb", "欧洲央行", "日本", "日本央行", "boj", "英国", "英国央行", "boe",
        "德国", "法国", "意大利", "印度", "巴西", "加拿大",
        "国际", "全球", "海外", "美元", "美元指数", "dxy", "美债", "国债", "收益率",
        "opec", "原油", "wti", "brent", "黄金", "铜", "大宗商品",
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


def _yahoo_chart(symbol: str, range_: str = "3mo", interval: str = "1d", timeout: int = 12) -> list[float]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
    status, body = _http_get(url, timeout=timeout)
    if status != 200:
        return []
    try:
        payload = json.loads(body)
    except Exception:
        return []
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return []
    indicators = result[0].get("indicators") or {}
    quotes = indicators.get("quote") or []
    if not quotes:
        return []
    closes = quotes[0].get("close") or []
    series = [float(x) for x in closes if isinstance(x, (int, float))]
    return series


def _trend_from_series(series: list[float]) -> dict:
    if len(series) < 25:
        return {}
    close = series[-1]
    ma20 = sum(series[-20:]) / 20.0
    ret20 = (close / series[-20] - 1) * 100 if series[-20] else 0
    ret5 = (close / series[-5] - 1) * 100 if series[-5] else 0
    trend = "up" if close > ma20 and ret20 > 0 else "down" if close < ma20 and ret20 < 0 else "sideways"
    return {
        "close": round(close, 4),
        "ma20": round(ma20, 4),
        "ret5": round(ret5, 2),
        "ret20": round(ret20, 2),
        "trend": trend,
    }


def _build_macro_cycle(global_macro: dict) -> tuple[str, str]:
    cpi_trend = (global_macro.get("us_cpi") or {}).get("trend")
    unemp_trend = (global_macro.get("us_unemployment") or {}).get("trend")
    if cpi_trend == "↑" and unemp_trend == "↑":
        return "stagflation", "通胀上行 + 失业上行"
    if cpi_trend == "↓" and unemp_trend == "↑":
        return "disinflation_slowdown", "通胀下行 + 失业上行"
    if cpi_trend == "↑" and unemp_trend == "↓":
        return "reflation_overheat", "通胀上行 + 失业下行"
    if cpi_trend == "↓" and unemp_trend == "↓":
        return "soft_landing_recovery", "通胀下行 + 失业下行"
    return "neutral", "趋势混合/不显著"

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
        "package": "macro-regime",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "macro-regime freshness is inherited from latest prewarm artifact, macro cache, and explicit provider timestamps",
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
        "note": "Macro evidence is incomplete; do not infer a market regime or portfolio action.",
        "missing_critical_inputs": errors,
    }
    return output


def _extract_snapshot(prewarm: dict[str, Any]) -> dict[str, Any]:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    snapshot = prewarm.get("hhxg_snapshot") if isinstance(prewarm.get("hhxg_snapshot"), dict) else {}
    if not snapshot:
        snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else {}
    return snapshot if isinstance(snapshot, dict) else {}


def _normalize_sources(source: Any) -> list[str]:
    if isinstance(source, str) and source:
        return [source]
    if isinstance(source, list):
        return [str(item) for item in source if item]
    return []


def _parse_month(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.isdigit() and len(raw) == 6:
        return f"{raw[:4]}-{raw[4:]}"
    cleaned = raw.replace("年", "-").replace("月", "").replace("份", "").replace(" ", "")
    if len(cleaned) >= 7 and cleaned[4] == "-":
        return cleaned[:7]
    import re
    m = re.search(r"(20\\d{2})[^0-9]?([01]?\\d)", cleaned)
    if m:
        year = m.group(1)
        month = m.group(2).zfill(2)
        return f"{year}-{month}"
    return None


def _parse_quarter(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    raw = value.strip().upper()
    if "Q" in raw:
        try:
            year = int(raw.split("Q")[0])
            q = int(raw.split("Q")[1])
            if 1 <= q <= 4:
                return year, q
        except Exception:
            return None
    return None


def _stale(month_str: str | None, max_months: int = 12) -> bool:
    if not month_str:
        return True
    try:
        if len(month_str) >= 7:
            month = datetime.strptime(month_str[:7], "%Y-%m")
        else:
            month = datetime.strptime(month_str, "%Y-%m")
    except Exception:
        return True
    delta = (datetime.now().year - month.year) * 12 + (datetime.now().month - month.month)
    return delta > max_months


def _stale_quarter(q_value: Any, max_quarters: int = 6) -> bool:
    parsed = _parse_quarter(q_value) if isinstance(q_value, str) else None
    if not parsed:
        return True
    year, quarter = parsed
    now = datetime.now()
    now_q = (now.month - 1) // 3 + 1
    delta_q = (now.year - year) * 4 + (now_q - quarter)
    return delta_q > max_quarters


def _tushare_query(api_name: str, fields: str, params: dict) -> list[dict]:
    token = os.environ.get("TUSHARE_TOKEN") or ""
    if not token:
        return []
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": fields,
    }
    status, body = _http_get("http://api.tushare.pro", timeout=15) if False else (None, "")
    try:
        req = urllib.request.Request(
            "http://api.tushare.pro",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    if data.get("code") != 0:
        return []
    payload = data.get("data") or {}
    fields_list = payload.get("fields") or []
    items = payload.get("items") or []
    if not fields_list or not items:
        return []
    records = []
    for row in items:
        if not isinstance(row, list):
            continue
        records.append(dict(zip(fields_list, row)))
    return records


def _latest_by_key(records: list[dict], key: str) -> dict | None:
    with_key = [r for r in records if isinstance(r, dict) and r.get(key)]
    if not with_key:
        return records[-1] if records and isinstance(records[-1], dict) else None
    return sorted(with_key, key=lambda r: str(r.get(key)), reverse=True)[0]


def _build_domestic_macro(prewarm: dict) -> dict:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    pmi = prewarm.get("akshare_macro_pmi_yearly") or prewarm.get("akshare_macro_pmi") or market_data.get("akshare_macro_pmi_yearly") or market_data.get("akshare_macro_pmi") or []
    non_man = prewarm.get("akshare_macro_non_man_pmi") or market_data.get("akshare_macro_non_man_pmi") or []
    cpi = prewarm.get("akshare_macro_cpi_monthly") or prewarm.get("akshare_macro_cpi") or market_data.get("akshare_macro_cpi_monthly") or market_data.get("akshare_macro_cpi") or []
    ppi = prewarm.get("akshare_macro_ppi_yearly") or prewarm.get("akshare_macro_ppi") or market_data.get("akshare_macro_ppi_yearly") or market_data.get("akshare_macro_ppi") or []

    # If prewarm failed, fetch directly from Jin10 (with timeout)
    if not pmi or not cpi or not ppi:
        try:
            if not pmi:
                pmi = _jin10_report("65", "中国官方制造业PMI")
            if not non_man:
                non_man = _jin10_report("75", "中国官方非制造业PMI")
            if not cpi:
                cpi = _jin10_report("72", "中国CPI月率")
            if not ppi:
                ppi = _jin10_report("60", "中国PPI年率")
        except Exception:
            pass

    def latest_by_month(records: list) -> dict | None:
        with_month = [r for r in records if isinstance(r, dict) and r.get("月份")]
        if not with_month:
            return records[-1] if records and isinstance(records[-1], dict) else None
        def _missing_value(rec: dict | None) -> bool:
            if not isinstance(rec, dict):
                return True
            value = rec.get("今值")
            return value in (None, "", ".", "nan")
        with_value = [r for r in with_month if not _missing_value(r)]
        pool = with_value or with_month
        return sorted(pool, key=lambda r: str(r.get("月份")), reverse=True)[0]

    def _missing_value(rec: dict | None) -> bool:
        if not isinstance(rec, dict):
            return True
        value = rec.get("今值")
        return value in (None, "", ".", "nan")

    pmi_latest = latest_by_month(pmi)
    non_man_latest = latest_by_month(non_man)
    cpi_latest = latest_by_month(cpi)
    ppi_latest = latest_by_month(ppi)

    def pick_month(rec: dict | None) -> str | None:
        if not isinstance(rec, dict):
            return None
        return _parse_month(rec.get("月份") or rec.get("month") or rec.get("日期"))

    pmi_month = pick_month(pmi_latest)
    non_man_month = pick_month(non_man_latest)
    cpi_month = pick_month(cpi_latest)
    ppi_month = pick_month(ppi_latest)

    if pmi and cpi and ppi and not (_stale(pmi_month) or _stale(cpi_month) or _stale(ppi_month)):
        _save_macro_cache({
            "pmi_yearly": pmi,
            "non_man_yearly": non_man,
            "cpi_monthly": cpi,
            "ppi_yearly": ppi,
        })

    # If stale, refresh from Jin10 then fallback to cache
    if _stale(pmi_month) or _stale(cpi_month) or _stale(ppi_month):
        try:
            pmi_yearly = _jin10_report("65", "中国官方制造业PMI")
            non_man_yearly = _jin10_report("75", "中国官方非制造业PMI")
            cpi_monthly = _jin10_report("72", "中国CPI月率")
            ppi_yearly = _jin10_report("60", "中国PPI年率")
            _save_macro_cache({
                "pmi_yearly": pmi_yearly,
                "non_man_yearly": non_man_yearly,
                "cpi_monthly": cpi_monthly,
                "ppi_yearly": ppi_yearly,
            })
            pmi_latest = latest_by_month(pmi_yearly) or pmi_latest
            non_man_latest = latest_by_month(non_man_yearly) or non_man_latest
            cpi_latest = latest_by_month(cpi_monthly) or cpi_latest
            ppi_latest = latest_by_month(ppi_yearly) or ppi_latest
            pmi_month = pick_month(pmi_latest)
            non_man_month = pick_month(non_man_latest)
            cpi_month = pick_month(cpi_latest)
            ppi_month = pick_month(ppi_latest)
        except Exception:
            cache = _load_macro_cache()
            if cache:
                pmi_latest = latest_by_month(cache.get("pmi_yearly", [])) or pmi_latest
                non_man_latest = latest_by_month(cache.get("non_man_yearly", [])) or non_man_latest
                cpi_latest = latest_by_month(cache.get("cpi_monthly", [])) or cpi_latest
                ppi_latest = latest_by_month(cache.get("ppi_yearly", [])) or ppi_latest
                pmi_month = pick_month(pmi_latest)
                non_man_month = pick_month(non_man_latest)
                cpi_month = pick_month(cpi_latest)
                ppi_month = pick_month(ppi_latest)

    missing_cpi = _missing_value(cpi_latest)
    missing_ppi = _missing_value(ppi_latest)
    use_tushare = _stale(pmi_month) or _stale(cpi_month) or _stale(ppi_month) or missing_cpi or missing_ppi
    tushare_source = False
    source = "jin10"
    if use_tushare:
        _load_env()
        start_m = (datetime.now().replace(day=1) - timedelta(days=400)).strftime("%Y%m")
        end_m = datetime.now().strftime("%Y%m")
        pmi_records = _tushare_query("cn_pmi", "month,pmi010000,pmi020100", {"start_m": start_m, "end_m": end_m})
        cpi_records = _tushare_query("cn_cpi", "month,nt_val,nt_yoy,nt_mom", {"start_m": start_m, "end_m": end_m})
        ppi_records = _tushare_query("cn_ppi", "month,ppi_yoy,ppi_mom", {"start_m": start_m, "end_m": end_m})
        pmi_ts = _latest_by_key(pmi_records, "month")
        cpi_ts = _latest_by_key(cpi_records, "month")
        ppi_ts = _latest_by_key(ppi_records, "month")
        if pmi_ts or cpi_ts or ppi_ts:
            tushare_source = True
            if pmi_ts:
                pmi_latest = pmi_ts
                pmi_month = _parse_month(pmi_ts.get("month"))
            if cpi_ts:
                cpi_latest = {
                    "月份": _parse_month(cpi_ts.get("month")) or cpi_ts.get("month"),
                    "今值": cpi_ts.get("nt_mom") if cpi_ts.get("nt_mom") not in (None, "") else cpi_ts.get("nt_val") or cpi_ts.get("nt_yoy"),
                    "前值": None,
                    "商品": "中国CPI月率",
                    **cpi_ts,
                }
                cpi_month = _parse_month(cpi_ts.get("month"))
            if ppi_ts:
                ppi_latest = {
                    "月份": _parse_month(ppi_ts.get("month")) or ppi_ts.get("month"),
                    "今值": ppi_ts.get("ppi_yoy") if ppi_ts.get("ppi_yoy") not in (None, "") else ppi_ts.get("ppi_mom"),
                    "前值": None,
                    "商品": "中国PPI年率",
                    **ppi_ts,
                }
                ppi_month = _parse_month(ppi_ts.get("month"))

    missing_pmi = False
    if isinstance(pmi_latest, dict):
        missing_pmi = pmi_latest.get("今值") in (None, "", ".", "nan")
    # extra macro series from Tushare prewarm
    cn_m = prewarm.get("tushare_cn_m") if isinstance(prewarm.get("tushare_cn_m"), list) else market_data.get("tushare_cn_m") if isinstance(market_data.get("tushare_cn_m"), list) else []
    sf_month = prewarm.get("tushare_sf_month") if isinstance(prewarm.get("tushare_sf_month"), list) else market_data.get("tushare_sf_month") if isinstance(market_data.get("tushare_sf_month"), list) else []
    cn_gdp = prewarm.get("tushare_cn_gdp") if isinstance(prewarm.get("tushare_cn_gdp"), list) else market_data.get("tushare_cn_gdp") if isinstance(market_data.get("tushare_cn_gdp"), list) else []
    shibor = prewarm.get("tushare_shibor") if isinstance(prewarm.get("tushare_shibor"), list) else market_data.get("tushare_shibor") if isinstance(market_data.get("tushare_shibor"), list) else []
    lpr = prewarm.get("tushare_lpr") if isinstance(prewarm.get("tushare_lpr"), list) else market_data.get("tushare_lpr") if isinstance(market_data.get("tushare_lpr"), list) else []

    m2_latest = _latest_by_key(cn_m, "month") if cn_m else None
    sf_latest = _latest_by_key(sf_month, "month") if sf_month else None
    gdp_latest = _latest_by_key(cn_gdp, "quarter") if cn_gdp else None
    shibor_latest = _latest_by_key(shibor, "date") if shibor else None
    lpr_latest = _latest_by_key(lpr, "date") if lpr else None

    extra_stale = {
        "m2": _stale(_parse_month(m2_latest.get("month")) if isinstance(m2_latest, dict) else None) if m2_latest else True,
        "social_financing": _stale(_parse_month(sf_latest.get("month")) if isinstance(sf_latest, dict) else None) if sf_latest else True,
        "gdp": _stale_quarter(gdp_latest.get("quarter") if isinstance(gdp_latest, dict) else None),
        "shibor": _stale(_parse_month(shibor_latest.get("date")) if isinstance(shibor_latest, dict) else None, max_months=1) if shibor_latest else True,
        "lpr": _stale(_parse_month(lpr_latest.get("date")) if isinstance(lpr_latest, dict) else None, max_months=1) if lpr_latest else True,
    }

    return {
        "pmi": None if (_stale(pmi_month) or missing_pmi) else {
            "manufacturing": pmi_latest,
            "non_manufacturing": non_man_latest,
        },
        "cpi": None if (_stale(cpi_month) or _missing_value(cpi_latest)) else cpi_latest,
        "ppi": None if (_stale(ppi_month) or _missing_value(ppi_latest)) else ppi_latest,
        "liquidity": {
            "m2": m2_latest,
            "shibor": shibor_latest,
            "lpr": lpr_latest,
        },
        "credit": {
            "social_financing": sf_latest,
        },
        "growth": {
            "gdp": gdp_latest,
        },
        "stale": {
            "pmi": _stale(pmi_month) or _stale(non_man_month) or missing_pmi,
            "cpi": _stale(cpi_month) or _missing_value(cpi_latest),
            "ppi": _stale(ppi_month) or _missing_value(ppi_latest),
            "extra": extra_stale,
        },
        "source": "tushare" if tushare_source else source,
        "note": "macro data stale; hidden" if (_stale(pmi_month) or _stale(cpi_month) or _stale(ppi_month)) else "",
    }


def _build_capital_flow(snapshot: dict) -> dict:
    hotmoney = snapshot.get("hotmoney") if isinstance(snapshot, dict) else {}
    sectors = snapshot.get("sectors") if isinstance(snapshot, dict) else []
    strong = []
    if isinstance(sectors, list):
        for group in sectors:
            if not isinstance(group, dict):
                continue
            for item in group.get("strong", []) or []:
                if isinstance(item, dict):
                    strong.append({"label": group.get("label"), **item})
    return {
        "hotmoney_total_net_yi": hotmoney.get("total_net_yi") if isinstance(hotmoney, dict) else None,
        "top_net_buy": hotmoney.get("top_net_buy") if isinstance(hotmoney, dict) else None,
        "sector_strong_net": strong[:10],
        "source": "hhxg_snapshot",
    }


def _build_sector_rotation(snapshot: dict) -> dict:
    sectors = snapshot.get("sectors") if isinstance(snapshot, dict) else []
    return {
        "sectors": sectors,
        "source": "hhxg_snapshot.sectors",
    }


def _market_risk(snapshot: dict[str, Any]) -> dict[str, Any]:
    market = snapshot.get("market") if isinstance(snapshot, dict) else {}
    if not isinstance(market, dict):
        market = {}
    sentiment = _safe_float(market.get("sentiment_index"))
    limit_down = _safe_float(market.get("limit_down"))
    fried = _safe_float(market.get("fried"))
    promotion_rate = _safe_float(market.get("promotion_rate"))
    score = 0
    reasons: list[str] = []
    if sentiment is not None:
        if sentiment < 30:
            score += 3
            reasons.append("sentiment_index_below_30")
        elif sentiment < 45:
            score += 1
            reasons.append("sentiment_index_below_45")
    if limit_down is not None:
        if limit_down >= 30:
            score += 3
            reasons.append("limit_down_above_30")
        elif limit_down >= 10:
            score += 2
            reasons.append("limit_down_above_10")
    if fried is not None and fried >= 30:
        score += 1
        reasons.append("fried_board_above_30")
    if promotion_rate is not None and promotion_rate < 0.25:
        score += 1
        reasons.append("promotion_rate_below_25pct")
    if score >= 5:
        level = "red"
        mode = "risk_off"
    elif score >= 3:
        level = "orange"
        mode = "risk_off"
    elif score >= 1:
        level = "yellow"
        mode = "neutral"
    else:
        level = "green"
        mode = "risk_on" if sentiment is not None and sentiment >= 60 else "neutral"
    return {
        "risk_score": score,
        "risk_level": level,
        "risk_mode": mode,
        "reasons": reasons,
        "inputs": {
            "sentiment_index": sentiment,
            "limit_down": limit_down,
            "fried": fried,
            "promotion_rate": promotion_rate,
        },
    }


def _build_concept_heat(snapshot: dict[str, Any]) -> dict[str, Any]:
    themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
    heat: list[dict[str, Any]] = []
    for item in themes:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("theme")
        if not name:
            continue
        net_yi = _safe_float(item.get("net_yi")) or 0.0
        limitup = _safe_float(item.get("limitup_count") or item.get("limitup")) or 0.0
        stock_count = _safe_float(item.get("stock_count")) or 0.0
        score = min(100.0, max(0.0, net_yi * 5 + limitup * 12 + stock_count * 2))
        heat.append({
            "name": name,
            "score": round(score, 2),
            "net_yi": net_yi,
            "limitup_count": limitup,
            "stock_count": stock_count,
            "top_stocks": (item.get("top_stocks") or [])[:5] if isinstance(item.get("top_stocks"), list) else [],
            "source": "hhxg_snapshot.hot_themes",
        })
    if not heat:
        sectors = _build_sector_rotation(snapshot).get("sectors") or []
        for group in sectors:
            if not isinstance(group, dict):
                continue
            for item in group.get("strong", []) or []:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not name:
                    continue
                net_yi = _safe_float(item.get("net_yi")) or 0.0
                limitup = _safe_float(item.get("limitup_count") or item.get("limitup")) or 0.0
                heat.append({
                    "name": name,
                    "score": round(min(100.0, max(0.0, net_yi * 5 + limitup * 12)), 2),
                    "net_yi": net_yi,
                    "limitup_count": limitup,
                    "leader": item.get("leader"),
                    "label": group.get("label"),
                    "source": "hhxg_snapshot.sectors",
                })
    return {
        "heat": sorted(heat, key=lambda row: row.get("score", 0), reverse=True)[:20],
        "source": "hhxg_snapshot.hot_themes/sectors",
    }


def _build_macro_alert_check(snapshot: dict[str, Any]) -> dict[str, Any]:
    risk = _market_risk(snapshot)
    alerts: list[dict[str, Any]] = []
    for reason in risk["reasons"]:
        severity = "high" if risk["risk_level"] in {"red", "orange"} else "medium"
        alerts.append({
            "severity": severity,
            "code": reason,
            "message": f"Macro/market risk trigger: {reason}",
        })
    if not alerts:
        alerts.append({
            "severity": "info",
            "code": "no_extreme_market_alert",
            "message": "No extreme risk trigger found in the supplied snapshot.",
        })
    return {
        "risk": risk,
        "alerts": alerts,
        "source": "hhxg_snapshot.market",
    }


def _build_macro_regime_query(prewarm: dict[str, Any]) -> dict[str, Any]:
    snapshot = _extract_snapshot(prewarm)
    risk = _market_risk(snapshot)
    capital = _build_capital_flow(snapshot)
    sector = _build_sector_rotation(snapshot)
    heat = _build_concept_heat(snapshot)
    risk_budget_map = {
        "green": {"max_equity": 0.7, "cash_min": 0.1, "new_position_allowed": True},
        "yellow": {"max_equity": 0.55, "cash_min": 0.2, "new_position_allowed": True},
        "orange": {"max_equity": 0.35, "cash_min": 0.35, "new_position_allowed": False},
        "red": {"max_equity": 0.2, "cash_min": 0.5, "new_position_allowed": False},
    }
    return {
        "risk": risk,
        "risk_budget_reference": risk_budget_map.get(risk["risk_level"], risk_budget_map["yellow"]),
        "capital_flow": capital,
        "sector_rotation": sector,
        "concept_heat": heat,
        "source": "hhxg_snapshot",
    }


def _incomplete_reasons(command: str, result: dict[str, Any]) -> list[str]:
    if command == "domestic-macro":
        if not any(result.get(key) for key in ("pmi", "cpi", "ppi")):
            return ["macro_indicators_missing"]
    if command == "global-macro-analysis":
        if not result.get("global_assets") and not result.get("global_macro"):
            return ["global_macro_inputs_missing"]
    if command == "market-review":
        if not result.get("summary") and not any((result.get("domestic_macro") or {}).get(key) for key in ("pmi", "cpi", "ppi")):
            return ["market_review_inputs_missing"]
    if command == "capital-flow-analysis":
        if result.get("hotmoney_total_net_yi") is None and not result.get("top_net_buy") and not result.get("sector_strong_net"):
            return ["capital_flow_snapshot_missing"]
    if command == "sector-rotation":
        if not result.get("sectors"):
            return ["sector_rotation_snapshot_missing"]
    if command == "concept-heat":
        if not result.get("heat"):
            return ["concept_heat_snapshot_missing"]
    if command == "macro-alert-check":
        risk_inputs = (result.get("risk") or {}).get("inputs") or {}
        if not any(value is not None for value in risk_inputs.values()):
            return ["market_risk_inputs_missing"]
    if command == "macro-regime-query":
        risk_inputs = ((result.get("risk") or {}).get("inputs") or {})
        if not any(value is not None for value in risk_inputs.values()) and not (result.get("sector_rotation") or {}).get("sectors"):
            return ["macro_regime_inputs_missing"]
    return []


def _wrap_result(command: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors = _incomplete_reasons(command, result)
    if errors:
        return _fail(command, payload, errors)
    output = _base_output(command, payload)
    output["sources"] = _normalize_sources(result.get("source"))
    output["warnings"] = ["macro_data_stale"] if result.get("note") else []
    output["result"] = result
    return output


def _build_result(command: str, prewarm: dict) -> dict:
    snapshot = _extract_snapshot(prewarm)
    tushare_news = prewarm.get("tushare_news") if isinstance(prewarm.get("tushare_news"), list) else []
    tushare_major_news = prewarm.get("tushare_major_news") if isinstance(prewarm.get("tushare_major_news"), list) else []
    jin10_news = prewarm.get("jin10_important_news") if isinstance(prewarm.get("jin10_important_news"), list) else []
    tushare_events = prewarm.get("tushare_eco_cal") if isinstance(prewarm.get("tushare_eco_cal"), list) else []

    if command == "domestic-macro":
        return _build_domestic_macro(prewarm)

    if command == "global-macro-analysis":
        _load_env()
        global_macro = _build_global_macro()
        assets = [
            ("SPY", "S&P 500"),
            ("QQQ", "Nasdaq 100"),
            ("DIA", "Dow Jones"),
            ("IWM", "Russell 2000"),
            ("^STOXX50E", "EuroStoxx 50"),
            ("^N225", "Nikkei 225"),
            ("^HSI", "Hang Seng"),
            ("^FTSE", "FTSE 100"),
            ("GLD", "Gold"),
            ("GC=F", "Gold Futures"),
            ("TLT", "US 20Y Treasury"),
            ("HYG", "High Yield Credit"),
            ("USO", "Crude Oil ETF"),
            ("CL=F", "WTI Crude"),
            ("HG=F", "Copper"),
            ("OANDA:USDJPY", "USDJPY"),
            ("EURUSD=X", "EURUSD"),
            ("USDCNH=X", "USDCNH"),
            ("BINANCE:BTCUSDT", "BTC"),
            ("^VIX", "VIX"),
            ("DX-Y.NYB", "DXY"),
            ("^TNX", "US10Y"),
            ("^FVX", "US5Y"),
        ]
        quotes = []
        missing: list[tuple[str, str]] = []
        for symbol, name in assets:
            q = _finnhub_quote(symbol)
            if not q:
                missing.append((symbol, name))
                continue
            price = q.get("c")
            prev = q.get("pc") or 0
            change = q.get("d")
            pct = q.get("dp")
            quotes.append({
                "symbol": symbol,
                "name": name,
                "price": price,
                "change": change,
                "pct": pct,
                "prev_close": prev,
                "source": "finnhub",
            })

        yahoo_symbol_map = {
            "SPY": "SPY",
            "QQQ": "QQQ",
            "DIA": "DIA",
            "IWM": "IWM",
            "^STOXX50E": "^STOXX50E",
            "^N225": "^N225",
            "^HSI": "^HSI",
            "^FTSE": "^FTSE",
            "GLD": "GLD",
            "GC=F": "GC=F",
            "TLT": "TLT",
            "HYG": "HYG",
            "USO": "USO",
            "CL=F": "CL=F",
            "HG=F": "HG=F",
            "OANDA:USDJPY": "JPY=X",
            "EURUSD=X": "EURUSD=X",
            "USDCNH=X": "CNH=X",
            "BINANCE:BTCUSDT": "BTC-USD",
            "^VIX": "^VIX",
            "DX-Y.NYB": "DX-Y.NYB",
            "^TNX": "^TNX",
            "^FVX": "^FVX",
        }
        if missing:
            yahoo_symbols = [yahoo_symbol_map.get(sym) for sym, _ in missing if yahoo_symbol_map.get(sym)]
            yahoo_quotes = _yahoo_quotes(list(dict.fromkeys(yahoo_symbols)))
            for symbol, name in missing:
                ysym = yahoo_symbol_map.get(symbol)
                if not ysym:
                    continue
                row = yahoo_quotes.get(ysym)
                if not row:
                    continue
                quotes.append({
                    "symbol": symbol,
                    "name": name,
                    "price": row.get("price"),
                    "change": row.get("change"),
                    "pct": row.get("pct"),
                    "prev_close": row.get("prev_close"),
                    "source": "yahoo",
                })

        # AkShare fallback for global assets (indices/commodities/fx/rates)
        found_symbols = {q.get("symbol") for q in quotes if isinstance(q, dict)}
        akshare_map: dict[str, tuple[str, str | None]] = {
            "SPY": ("index_us", ".INX"),
            "QQQ": ("index_us", ".NDX"),
            "DIA": ("index_us", ".DJI"),
            "^STOXX50E": ("index_global_sina", "欧洲Stoxx50指数"),
            "^N225": ("index_global_sina", "日经225指数"),
            "^FTSE": ("index_global_sina", "英国富时100指数"),
            "^HSI": ("hk_index", "HSI"),
            "GLD": ("futures_foreign", "GC"),
            "GC=F": ("futures_foreign", "GC"),
            "USO": ("futures_foreign", "CL"),
            "CL=F": ("futures_foreign", "CL"),
            "HG=F": ("futures_foreign", "HG"),
            "OANDA:USDJPY": ("forex", "USDJPY"),
            "EURUSD=X": ("forex", "EURUSD"),
            "USDCNH=X": ("forex", "USDCNH"),
            "DX-Y.NYB": ("index_global_em", "美元指数"),
            "^TNX": ("bond_us", "10Y"),
            "^FVX": ("bond_us", "5Y"),
        }
        if missing:
            for symbol, name in missing:
                if symbol in found_symbols:
                    continue
                if symbol not in akshare_map:
                    continue
                kind, key = akshare_map[symbol]
                quote = None
                if kind == "index_us" and key:
                    quote = _akshare_index_us(key)
                elif kind == "index_global_sina" and key:
                    quote = _akshare_index_global_sina(key)
                elif kind == "index_global_em" and key:
                    quote = _akshare_index_global_em(key)
                elif kind == "hk_index" and key:
                    quote = _akshare_hk_index(key)
                elif kind == "forex" and key:
                    quote = _akshare_forex(key)
                elif kind == "futures_foreign" and key:
                    quote = _akshare_futures_foreign(key)
                elif kind == "bond_us" and key:
                    quote = _akshare_bond_us(key)
                if not quote:
                    continue
                quotes.append({
                    "symbol": symbol,
                    "name": name,
                    "price": quote.get("price"),
                    "change": quote.get("change"),
                    "pct": quote.get("pct"),
                    "prev_close": quote.get("prev_close"),
                    "source": f"akshare:{kind}",
                })

        # light trend signals (3mo daily)
        trend_symbols = ["SPY", "QQQ", "TLT", "GLD", "USO", "^VIX", "DX-Y.NYB", "BINANCE:BTCUSDT"]
        asset_trends: dict[str, dict] = {}
        for sym in trend_symbols:
            series = _finnhub_candles(sym)
            if not series:
                ysym = yahoo_symbol_map.get(sym) or ("BTC-USD" if sym == "BINANCE:BTCUSDT" else sym)
                series = _yahoo_chart(ysym, range_="3mo", interval="1d")
            if series:
                asset_trends[sym] = _trend_from_series(series)

        # fallback: derive light trend from 1d pct if candles unavailable
        if not asset_trends:
            for q in quotes:
                sym = q.get("symbol")
                pct = q.get("pct")
                if sym and isinstance(pct, (int, float)):
                    if pct >= 0.3:
                        trend = "↑"
                    elif pct <= -0.3:
                        trend = "↓"
                    else:
                        trend = "→"
                    asset_trends[sym] = {"trend": trend, "pct": pct, "source": "1d_pct"}
        else:
            # fill missing trend symbols with 1d pct when possible
            for q in quotes:
                sym = q.get("symbol")
                if sym in asset_trends:
                    continue
                pct = q.get("pct")
                if sym and isinstance(pct, (int, float)):
                    if pct >= 0.3:
                        trend = "↑"
                    elif pct <= -0.3:
                        trend = "↓"
                    else:
                        trend = "→"
                    asset_trends[sym] = {"trend": trend, "pct": pct, "source": "1d_pct"}

        equity = [q for q in quotes if q["symbol"] in {"SPY", "QQQ", "DIA", "IWM", "^STOXX50E", "^N225", "^HSI", "^FTSE"}]
        risk_score = 0.0
        if equity:
            avg = sum((q.get("pct") or 0) for q in equity) / len(equity)
            risk_score += avg
        for q in quotes:
            if q["symbol"] == "HYG":
                risk_score += (q.get("pct") or 0)
            if q["symbol"] == "GLD":
                risk_score -= (q.get("pct") or 0) * 0.5
            if q["symbol"] == "^VIX":
                risk_score -= (q.get("pct") or 0) * 0.8
            if q["symbol"] in {"DX-Y.NYB", "USDCNH=X"}:
                risk_score -= (q.get("pct") or 0) * 0.3
        risk_mode = "neutral"
        if risk_score >= 0.6:
            risk_mode = "risk_on"
        elif risk_score <= -0.6:
            risk_mode = "risk_off"

        risk_level = "🟡中"
        if risk_mode == "risk_on":
            risk_level = "🟢低"
        elif risk_mode == "risk_off":
            risk_level = "🟠高"

        macro_cycle, macro_cycle_reason = _build_macro_cycle(global_macro)

        risk_budget_map = {
            "🟢低": {"max_equity": 0.7, "cash_min": 0.1, "max_leverage": 1.0},
            "🟡中": {"max_equity": 0.55, "cash_min": 0.2, "max_leverage": 0.9},
            "🟠高": {"max_equity": 0.35, "cash_min": 0.35, "max_leverage": 0.8},
            "🔴严重": {"max_equity": 0.2, "cash_min": 0.5, "max_leverage": 0.6},
        }
        risk_budget = risk_budget_map.get(risk_level, {"max_equity": 0.5, "cash_min": 0.25, "max_leverage": 0.9})

        # cross-asset summary
        def _group(sym: str) -> str:
            if sym in {"SPY", "QQQ", "DIA", "IWM", "^STOXX50E", "^N225", "^HSI", "^FTSE"}:
                return "equity"
            if sym in {"TLT", "^TNX", "^FVX"}:
                return "rates"
            if sym in {"GLD", "GC=F", "USO", "CL=F", "HG=F"}:
                return "commodities"
            if sym in {"OANDA:USDJPY", "EURUSD=X", "USDCNH=X", "DX-Y.NYB"}:
                return "fx"
            if sym in {"BINANCE:BTCUSDT"}:
                return "crypto"
            if sym in {"HYG"}:
                return "credit"
            if sym in {"^VIX"}:
                return "volatility"
            return "other"

        group_stats: dict[str, list[float]] = {}
        for q in quotes:
            sym = q.get("symbol")
            pct = q.get("pct")
            if sym and isinstance(pct, (int, float)):
                group_stats.setdefault(_group(sym), []).append(pct)
        group_momentum = {k: round(sum(v)/len(v), 3) for k, v in group_stats.items() if v}

        movers = [q for q in quotes if isinstance(q.get("pct"), (int, float))]
        top_gainers = sorted(movers, key=lambda x: x.get("pct", 0), reverse=True)[:5]
        top_losers = sorted(movers, key=lambda x: x.get("pct", 0))[:5]

        news_items = []
        seen_titles = set()

        def _push_news(title: str | None, summary: str | None, dt: str | None, source: str) -> None:
            text = title or summary or ""
            if not text:
                return
            key = text[:80]
            if key in seen_titles:
                return
            seen_titles.add(key)
            scope = _classify_scope(title, summary, source)
            news_items.append({
                "title": title or text[:80],
                "summary": summary,
                "datetime": dt,
                "source": source,
                "scope": scope,
            })

        # QVeris primary
        for item in _qveris_news_fallback("global markets news today"):
            if not isinstance(item, dict):
                continue
            _push_news(item.get("title"), item.get("summary"), item.get("datetime"), "qveris")

        # Agent-reach (xreach) secondary
        for item in _xreach_search("global markets OR macro OR inflation OR rate hike OR rate cut", limit=20):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            _push_news(text[:80] if text else None, text, item.get("time") or item.get("created_at"), "xreach")

        # Jin10 / Tushare (tertiary)
        for item in jin10_news[:20]:
            if isinstance(item, dict):
                _push_news(item.get("title"), item.get("content"), item.get("time"), "jin10.important")
        for item in tushare_major_news[:20]:
            if isinstance(item, dict):
                _push_news(item.get("title"), item.get("content"), item.get("datetime"), "tushare.major_news")
        for item in tushare_news[:20]:
            if isinstance(item, dict):
                _push_news(item.get("title"), item.get("content"), item.get("datetime"), "tushare.news")

        global_news = [n for n in news_items if n.get("scope") == "global"]
        china_macro_news = [n for n in news_items if n.get("scope") == "china_macro"]
        a_share_news = [n for n in news_items if n.get("scope") == "a_share"]

        events = []
        for item in news_items[:10]:
            events.append({
                "country": None,
                "event": item.get("title"),
                "importance": None,
                "report_date": item.get("datetime"),
                "actual": None,
                "forecast": None,
                "previous": None,
                "source": item.get("source"),
            })
        for item in tushare_events[:30]:
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
                "source": "tushare.eco_cal",
            })

        return {
            "global_assets": quotes,
            "risk_mode": risk_mode,
            "risk_level": risk_level,
            "global_macro": global_macro,
            "macro_cycle": macro_cycle,
            "macro_cycle_reason": macro_cycle_reason,
            "risk_budget": risk_budget,
            "asset_trends": asset_trends,
            "asset_groups": group_momentum,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "global_news": global_news[:20],
            "global_events": events[:30],
            "china_macro_news": (snapshot.get("macro_news") or [])[:10] + china_macro_news[:10],
            "a_share_news": a_share_news[:10],
            "source": "finnhub/yahoo/akshare+qveris/agent-reach+tushare",
        }

    if command == "market-review":
        summary = snapshot.get("ai_summary") if isinstance(snapshot, dict) else {}
        return {
            "summary": summary,
            "domestic_macro": _build_domestic_macro(prewarm),
            "source": "hhxg_snapshot + domestic_macro",
        }

    if command == "capital-flow-analysis":
        return _build_capital_flow(snapshot)

    if command == "concept-heat":
        return _build_concept_heat(snapshot)

    if command == "macro-alert-check":
        return _build_macro_alert_check(snapshot)

    if command == "macro-regime-query":
        return _build_macro_regime_query(prewarm)

    if command == "sector-rotation":
        return _build_sector_rotation(snapshot)

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
        prewarm = _load_latest_prewarm()
        result = _build_result(args.command, prewarm)
        output = _wrap_result(args.command, payload, result)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
