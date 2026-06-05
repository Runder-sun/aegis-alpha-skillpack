from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta


def _try_akshare(symbol: str, lookback: int):
    try:
        import akshare as ak
    except Exception:
        return None, "akshare not installed"

    end = datetime.utcnow().strftime("%Y%m%d")
    start = (datetime.utcnow() - timedelta(days=lookback * 2)).strftime("%Y%m%d")
    df = None
    if hasattr(ak, "stock_zh_index_daily"):
        df = ak.stock_zh_index_daily(symbol=symbol)
        if "date" in df.columns:
            import pandas as pd
            date_series = pd.to_datetime(df["date"])
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            df = df[(date_series >= start_dt) & (date_series <= end_dt)]
    elif hasattr(ak, "index_zh_a_hist"):
        clean_symbol = symbol.replace("sh", "").replace("sz", "")
        df = ak.index_zh_a_hist(symbol=clean_symbol, period="daily", start_date=start, end_date=end)
    if df is None or df.empty:
        return None, "akshare returned empty"
    return df, "akshare"


def _try_baostock(symbol: str, lookback: int):
    try:
        import baostock as bs
    except Exception:
        return None, "baostock not installed"

    end = datetime.utcnow().strftime("%Y-%m-%d")
    start = (datetime.utcnow() - timedelta(days=lookback * 2)).strftime("%Y-%m-%d")
    lg = bs.login()
    if lg.error_code != "0":
        return None, f"baostock login failed: {lg.error_msg}"
    try:
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,close",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="3",
        )
        data = []
        while rs.next():
            data.append(rs.get_row_data())
    finally:
        bs.logout()
    if not data:
        return None, "baostock returned empty"
    # convert to list of (date, close)
    return data, "baostock"


def _compute_from_akshare(df, ma_window: int):
    close_col = None
    for cand in ("close", "收盘", "收盘价"):
        if cand in df.columns:
            close_col = cand
            break
    if close_col is None:
        close_col = df.columns[-1]
    series = df[close_col].astype(float)
    if len(series) < ma_window:
        raise ValueError("not enough data for MA")
    ma20 = series.rolling(window=ma_window).mean().iloc[-1]
    close = series.iloc[-1]
    return float(close), float(ma20)


def _compute_from_baostock(data, ma_window: int):
    closes = [float(row[1]) for row in data if row[1]]
    if len(closes) < ma_window:
        raise ValueError("not enough data for MA")
    close = closes[-1]
    ma20 = sum(closes[-ma_window:]) / float(ma_window)
    return float(close), float(ma20)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    if args.command != "signal":
        raise SystemExit(f"unknown command: {args.command}")

    payload = json.loads(args.payload or "{}")
    symbol = payload.get("symbol", "sh000001")
    lookback = int(payload.get("lookback", 60))
    ma_window = int(payload.get("ma_window", 20))

    df, source = _try_akshare(symbol, lookback)
    close = ma20 = None
    error = None
    if df is not None:
        try:
            close, ma20 = _compute_from_akshare(df, ma_window)
        except Exception as exc:
            error = str(exc)
    else:
        data, source = _try_baostock(symbol.replace("sh", "sh.").replace("sz", "sz."), lookback)
        if data is not None:
            try:
                close, ma20 = _compute_from_baostock(data, ma_window)
            except Exception as exc:
                error = str(exc)
        else:
            error = source

    if close is None or ma20 is None:
        print(json.dumps({
            "package": "themesurfer-signal",
            "command": "signal",
            "success": False,
            "payload": payload,
            "error": error or "no data",
        }, ensure_ascii=False))
        return 1

    status = "FULL" if close >= ma20 else "LOCKOUT"
    print(json.dumps({
        "package": "themesurfer-signal",
        "command": "signal",
        "success": True,
        "payload": payload,
        "data": {
            "symbol": symbol,
            "close": close,
            "ma20": ma20,
            "status": status,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
