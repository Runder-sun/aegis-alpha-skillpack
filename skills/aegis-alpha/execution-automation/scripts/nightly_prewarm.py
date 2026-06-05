from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


def _run(cmd: list[str], timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False, timeout=timeout)
        return {"ok": proc.returncode == 0, "code": proc.returncode, "output": proc.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -2, "output": "timeout"}
    except Exception as exc:
        return {"ok": False, "code": -1, "output": str(exc)}


def _json_from_output(raw: str) -> object:
    try:
        return json.loads(raw)
    except Exception:
        if not raw:
            return raw
        # attempt to extract JSON block when stderr notes are mixed in
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = raw[start:end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                pass
        return raw


def _jin10_report(attr_id: str, symbol: str, timeout: int = 10) -> list[dict]:
    url = "https://datacenter-api.jin10.com/reports/list_v2"
    params = {
        "category": "ec",
        "attr_id": attr_id,
        "max_date": "",
        "_": str(int(time.time() * 1000)),
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


def _load_env() -> None:
    env_paths = [
        Path(__file__).resolve().parents[4] / ".env",
        Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace")) / ".env",
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


def _load_jin10_attr_map(ws_path: Path) -> dict:
    env_raw = os.environ.get("JIN10_ATTR_MAP")
    if env_raw:
        try:
            data = json.loads(env_raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    for path in [
        ws_path / "config" / "jin10_attr_map.json",
        ws_path / "skills" / "execution-automation" / "data" / "jin10_attr_map.json",
    ]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


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


def main() -> int:
    workspace = os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace")
    ws_path = Path(workspace)
    skills_dir = ws_path / "skills"

    results: dict[str, object] = {}

    # hhxg market snapshot/margin/calendar
    hhxg_dispatch = skills_dir / "hhxg-market" / "scripts" / "dispatch.py"
    if hhxg_dispatch.exists():
        for command, key in {
            "snapshot-full": "hhxg_snapshot",
            "margin-full": "hhxg_margin",
            "calendar-week": "hhxg_calendar",
        }.items():
            res = _run(["python3", str(hhxg_dispatch), "--command", command, "--payload", "{}"])
            parsed = _json_from_output(res["output"]) if res["ok"] else res
            if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
                payload = parsed.get("result") or {}
                if payload.get("success") and isinstance(payload.get("data"), (dict, list)):
                    results[key] = payload.get("data")
                else:
                    results[key] = payload
            else:
                results[key] = parsed

    # market-intel daily news scan
    market_intel_dispatch = skills_dir / "market-intel" / "scripts" / "dispatch.py"
    if market_intel_dispatch.exists():
        res = _run(["python3", str(market_intel_dispatch), "--command", "daily-news-scan", "--payload", "{}"])
        parsed = _json_from_output(res["output"]) if res["ok"] else res
        if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
            news_payload = parsed.get("result") or {}
            a_share = news_payload.get("a_share") if isinstance(news_payload, dict) else None
            if isinstance(a_share, list):
                results["hhxg_news"] = a_share
            else:
                results["hhxg_news"] = a_share if a_share is not None else []
        else:
            results["hhxg_news"] = parsed

    # themesurfer signal
    ts_dir = skills_dir / "themesurfer-signal" / "scripts" / "dispatch.py"
    if ts_dir.exists():
        res = _run(["python3", str(ts_dir), "--command", "signal", "--payload", "{}"])
        results["themesurfer_signal"] = _json_from_output(res["output"]) if res["ok"] else res

    # macro from Jin10 (fast + avoids stale local series)
    try:
        pmi_yearly = _jin10_report("65", "中国官方制造业PMI")
        non_man = _jin10_report("75", "中国官方非制造业PMI")
        cpi_monthly = _jin10_report("72", "中国CPI月率")
        ppi_yearly = _jin10_report("60", "中国PPI年率")
        results["akshare_macro_pmi_yearly"] = pmi_yearly
        results["akshare_macro_non_man_pmi"] = non_man
        results["akshare_macro_cpi_monthly"] = cpi_monthly
        results["akshare_macro_ppi_yearly"] = ppi_yearly
        # compatibility aliases (avoid stale 2006-2008 series)
        results["akshare_macro_pmi"] = pmi_yearly
        results["akshare_macro_cpi"] = cpi_monthly
        results["akshare_macro_ppi"] = ppi_yearly
        # persist macro cache for downstream fallback
        cache_path = ws_path / "memory" / "macro_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_payload = {
            "pmi_yearly": pmi_yearly,
            "non_man_yearly": non_man,
            "cpi_monthly": cpi_monthly,
            "ppi_yearly": ppi_yearly,
        }
        cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        # If Jin10 returns missing values, try Tushare for the missing series
        def _needs_tushare(records: list[dict] | None, key: str = "今值") -> bool:
            if not records or not isinstance(records, list):
                return True
            latest = records[0] if records else {}
            return latest.get(key) in (None, "", "-", "N/A")

        need_pmi = _needs_tushare(pmi_yearly, "今值")
        need_cpi = _needs_tushare(cpi_monthly, "今值")
        need_ppi = _needs_tushare(ppi_yearly, "今值")
        if need_pmi or need_cpi or need_ppi:
            _load_env()
            try:
                start_m = (datetime.now().replace(day=1) - timedelta(days=400)).strftime("%Y%m")
            except Exception:
                start_m = None
            end_m = datetime.now().strftime("%Y%m")
            if start_m:
                pmi_records = _tushare_query("cn_pmi", "month,pmi010000,pmi020100", {"start_m": start_m, "end_m": end_m}) if need_pmi else []
                cpi_records = _tushare_query("cn_cpi", "month,nt_val,nt_yoy,nt_mom", {"start_m": start_m, "end_m": end_m}) if need_cpi else []
                ppi_records = _tushare_query("cn_ppi", "month,ppi_yoy,ppi_mom", {"start_m": start_m, "end_m": end_m}) if need_ppi else []
                if pmi_records:
                    results["akshare_macro_pmi_yearly"] = pmi_records
                    results["akshare_macro_pmi"] = pmi_records
                if cpi_records:
                    results["akshare_macro_cpi_monthly"] = cpi_records
                    results["akshare_macro_cpi"] = cpi_records
                if ppi_records:
                    results["akshare_macro_ppi_yearly"] = ppi_records
                    results["akshare_macro_ppi"] = ppi_records
                if pmi_records or cpi_records or ppi_records:
                    results["macro_source"] = "tushare"
    except Exception as exc:
        results["akshare_macro_error"] = f"jin10_fetch_failed: {exc}"
        # fallback to Tushare if configured
        _load_env()
        try:
            start_m = (datetime.now().replace(day=1) - timedelta(days=400)).strftime("%Y%m")
        except Exception:
            start_m = None
        end_m = datetime.now().strftime("%Y%m")
        if start_m:
            pmi_records = _tushare_query("cn_pmi", "month,pmi010000,pmi020100", {"start_m": start_m, "end_m": end_m})
            cpi_records = _tushare_query("cn_cpi", "month,nt_val,nt_yoy,nt_mom", {"start_m": start_m, "end_m": end_m})
            ppi_records = _tushare_query("cn_ppi", "month,ppi_yoy,ppi_mom", {"start_m": start_m, "end_m": end_m})
            if pmi_records or cpi_records or ppi_records:
                results["macro_source"] = "tushare"
                results["akshare_macro_pmi_yearly"] = pmi_records
                results["akshare_macro_cpi_monthly"] = cpi_records
                results["akshare_macro_ppi_yearly"] = ppi_records
                results["akshare_macro_pmi"] = pmi_records
                results["akshare_macro_cpi"] = cpi_records
                results["akshare_macro_ppi"] = ppi_records
                cache_path = ws_path / "memory" / "macro_cache.json"
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_payload = {
                    "pmi_yearly": pmi_records,
                    "non_man_yearly": [],
                    "cpi_monthly": cpi_records,
                    "ppi_yearly": ppi_records,
                }
                cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # jin10 extra indicators (configurable attr_id map)
    try:
        extra_map = _load_jin10_attr_map(ws_path)
        extra_reports: dict[str, object] = {}
        for key, spec in extra_map.items():
            if isinstance(spec, dict):
                attr_id = str(spec.get("attr_id") or "").strip()
                label = spec.get("label") or key
            else:
                attr_id = str(spec).strip()
                label = key
            if not attr_id:
                continue
            try:
                extra_reports[key] = _jin10_report(attr_id, label)
            except Exception:
                continue
        if extra_reports:
            results["jin10_extra_reports"] = extra_reports
    except Exception as exc:
        results["jin10_extra_error"] = f"jin10_extra_failed: {exc}"

    # tushare global/news/policy/research/event calendar
    _load_env()
    try:
        today = datetime.now()
        start_3d = (today - timedelta(days=3)).strftime("%Y%m%d")
        start_7d = (today - timedelta(days=7)).strftime("%Y%m%d")
        start_14d = (today - timedelta(days=14)).strftime("%Y%m%d")
        end_today = today.strftime("%Y%m%d")
        end_7d = (today + timedelta(days=7)).strftime("%Y%m%d")

        news = _tushare_query("news", "title,content,datetime,channels,src", {
            "start_date": start_3d,
            "end_date": end_today,
            "limit": 80,
        })
        major_news = _tushare_query("major_news", "title,content,datetime,src", {
            "start_date": start_3d,
            "end_date": end_today,
            "limit": 40,
        })
        policy = _tushare_query("npr", "title,content,doc_type,issue_date,source", {
            "start_date": start_14d,
            "end_date": end_today,
        })
        research = _tushare_query("research_report", "ts_code,title,author,org_name,report_type,summary,issue_date", {
            "start_date": start_7d,
            "end_date": end_today,
            "limit": 80,
        })
        eco_cal = _tushare_query("eco_cal", "country,event,importance,report_date,actual,forecast,previous", {
            "start_date": start_3d,
            "end_date": end_7d,
        })

        if news:
            results["tushare_news"] = news
        if major_news:
            results["tushare_major_news"] = major_news
        if policy:
            results["tushare_policy"] = policy
        if research:
            results["tushare_research_report"] = research
        if eco_cal:
            results["tushare_eco_cal"] = eco_cal
    except Exception as exc:
        results["tushare_error"] = f"tushare_fetch_failed: {exc}"

    # jin10 important news snapshot (playwright-based)
    try:
        jin10_skill = skills_dir / "jin10-feed" / "scripts" / "dispatch.py"
        if jin10_skill.exists():
            res = _run(["python3", str(jin10_skill), "--command", "jin10-snapshot", "--payload", "{}"])
            parsed = _json_from_output(res["output"]) if res["ok"] else res
            # normalize result
            if isinstance(parsed, dict):
                payload = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
                data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(data, dict):
                    items = data.get("items") or data.get("new_items") or []
                    if items:
                        results["jin10_important_news"] = items
                    else:
                        results["jin10_important_news"] = []
                        results["jin10_snapshot_empty"] = True
                    results["jin10_snapshot_raw"] = payload
                else:
                    results["jin10_snapshot_raw"] = payload
            else:
                results["jin10_snapshot_raw"] = parsed
    except Exception as exc:
        results["jin10_error"] = f"jin10_snapshot_failed: {exc}"

    # tushare macro expansion: M2 / Social Financing / GDP / Shibor / LPR
    try:
        today = datetime.now()
        start_m = (today.replace(day=1) - timedelta(days=450)).strftime("%Y%m")
        end_m = today.strftime("%Y%m")
        start_q = f"{today.year-3}Q1"
        end_q = f"{today.year}Q{(today.month - 1)//3 + 1}"
        start_date_30d = (today - timedelta(days=30)).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")

        cn_m = _tushare_query("cn_m", "month,m0,m0_yoy,m1,m1_yoy,m2,m2_yoy", {"start_m": start_m, "end_m": end_m})
        sf_month = _tushare_query("sf_month", "month,inc_month,inc_cumval,stk_endval", {"start_m": start_m, "end_m": end_m})
        cn_gdp = _tushare_query("cn_gdp", "quarter,gdp,gdp_yoy,pi,pi_yoy,si,si_yoy,ti,ti_yoy", {"start_q": start_q, "end_q": end_q})
        shibor = _tushare_query("shibor", "date,on,1w,2w,1m,3m,6m,9m,1y", {"start_date": start_date_30d, "end_date": end_date})
        lpr = _tushare_query("shibor_lpr", "date,1y", {"start_date": start_date_30d, "end_date": end_date})

        if cn_m:
            results["tushare_cn_m"] = cn_m
        if sf_month:
            results["tushare_sf_month"] = sf_month
        if cn_gdp:
            results["tushare_cn_gdp"] = cn_gdp
        if shibor:
            results["tushare_shibor"] = shibor
        if lpr:
            results["tushare_lpr"] = lpr
    except Exception as exc:
        results["tushare_macro_error"] = f"tushare_macro_fetch_failed: {exc}"

    # baostock index daily (fallback)
    try:
        import baostock as bs
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            lg = bs.login()
            if lg.error_code == "0":
                rs = bs.query_history_k_data_plus(
                    "sh.000001",
                    "date,close,volume,amount",
                    frequency="d",
                    adjustflag="3",
                )
                data = []
                while rs.next():
                    data.append(rs.get_row_data())
                bs.logout()
                results["baostock_index_daily"] = data[-30:]
            else:
                results["baostock_error"] = lg.error_msg
    except Exception as exc:
        results["baostock_error"] = str(exc)

    results["market_data"] = {
        "hhxg_snapshot": results.get("hhxg_snapshot"),
        "hhxg_margin": results.get("hhxg_margin"),
        "hhxg_calendar": results.get("hhxg_calendar"),
        "akshare_macro_pmi_yearly": results.get("akshare_macro_pmi_yearly"),
        "akshare_macro_non_man_pmi": results.get("akshare_macro_non_man_pmi"),
        "akshare_macro_cpi_monthly": results.get("akshare_macro_cpi_monthly"),
        "akshare_macro_ppi_yearly": results.get("akshare_macro_ppi_yearly"),
        "akshare_macro_pmi": results.get("akshare_macro_pmi"),
        "akshare_macro_cpi": results.get("akshare_macro_cpi"),
        "akshare_macro_ppi": results.get("akshare_macro_ppi"),
        "tushare_cn_m": results.get("tushare_cn_m"),
        "tushare_sf_month": results.get("tushare_sf_month"),
        "tushare_cn_gdp": results.get("tushare_cn_gdp"),
        "tushare_shibor": results.get("tushare_shibor"),
        "tushare_lpr": results.get("tushare_lpr"),
        "baostock_index_daily": results.get("baostock_index_daily"),
    }
    results["news_sentiment"] = {
        "hhxg_news": results.get("hhxg_news"),
        "tushare_news": results.get("tushare_news"),
        "tushare_major_news": results.get("tushare_major_news"),
        "tushare_policy": results.get("tushare_policy"),
        "tushare_research_report": results.get("tushare_research_report"),
        "tushare_eco_cal": results.get("tushare_eco_cal"),
        "jin10_important_news": results.get("jin10_important_news"),
        "jin10_snapshot_raw": results.get("jin10_snapshot_raw"),
        "jin10_extra_reports": results.get("jin10_extra_reports"),
    }

    # persist
    out_dir = ws_path / "memory" / "prewarm"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"nightly-prewarm-{stamp}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "ok": True,
        "saved_to": str(out_path),
        "keys": list(results.keys()),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
