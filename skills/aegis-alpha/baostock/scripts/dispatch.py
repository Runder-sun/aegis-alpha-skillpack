from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta


def _ensure_baostock():
    try:
        import baostock as bs  # noqa: F401
        return True, None
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def _parse_date(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    return value


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _last_30_days() -> str:
    return (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")


def _current_year_quarter() -> tuple[int, int]:
    now = datetime.now()
    q = (now.month - 1) // 3  # 0 = just-ended prior quarter
    if q == 0:
        return now.year - 1, 4
    return now.year, q


def _query_history(bs, symbol: str, start_date: str, end_date: str, fields: str, adjustflag: str, frequency: str = "d"):
    rs = bs.query_history_k_data_plus(
        symbol,
        fields,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        adjustflag=adjustflag,
    )
    data = []
    while rs.next():
        row = rs.get_row_data()
        if rs.fields:
            data.append(dict(zip(rs.fields, row)))
        else:
            data.append(row)
    return {"fields": fields.split(","), "records": data}


def _query_report(bs, func_name: str, code: str, year: int, quarter: int) -> list[dict]:
    func = getattr(bs, func_name, None)
    if func is None:
        return []
    rs = func(code=code, year=year, quarter=quarter)
    rows: list[dict] = []
    while rs.next():
        row = rs.get_row_data()
        if rs.fields:
            rows.append(dict(zip(rs.fields, row)))
        else:
            rows.append({"values": row})
    return rows


def _run_command(command: str, payload: dict) -> dict:
    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"login failed: {lg.error_msg}")

    try:
        # ── history: daily ──────────────────────────────────────────────────
        if command == "a-stock-daily":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            start_date = _parse_date(payload.get("start_date"), _last_30_days())
            end_date = _parse_date(payload.get("end_date"), _today())
            fields = payload.get("fields", "date,code,open,high,low,close,volume,amount,turn,pctChg")
            adjustflag = payload.get("adjustflag", "3")
            return _query_history(bs, symbol, start_date, end_date, fields, adjustflag, "d")

        if command == "index-daily":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            start_date = _parse_date(payload.get("start_date"), _last_30_days())
            end_date = _parse_date(payload.get("end_date"), _today())
            fields = payload.get("fields", "date,code,open,high,low,close,volume,amount,pctChg")
            return _query_history(bs, symbol, start_date, end_date, fields, "3", "d")

        # ── history: weekly ─────────────────────────────────────────────────
        if command == "stock-weekly":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            start_date = _parse_date(payload.get("start_date"), _last_30_days())
            end_date = _parse_date(payload.get("end_date"), _today())
            fields = payload.get("fields", "date,code,open,high,low,close,volume,amount,turn,pctChg")
            adjustflag = payload.get("adjustflag", "3")
            return _query_history(bs, symbol, start_date, end_date, fields, adjustflag, "w")

        # ── fundamental data ────────────────────────────────────────────────
        if command == "fundamental-data":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            year, quarter = _current_year_quarter()
            year = int(payload.get("year", year))
            quarter = int(payload.get("quarter", quarter))
            profit = _query_report(bs, "query_profit_data", symbol, year, quarter)
            growth = _query_report(bs, "query_growth_data", symbol, year, quarter)
            return {"symbol": symbol, "year": year, "quarter": quarter, "profit": profit, "growth": growth}

        if command == "balance-sheet":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            year, quarter = _current_year_quarter()
            year = int(payload.get("year", year))
            quarter = int(payload.get("quarter", quarter))
            rows = _query_report(bs, "query_balance_data", symbol, year, quarter)
            return {"symbol": symbol, "year": year, "quarter": quarter, "records": rows}

        if command == "cash-flow":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            year, quarter = _current_year_quarter()
            year = int(payload.get("year", year))
            quarter = int(payload.get("quarter", quarter))
            rows = _query_report(bs, "query_cash_flow_data", symbol, year, quarter)
            return {"symbol": symbol, "year": year, "quarter": quarter, "records": rows}

        if command == "dupont-data":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            year, quarter = _current_year_quarter()
            year = int(payload.get("year", year))
            quarter = int(payload.get("quarter", quarter))
            rows = _query_report(bs, "query_dupont_data", symbol, year, quarter)
            return {"symbol": symbol, "year": year, "quarter": quarter, "records": rows}

        if command == "dividend-data":
            symbol = payload.get("symbol")
            if not symbol:
                raise ValueError("missing symbol")
            year_str = payload.get("year", "")
            year_type = payload.get("year_type", "report")
            rs = bs.query_dividend_data(code=symbol, year=year_str, yearType=year_type)
            rows: list[dict] = []
            while rs.next():
                row = rs.get_row_data()
                if rs.fields:
                    rows.append(dict(zip(rs.fields, row)))
                else:
                    rows.append({"values": row})
            return {"symbol": symbol, "records": rows}

        raise ValueError(f"unknown command: {command}")

    finally:
        bs.logout()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")

    ok, err = _ensure_baostock()
    if not ok:
        print(json.dumps({
            "package": "baostock",
            "command": args.command,
            "success": False,
            "error": f"baostock not available: {err}",
        }, ensure_ascii=False))
        return 1

    try:
        data = _run_command(args.command, payload)
        print(json.dumps({
            "package": "baostock",
            "command": args.command,
            "success": True,
            "payload": payload,
            "data": data,
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "package": "baostock",
            "command": args.command,
            "success": False,
            "payload": payload,
            "error": str(exc),
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
