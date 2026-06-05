from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta


def _ensure_akshare():
    try:
        import akshare as ak  # noqa: F401
        return True, None
    except Exception as exc:  # pragma: no cover - runtime dependency
        return False, str(exc)


def _parse_date(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return value


def _today_yyyymmdd() -> str:
    return datetime.utcnow().strftime("%Y%m%d")


def _last_30_days() -> str:
    return (datetime.utcnow() - timedelta(days=30)).strftime("%Y%m%d")


def _df_to_records(df, limit: int | None = None):
    if df is None:
        return []
    try:
        if limit:
            df = df.tail(limit)
        return json.loads(df.to_json(orient="records", force_ascii=False))
    except Exception:
        return []


def _latest_by_month(records: list[dict]) -> dict | None:
    if not records:
        return None
    # Prefer lexicographic by "月份" field like "2026年03月份"
    with_month = [r for r in records if isinstance(r, dict) and r.get("月份")]
    if not with_month:
        return records[-1] if isinstance(records[-1], dict) else None
    def key_fn(r):
        return str(r.get("月份"))
    return sorted(with_month, key=key_fn, reverse=True)[0]


def _run_command(command: str, payload: dict) -> dict:
    import akshare as ak

    # ── market data ─────────────────────────────────────────────────────────
    if command == "a-stock-daily":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        adjust = payload.get("adjust", "")
        df = ak.stock_zh_a_hist(symbol=str(symbol), period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
        return {"records": _df_to_records(df)}

    if command == "index-daily":
        symbol = payload.get("symbol", "sh000001")
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        df = None
        if hasattr(ak, "stock_zh_index_daily"):
            df = ak.stock_zh_index_daily(symbol=str(symbol))
            if "date" in df.columns:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        elif hasattr(ak, "index_zh_a_hist"):
            df = ak.index_zh_a_hist(symbol=str(symbol).lstrip("sh").lstrip("sz"), period="daily", start_date=start_date, end_date=end_date)
        return {"records": _df_to_records(df)}

    if command == "stock-minute":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        period = str(payload.get("period", "5"))
        adjust = payload.get("adjust", "")
        df = ak.stock_zh_a_hist_min_em(symbol=symbol, period=period, adjust=adjust)
        return {"symbol": symbol, "period": period, "records": _df_to_records(df, 200)}

    if command == "fund-etf-daily":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        adjust = payload.get("adjust", "qfq")
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
        return {"symbol": symbol, "records": _df_to_records(df)}

    # ── board / sector ───────────────────────────────────────────────────────
    if command == "concept-board-list":
        df = ak.stock_board_concept_name_em()
        return {"records": _df_to_records(df)}

    if command == "concept-board-hist":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        df = ak.stock_board_concept_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="")
        return {"symbol": symbol, "records": _df_to_records(df)}

    if command == "industry-board-list":
        df = ak.stock_board_industry_name_em()
        return {"records": _df_to_records(df)}

    if command == "industry-board-hist":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        df = ak.stock_board_industry_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="")
        return {"symbol": symbol, "records": _df_to_records(df)}

    # ── capital flow ─────────────────────────────────────────────────────────
    if command == "north-capital-flow":
        market = payload.get("market", "total")
        symbol_map = {"sh": "沪股通", "sz": "深股通", "total": "北向资金"}
        symbol = symbol_map.get(market, "北向资金")
        try:
            df = ak.stock_em_hsgt_north_net_flow_in(symbol=symbol)
        except TypeError:
            df = ak.stock_em_hsgt_north_net_flow_in()
        limit = int(payload.get("limit", 20))
        return {"records": _df_to_records(df, limit), "market": market}

    if command == "stock-individual-flow":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        market = payload.get("market", "沪深A股")
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        limit = int(payload.get("limit", 10))
        return {"symbol": symbol, "records": _df_to_records(df, limit)}

    if command == "stock-market-flow":
        df = ak.stock_market_fund_flow()
        limit = int(payload.get("limit", 20))
        return {"records": _df_to_records(df, limit)}

    if command == "margin-detail":
        exchange = payload.get("exchange", "all")
        date = _parse_date(payload.get("date"), _today_yyyymmdd())
        results: dict = {"date": date}
        if exchange in ("sh", "all"):
            try:
                df = ak.stock_margin_sse(start_date=date, end_date=date)
                results["sh"] = _df_to_records(df)
            except Exception as e:
                results["sh_error"] = str(e)
        if exchange in ("sz", "all"):
            try:
                df = ak.stock_margin_szse(date=date)
                results["sz"] = _df_to_records(df)
            except Exception as e:
                results["sz_error"] = str(e)
        return results

    if command == "limit-up-list":
        date = _parse_date(payload.get("date"), _today_yyyymmdd())
        pool = payload.get("pool", "zt")
        if pool == "dt":
            df = ak.stock_dt_pool_em(date=date)
        elif pool == "strong":
            df = ak.stock_zt_pool_strong_em(date=date)
        else:
            df = ak.stock_zt_pool_em(date=date)
        return {"date": date, "pool": pool, "records": _df_to_records(df)}

    # ── sentiment / news ─────────────────────────────────────────────────────
    if command == "stock-hot-rank":
        df = ak.stock_hot_rank_em()
        limit = int(payload.get("limit", 50))
        return {"records": _df_to_records(df, limit)}

    if command == "stock-news":
        symbol = payload.get("symbol")
        if not symbol:
            raise ValueError("missing symbol")
        df = ak.stock_news_em(symbol=symbol)
        limit = int(payload.get("limit", 20))
        return {"symbol": symbol, "records": _df_to_records(df, limit)}

    # ── macro ────────────────────────────────────────────────────────────────
    if command == "macro-pmi":
        df = ak.macro_china_pmi()
        records = _df_to_records(df)
        return {"records": records, "latest": _latest_by_month(records)}

    if command == "macro-cpi":
        df = ak.macro_china_cpi()
        records = _df_to_records(df)
        return {"records": records, "latest": _latest_by_month(records)}

    if command == "macro-ppi":
        df = ak.macro_china_ppi()
        records = _df_to_records(df)
        return {"records": records, "latest": _latest_by_month(records)}

    if command == "macro-cn-forex":
        df = ak.macro_china_fx_gold()
        limit = int(payload.get("limit", 24))
        return {"records": _df_to_records(df, limit)}

    if command == "macro-us-cpi":
        df = ak.macro_usa_cpi_monthly()
        limit = int(payload.get("limit", 24))
        return {"records": _df_to_records(df, limit)}

    if command == "global-bond-yield":
        start_date = _parse_date(payload.get("start_date"), _last_30_days())
        end_date = _parse_date(payload.get("end_date"), _today_yyyymmdd())
        df = ak.bond_zh_us_rate(start_date=start_date, end_date=end_date)
        limit = int(payload.get("limit", 60))
        return {"records": _df_to_records(df, limit)}

    raise ValueError(f"unknown command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")

    ok, err = _ensure_akshare()
    if not ok:
        print(json.dumps({
            "package": "akshare",
            "command": args.command,
            "success": False,
            "error": f"akshare not available: {err}",
        }, ensure_ascii=False))
        return 1

    try:
        data = _run_command(args.command, payload)
        print(json.dumps({
            "package": "akshare",
            "command": args.command,
            "success": True,
            "payload": payload,
            "data": data,
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "package": "akshare",
            "command": args.command,
            "success": False,
            "payload": payload,
            "error": str(exc),
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
