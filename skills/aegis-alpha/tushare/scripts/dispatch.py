from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import urllib.request


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _load_env() -> None:
    env_paths = [
        _workspace_dir() / ".env",
        Path.home() / ".aegis-alpha" / "workspace" / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _to_yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _parse_date(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = value.replace("-", "")
    if len(cleaned) == 8 and cleaned.isdigit():
        return cleaned
    return fallback


def _tushare_query(api_name: str, fields: str, params: dict[str, Any]) -> list[dict]:
    token = os.environ.get("TUSHARE_TOKEN") or ""
    if not token:
        return []
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": fields,
    }
    try:
        req = urllib.request.Request(
            "http://api.tushare.pro",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
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
    records: list[dict] = []
    for row in items:
        if not isinstance(row, list):
            continue
        records.append(dict(zip(fields_list, row)))
    return records


def _run_command(command: str, payload: dict) -> dict:
    today = datetime.now()
    if command == "news":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=3)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        limit = int(payload.get("limit", 50))
        src = payload.get("src")
        keyword = payload.get("keyword")
        params = {"start_date": start_date, "end_date": end_date, "limit": limit}
        if src:
            params["src"] = src
        if keyword:
            params["keyword"] = keyword
        records = _tushare_query("news", "title,content,datetime,channels,src", params)
        return {"records": records, "count": len(records), "source": "tushare.news"}

    if command == "major-news":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=3)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        limit = int(payload.get("limit", 30))
        src = payload.get("src")
        params = {"start_date": start_date, "end_date": end_date, "limit": limit}
        if src:
            params["src"] = src
        records = _tushare_query("major_news", "title,content,datetime,src", params)
        return {"records": records, "count": len(records), "source": "tushare.major_news"}

    if command == "research-report":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=7)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        limit = int(payload.get("limit", 50))
        params = {"start_date": start_date, "end_date": end_date, "limit": limit}
        records = _tushare_query("research_report", "ts_code,title,author,org_name,report_type,summary,issue_date", params)
        return {"records": records, "count": len(records), "source": "tushare.research_report"}

    if command == "policy":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=14)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        keyword = payload.get("keyword")
        params = {"start_date": start_date, "end_date": end_date}
        if keyword:
            params["keyword"] = keyword
        records = _tushare_query("npr", "title,content,doc_type,issue_date,source", params)
        return {"records": records, "count": len(records), "source": "tushare.npr"}

    if command == "eco-cal":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=1)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today + timedelta(days=7)))
        params = {"start_date": start_date, "end_date": end_date}
        records = _tushare_query("eco_cal", "country,event,importance,report_date,actual,forecast,previous", params)
        return {"records": records, "count": len(records), "source": "tushare.eco_cal"}

    if command == "macro-cn-m2":
        start_m = payload.get("start_m")
        end_m = payload.get("end_m")
        if not start_m:
            start_m = (today.replace(day=1) - timedelta(days=450)).strftime("%Y%m")
        if not end_m:
            end_m = today.strftime("%Y%m")
        params = {"start_m": start_m, "end_m": end_m}
        records = _tushare_query("cn_m", "month,m0,m0_yoy,m1,m1_yoy,m2,m2_yoy", params)
        return {"records": records, "count": len(records), "source": "tushare.cn_m"}

    if command == "macro-cn-sf":
        start_m = payload.get("start_m")
        end_m = payload.get("end_m")
        if not start_m:
            start_m = (today.replace(day=1) - timedelta(days=450)).strftime("%Y%m")
        if not end_m:
            end_m = today.strftime("%Y%m")
        params = {"start_m": start_m, "end_m": end_m}
        records = _tushare_query("sf_month", "month,inc_month,inc_cumval,stk_endval", params)
        return {"records": records, "count": len(records), "source": "tushare.sf_month"}

    if command == "macro-cn-gdp":
        start_q = payload.get("start_q")
        end_q = payload.get("end_q")
        if not start_q or not end_q:
            year = today.year
            q = (today.month - 1) // 3 + 1
            end_q = end_q or f"{year}Q{q}"
            start_q = start_q or f"{year-3}Q1"
        params = {"start_q": start_q, "end_q": end_q}
        records = _tushare_query("cn_gdp", "quarter,gdp,gdp_yoy,pi,pi_yoy,si,si_yoy,ti,ti_yoy", params)
        return {"records": records, "count": len(records), "source": "tushare.cn_gdp"}

    if command == "macro-cn-shibor":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=30)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        params = {"start_date": start_date, "end_date": end_date}
        records = _tushare_query("shibor", "date,on,1w,2w,1m,3m,6m,9m,1y", params)
        return {"records": records, "count": len(records), "source": "tushare.shibor"}

    if command == "macro-cn-lpr":
        start_date = _parse_date(payload.get("start_date"), _to_yyyymmdd(today - timedelta(days=120)))
        end_date = _parse_date(payload.get("end_date"), _to_yyyymmdd(today))
        params = {"start_date": start_date, "end_date": end_date}
        records = _tushare_query("shibor_lpr", "date,1y", params)
        return {"records": records, "count": len(records), "source": "tushare.shibor_lpr"}

    # ── market snapshot / screening ──────────────────────────────────────────
    if command == "daily-basic":
        params: dict = {}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        params["trade_date"] = payload.get("trade_date") or _to_yyyymmdd(today)
        fields = payload.get("fields", "ts_code,trade_date,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv,turnover_rate,volume_ratio")
        records = _tushare_query("daily_basic", fields, params)
        return {"records": records, "count": len(records), "source": "tushare.daily_basic"}

    if command == "stock-list":
        params = {"list_status": payload.get("list_status", "L")}
        fields = payload.get("fields", "ts_code,symbol,name,area,industry,market,list_date,is_hs")
        records = _tushare_query("stock_basic", fields, params)
        return {"records": records, "count": len(records), "source": "tushare.stock_basic"}

    if command == "stk-limit":
        params = {}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        params["trade_date"] = payload.get("trade_date") or _to_yyyymmdd(today)
        records = _tushare_query("stk_limit", "ts_code,trade_date,up_limit,down_limit,pre_close", params)
        return {"records": records, "count": len(records), "source": "tushare.stk_limit"}

    # ── dragon-tiger board ───────────────────────────────────────────────────
    if command == "top-list":
        params = {"trade_date": payload.get("trade_date") or _to_yyyymmdd(today)}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        records = _tushare_query(
            "top_list",
            "trade_date,ts_code,name,close,pct_chg,turnover_rate,l_sell,l_buy,l_amount,net_amount,reason",
            params,
        )
        return {"records": records, "count": len(records), "source": "tushare.top_list"}

    if command == "top-inst":
        params = {"trade_date": payload.get("trade_date") or _to_yyyymmdd(today)}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        records = _tushare_query("top_inst", "trade_date,ts_code,exalter,buy,sell,net_buy", params)
        return {"records": records, "count": len(records), "source": "tushare.top_inst"}

    # ── margin / float ───────────────────────────────────────────────────────
    if command == "margin":
        params: dict = {"trade_date": payload.get("trade_date") or _to_yyyymmdd(today)}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        if payload.get("exchange_id"):
            params["exchange_id"] = payload["exchange_id"]
        records = _tushare_query("margin", "trade_date,ts_code,rzye,rzyezb,rqye,rqyezb,rqmcl,rzrqye", params)
        return {"records": records, "count": len(records), "source": "tushare.margin"}

    if command == "share-float":
        params = {}
        for k in ("ts_code", "ann_date", "float_date"):
            if payload.get(k):
                params[k] = payload[k]
        if payload.get("limit"):
            params["limit"] = int(payload["limit"])
        records = _tushare_query("share_float", "ts_code,ann_date,float_date,float_share,float_ratio,holder_name,share_type", params)
        return {"records": records, "count": len(records), "source": "tushare.share_float"}

    # ── financial statements ─────────────────────────────────────────────────
    if command == "income":
        ts_code = payload.get("ts_code")
        if not ts_code:
            raise ValueError("missing ts_code")
        params = {"ts_code": ts_code, "report_type": payload.get("report_type", "1")}
        if payload.get("period"):
            params["period"] = payload["period"]
        records = _tushare_query(
            "income",
            "ts_code,ann_date,f_ann_date,end_date,report_type,total_revenue,revenue,operate_profit,n_income,n_income_attr_p",
            params,
        )
        limit = int(payload.get("limit", 8))
        return {"records": records[:limit], "count": min(len(records), limit), "source": "tushare.income"}

    if command == "balancesheet":
        ts_code = payload.get("ts_code")
        if not ts_code:
            raise ValueError("missing ts_code")
        params = {"ts_code": ts_code}
        if payload.get("period"):
            params["period"] = payload["period"]
        records = _tushare_query(
            "balancesheet",
            "ts_code,ann_date,f_ann_date,end_date,report_type,total_assets,total_hldr_eqy_inc_min_int,total_liab",
            params,
        )
        limit = int(payload.get("limit", 8))
        return {"records": records[:limit], "count": min(len(records), limit), "source": "tushare.balancesheet"}

    if command == "cashflow":
        ts_code = payload.get("ts_code")
        if not ts_code:
            raise ValueError("missing ts_code")
        params = {"ts_code": ts_code}
        if payload.get("period"):
            params["period"] = payload["period"]
        records = _tushare_query(
            "cashflow",
            "ts_code,ann_date,f_ann_date,end_date,report_type,n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,n_incr_cash_cash_equ",
            params,
        )
        limit = int(payload.get("limit", 8))
        return {"records": records[:limit], "count": min(len(records), limit), "source": "tushare.cashflow"}

    if command == "fina-indicator":
        ts_code = payload.get("ts_code")
        if not ts_code:
            raise ValueError("missing ts_code")
        params = {"ts_code": ts_code}
        if payload.get("period"):
            params["period"] = payload["period"]
        records = _tushare_query(
            "fina_indicator",
            "ts_code,ann_date,end_date,eps,bps,roe,roa,grossprofitmargin,netprofitmargin,current_ratio,quick_ratio,debt_to_assets,yoy_equity,yoy_sales,yoy_net_profit",
            params,
        )
        limit = int(payload.get("limit", 8))
        return {"records": records[:limit], "count": min(len(records), limit), "source": "tushare.fina_indicator"}

    # ── sector / industry ────────────────────────────────────────────────────
    if command == "sw-daily":
        params = {}
        if payload.get("ts_code"):
            params["ts_code"] = payload["ts_code"]
        if payload.get("trade_date"):
            params["trade_date"] = payload["trade_date"]
        elif payload.get("start_date"):
            params["start_date"] = payload["start_date"]
            if payload.get("end_date"):
                params["end_date"] = payload["end_date"]
        else:
            params["trade_date"] = _to_yyyymmdd(today)
        records = _tushare_query("sw_daily", "trade_date,ts_code,name,open,high,low,close,vol,amount,pct_chg", params)
        return {"records": records, "count": len(records), "source": "tushare.sw_daily"}

    raise ValueError(f"unknown command: {command}")


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


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

    payload = json.loads(args.payload or "{}")
    _load_env()
    result = _run_command(args.command, payload)

    print(json.dumps({
        "package": "tushare",
        "command": args.command,
        "payload": payload,
        "result": result,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
