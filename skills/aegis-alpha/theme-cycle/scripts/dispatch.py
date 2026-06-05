from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import re
from typing import Any


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _theme_store_path() -> Path:
    return _workspace_dir() / "memory" / "themes.json"


def _load_theme_store() -> dict:
    path = _theme_store_path()
    if not path.exists():
        return {"themes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "themes" in data:
            return data
    except Exception:
        pass
    return {"themes": {}}


def _save_theme_store(store: dict) -> None:
    path = _theme_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        store["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _theme_id(name: str, horizon: str, asset_class: str) -> str:
    return f"{asset_class}:{horizon}:{name}"


def _upsert_theme(store: dict, theme: dict) -> dict:
    themes = store.setdefault("themes", {})
    tid = theme.get("id")
    if not tid:
        tid = _theme_id(theme.get("name", ""), theme.get("horizon", ""), theme.get("asset_class", ""))
        theme["id"] = tid
    existing = themes.get(tid)
    if isinstance(existing, dict):
        theme.setdefault("started_at", existing.get("started_at"))
        theme.setdefault("first_seen", existing.get("first_seen"))
        theme["last_seen"] = theme.get("last_seen") or datetime.now().strftime("%Y-%m-%d")
        # record changes for mainline evolution tracking
        changes = {}
        for key in ("lifecycle", "cycle", "operation", "status", "global_link", "risk_mode", "macro_cycle"):
            if existing.get(key) != theme.get(key):
                changes[key] = {"from": existing.get(key), "to": theme.get(key)}
        history = existing.get("history") if isinstance(existing.get("history"), list) else []
        if changes:
            history.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "changes": changes,
                "reason": theme.get("update_reason") or "auto-update",
            })
            theme["history"] = history[-12:]
        else:
            theme["history"] = history
    else:
        theme.setdefault("started_at", datetime.now().strftime("%Y-%m-%d"))
        theme.setdefault("first_seen", datetime.now().strftime("%Y-%m-%d"))
        theme["last_seen"] = datetime.now().strftime("%Y-%m-%d")
        theme["history"] = [{
            "date": datetime.now().strftime("%Y-%m-%d"),
            "changes": {"created": True},
            "reason": theme.get("update_reason") or "created",
        }]
    themes[tid] = theme
    return theme


def _call_macro_regime(command: str) -> dict | None:
    script = Path(__file__).resolve().parents[2] / "macro-regime" / "scripts" / "dispatch.py"
    if not script.exists():
        script = _workspace_dir() / "skills" / "macro-regime" / "scripts" / "dispatch.py"
    if not script.exists():
        return None
    cmd = ["python3", str(script), "--command", command, "--payload", "{}"]
    env = dict(os.environ)
    env["AEGIS_ALPHA_WORKSPACE"] = str(_workspace_dir())
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    raw = (proc.stdout or "").strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict) or parsed.get("ok") is False:
        return None
    return parsed.get("result") if isinstance(parsed.get("result"), dict) else None


def load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding='utf-8'))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "theme-cycle",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "theme-cycle freshness is inherited from latest prewarm artifact, theme store, and macro-regime outputs",
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
        "note": "Theme-cycle evidence is incomplete; do not infer rotation, theme status, or portfolio action.",
        "missing_critical_inputs": errors,
    }
    return output


def _normalize_sources(source: Any) -> list[str]:
    if isinstance(source, str) and source:
        return [source]
    if isinstance(source, list):
        return [str(item) for item in source if item]
    return []


def _extract_snapshot(prewarm: dict[str, Any]) -> dict[str, Any]:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}
    snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else {}
    if not snapshot:
        snapshot = prewarm.get("hhxg_snapshot") if isinstance(prewarm.get("hhxg_snapshot"), dict) else {}
    return snapshot if isinstance(snapshot, dict) else {}


def _summarize_sectors(snapshot: dict) -> dict:
    sectors = snapshot.get("sectors") if isinstance(snapshot, dict) else []
    strong = []
    weak = []
    if isinstance(sectors, list):
        for group in sectors:
            if not isinstance(group, dict):
                continue
            label = group.get("label")
            for item in group.get("strong", []) or []:
                if isinstance(item, dict):
                    strong.append({"label": label, **item})
            for item in group.get("weak", []) or []:
                if isinstance(item, dict):
                    weak.append({"label": label, **item})
    return {
        "strong": strong[:12],
        "weak": weak[:12],
    }


def _global_mainlines(
    global_macro: dict,
    global_assets: list[dict],
    news_items: list[dict],
    policy_items: list[dict],
    research_reports: list[dict],
    events: list[dict],
    store: dict | None = None,
) -> list[dict]:
    lines: list[dict] = []
    today = datetime.now().strftime("%Y-%m-%d")

    def pick_pct(symbol: str) -> float:
        for q in global_assets:
            if q.get("symbol") == symbol:
                return float(q.get("pct") or 0)
        return 0.0

    risk_mode = global_macro.get("risk_mode") or "neutral"
    risk_level = global_macro.get("risk_level") or ("🟢低" if risk_mode == "risk_on" else "🟠高" if risk_mode == "risk_off" else "🟡中")
    macro_cycle = global_macro.get("macro_cycle") or "neutral"
    asset_trends = global_macro.get("asset_trends") if isinstance(global_macro.get("asset_trends"), dict) else {}
    asset_groups = global_macro.get("asset_groups") if isinstance(global_macro.get("asset_groups"), dict) else {}
    risk_budget = global_macro.get("risk_budget") if isinstance(global_macro.get("risk_budget"), dict) else {}

    timeframe_map = {
        "long": "1-10年",
        "medium": "3-12月",
        "short": "1-3月",
        "ultra_short": "1-2周",
    }

    def _trend(symbol: str) -> str | None:
        trend = asset_trends.get(symbol) if isinstance(asset_trends.get(symbol), dict) else None
        if isinstance(trend, dict):
            return trend.get("trend")
        return None

    qqq_pct = pick_pct("QQQ")
    spy_pct = pick_pct("SPY")
    tech_lead = qqq_pct - spy_pct
    oil_pct = pick_pct("CL=F") or pick_pct("USO")
    gold_pct = pick_pct("GLD") or pick_pct("GC=F")

    def _collect_text(items: list[dict], keys: tuple[str, ...]) -> str:
        texts = []
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in keys:
                val = item.get(key)
                if val:
                    texts.append(str(val))
        return " ".join(texts)

    text_blob = " ".join([
        _collect_text(news_items, ("title", "summary")),
        _collect_text(policy_items, ("title", "summary", "content")),
        _collect_text(research_reports, ("title", "summary")),
    ])

    def _count_keywords(keywords: list[str]) -> int:
        total = 0
        for kw in keywords:
            total += len(re.findall(re.escape(kw), text_blob, flags=re.IGNORECASE))
        return total

    theme_scores = {
        "AI/算力与半导体": _count_keywords(["AI", "人工智能", "半导体", "芯片", "GPU", "算力", "数据中心"]),
        "能源与资源品": _count_keywords(["原油", "油价", "OPEC", "能源", "天然气", "煤炭", "资源品"]),
        "利率与央行政策": _count_keywords(["美联储", "Fed", "利率", "加息", "降息", "央行", "ECB", "BOJ"]),
        "地缘与国防": _count_keywords(["冲突", "制裁", "战争", "中东", "乌克兰", "国防", "军工"]),
        "消费与通胀": _count_keywords(["通胀", "CPI", "PPI", "消费", "零售"]),
        "新能源/电力基建": _count_keywords(["新能源", "光伏", "风电", "储能", "电网", "电力"]),
    }
    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
    top_theme = sorted_themes[0][0] if sorted_themes else "多资产均衡"
    if all(v == 0 for v in theme_scores.values()):
        top_theme = "多资产均衡"

    # Prepare existing lines for stability
    existing_by_horizon: dict[str, list[dict]] = {}
    if isinstance(store, dict):
        themes = store.get("themes")
        if isinstance(themes, dict):
            for item in themes.values():
                if not isinstance(item, dict):
                    continue
                if str(item.get("asset_class")) != "全球":
                    continue
                horizon = item.get("horizon")
                if horizon:
                    existing_by_horizon.setdefault(horizon, []).append(item)

    def _fallback_line(horizon: str, idx: int) -> dict:
        name_map = {
            "long": ["全球均衡配置", "结构性科技成长"],
            "medium": ["宏观中性防守", "政策节奏观察"],
            "short": ["风险中性轮动", "仓位纪律优先"],
            "ultra_short": ["事件驱动防守", "波动率监控"],
        }
        name = (name_map.get(horizon, ["全球均衡配置"]) or ["全球均衡配置"])[idx % 2]
        return {
            "name": name,
            "horizon": horizon,
            "timeframe": timeframe_map.get(horizon),
            "asset_class": "全球",
            "narrative": "在数据不足时维持中性框架，等待主线信号增强",
            "operation": "控制风险预算，保持分散与流动性",
            "lifecycle": "emerging",
            "cycle": macro_cycle,
            "risk_mode": risk_mode,
            "macro_cycle": macro_cycle,
            "status": "monitor",
            "started_at": today,
            "start_signal": "数据不足时的稳态基线",
            "end_triggers": ["主线信号增强", "风险模式切换"],
            "end_signal": "主线信号增强/风险模式切换",
            "driver": "baseline",
            "confidence": 0.4,
            "catalysts": [],
            "risks": risks,
            "targets": [{"name": name, "type": "theme"}],
            "strategies": [{"name": "稳态框架", "detail": "先稳住风险预算，再等待信号确认"}],
            "estimated_end": "跟随主线增强",
            "contingency": "信号增强后及时替换",
            "evidence": ["数据不足/稳态基线"],
            "score": 0.1,
            "update_reason": "fallback",
        }

    def _select_lines(candidates: list[dict], horizon: str, desired: int = 2) -> list[dict]:
        selected: list[dict] = []
        for cand in sorted(candidates, key=lambda x: x.get("score", 0), reverse=True):
            if len(selected) >= desired:
                break
            selected.append(cand)
        if len(selected) < desired:
            for existing in existing_by_horizon.get(horizon, []):
                if len(selected) >= desired:
                    break
                if any(existing.get("name") == s.get("name") for s in selected):
                    continue
                selected.append(existing)
        while len(selected) < desired:
            selected.append(_fallback_line(horizon, len(selected)))
        return selected

    # 长期主线 (multi)
    def _top_titles(items: list[dict], key: str = "title", limit: int = 2) -> list[str]:
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get(key)
            if title:
                out.append(str(title))
            if len(out) >= limit:
                break
        return out

    catalysts = []
    catalysts.extend(_top_titles(news_items))
    catalysts.extend(_top_titles(policy_items))
    catalysts = catalysts[:3]

    risks = []
    if risk_mode == "risk_off":
        risks = ["风险偏好走弱", "波动率上行"]
    elif risk_mode == "risk_on":
        risks = ["估值过热风险", "流动性边际收紧"]
    else:
        risks = ["宏观方向不明", "事件扰动"]

    long_candidates: list[dict] = []

    def _long_line(name: str, narrative: str, operation: str, cycle: str, score: float, start_signal: str) -> dict:
        status = "monitor" if (risk_mode == "risk_off" and "AI" in name) else "active"
        return {
            "name": name,
            "horizon": "long",
            "timeframe": timeframe_map.get("long"),
            "asset_class": "全球",
            "narrative": narrative,
            "operation": operation,
            "lifecycle": "accelerating" if "AI" in name else "emerging",
            "cycle": cycle,
            "risk_mode": risk_mode,
            "macro_cycle": macro_cycle,
            "status": status,
            "started_at": today,
            "start_signal": start_signal,
            "end_triggers": ["主线催化显著降温", "风险模式转为risk_off", "领先资产持续转弱"],
            "end_signal": "风险模式转为risk_off或领先资产趋势反转",
            "driver": "macro",
            "confidence": 0.68,
            "catalysts": catalysts,
            "risks": risks,
            "targets": [{"name": name, "type": "theme"}],
            "strategies": [{"name": "趋势跟随", "detail": "以回调/突破分批建仓"}],
            "estimated_end": "结构性主题，持续跟踪",
            "contingency": "若风险模式转为risk_off，降低权益暴露",
            "evidence": [
                f"risk_mode={risk_mode}",
                f"macro_cycle={macro_cycle}",
                f"QQQ相对SPY={tech_lead:+.2f}%",
            ],
            "score": score,
            "update_reason": f"theme_score={score:.2f}",
        }

    if theme_scores.get("AI/算力与半导体", 0) > 0 or tech_lead > 0.2:
        long_candidates.append(_long_line(
            "AI/算力与半导体",
            "科技成长领跑，AI 与算力基础设施成为长期主线",
            "逢回调配置核心科技权益与算力基础设施",
            "结构性上行",
            max(theme_scores.get("AI/算力与半导体", 0), tech_lead * 10),
            f"QQQ相对SPY强势({tech_lead:+.2f}%)",
        ))
    if theme_scores.get("能源与资源品", 0) > 0 or oil_pct > 1.0:
        long_candidates.append(_long_line(
            "能源安全与资源周期",
            "能源供给与地缘扰动推升资源品长期定价",
            "偏好能源/资源品与上游定价权资产",
            "资源周期上行",
            max(theme_scores.get("能源与资源品", 0), abs(oil_pct)),
            f"油价动能{oil_pct:+.2f}%",
        ))
    if theme_scores.get("地缘与国防", 0) >= 2:
        long_candidates.append(_long_line(
            "地缘安全与国防周期",
            "地缘扰动频发，国防与安全资产具备长期需求",
            "关注国防/安全链条与风险对冲资产",
            "地缘风险上行",
            theme_scores.get("地缘与国防", 0),
            "地缘冲突关键词高频出现",
        ))
    if not long_candidates:
        long_candidates.append(_long_line(
            "多资产均衡",
            "宏观不确定性下的均衡配置框架",
            "维持股债商品分散配置",
            "均衡轮动",
            1.0,
            "宏观不确定性提升，均衡配置需求上升",
        ))

    lines.extend(_select_lines(long_candidates, "long", desired=2))

    # 中期主线（基于宏观）
    cpi_trend = (global_macro.get("global_macro") or {}).get("us_cpi", {}).get("trend")
    unemp_trend = (global_macro.get("global_macro") or {}).get("us_unemployment", {}).get("trend")
    mid_candidates: list[dict] = []
    if cpi_trend == "↑" and unemp_trend == "↑":
        mid_name = "滞胀对冲"
        mid_op = "偏黄金/资源、控制权益波动"
    elif cpi_trend == "↓" and unemp_trend == "↑":
        mid_name = "去通胀放缓"
        mid_op = "偏防守与高质量资产"
    elif cpi_trend == "↑" and unemp_trend == "↓":
        mid_name = "过热与再通胀"
        mid_op = "控制久期，关注价值/资源"
    elif cpi_trend == "↓" and unemp_trend == "↓":
        mid_name = "软着陆复苏"
        mid_op = "适度增加权益与成长"
    else:
        mid_name = "宏观中性"
        mid_op = "保持分散与风险预算"

    mid_start_signal = f"CPI趋势{cpi_trend or '→'} + 就业趋势{unemp_trend or '→'}"
    mid_candidates.append({
        "name": mid_name,
        "horizon": "medium",
        "timeframe": timeframe_map.get("medium"),
        "asset_class": "全球",
        "narrative": f"通胀趋势{cpi_trend or '→'}、就业趋势{unemp_trend or '→'}",
        "operation": mid_op,
        "lifecycle": "emerging",
        "cycle": macro_cycle,
        "risk_mode": risk_mode,
        "macro_cycle": macro_cycle,
        "status": "active" if risk_mode != "risk_off" else "monitor",
        "started_at": today,
        "start_signal": mid_start_signal,
        "end_triggers": ["CPI/就业趋势反转", "风险模式显著切换"],
        "end_signal": "CPI/就业趋势反转或风险模式切换",
        "driver": "macro",
        "confidence": 0.6,
        "catalysts": catalysts[:2],
        "risks": risks,
        "targets": [{"name": mid_name, "type": "theme"}],
        "strategies": [{"name": "宏观对冲", "detail": "保持资产分散与久期控制"}],
        "estimated_end": "关注宏观趋势变化",
        "contingency": "若数据反转，快速调整仓位",
        "evidence": [
            mid_start_signal,
            f"risk_budget={risk_budget}" if risk_budget else "risk_budget:无数据",
        ],
        "score": theme_scores.get("消费与通胀", 0) + theme_scores.get("利率与央行政策", 0),
        "update_reason": f"macro_cycle={macro_cycle}",
    })

    rate_score = theme_scores.get("利率与央行政策", 0)
    if rate_score > 0:
        mid_candidates.append({
            "name": "政策利率路径",
            "horizon": "medium",
            "timeframe": timeframe_map.get("medium"),
            "asset_class": "全球",
            "narrative": "央行政策预期成为中期定价主轴",
            "operation": "关注利率敏感资产与久期管理",
            "lifecycle": "emerging",
            "cycle": macro_cycle,
            "risk_mode": risk_mode,
            "macro_cycle": macro_cycle,
            "status": "active",
            "started_at": today,
            "start_signal": "政策/利率关键词高频出现",
            "end_triggers": ["政策预期转向", "通胀/就业趋势反转"],
            "end_signal": "政策预期转向",
            "driver": "macro",
            "confidence": 0.58,
            "catalysts": catalysts[:2],
            "risks": risks,
            "targets": [{"name": "利率敏感资产", "type": "macro"}],
            "strategies": [{"name": "久期管理", "detail": "根据政策预期调整久期风险"}],
            "estimated_end": "跟随政策预期变化",
            "contingency": "预期逆转时快速降风险",
            "evidence": ["policy_keywords_high"],
            "score": rate_score,
            "update_reason": "policy_keywords",
        })

    lines.extend(_select_lines(mid_candidates, "medium", desired=2))

    # 短期主线（多条）
    short_candidates: list[dict] = []
    short_name = "风险偏好回升" if risk_mode == "risk_on" else "防守降波" if risk_mode == "risk_off" else "风险中性"
    short_start_signal = f"risk_mode={risk_mode}, VIX趋势={_trend('^VIX') or '无数据'}"
    short_candidates.append({
        "name": short_name,
        "horizon": "short",
        "timeframe": timeframe_map.get("short"),
        "asset_class": "全球",
        "narrative": f"risk_mode={risk_mode}, 风险等级={risk_level}",
        "operation": "增加权益暴露" if risk_mode == "risk_on" else "降低权益/增加现金" if risk_mode == "risk_off" else "保持中性配置",
        "lifecycle": "accelerating" if risk_mode == "risk_on" else "declining" if risk_mode == "risk_off" else "emerging",
        "cycle": "风险偏好上行" if risk_mode == "risk_on" else "风险偏好下行" if risk_mode == "risk_off" else "风险中性",
        "risk_mode": risk_mode,
        "macro_cycle": macro_cycle,
        "status": "active" if risk_mode != "risk_off" else "monitor",
        "started_at": today,
        "start_signal": short_start_signal,
        "end_triggers": ["risk_mode切换", "风险等级上调"],
        "end_signal": "risk_mode切换或风险等级上调",
        "driver": "sentiment",
        "confidence": 0.55,
        "catalysts": catalysts[:1],
        "risks": risks,
        "targets": [{"name": short_name, "type": "theme"}],
        "strategies": [{"name": "风险控制", "detail": "仓位随风险等级调整"}],
        "estimated_end": "1-3月视风险模式而定",
        "contingency": "风险模式转为risk_off时快速降仓",
        "evidence": [
            short_start_signal,
            f"asset_groups={asset_groups}" if asset_groups else "asset_groups:无数据",
        ],
        "score": abs(risk_score) if "risk_score" in locals() else 1.0,
        "update_reason": f"risk_mode={risk_mode}",
    })

    commodity_mom = asset_groups.get("commodities")
    rates_mom = asset_groups.get("rates")
    if isinstance(commodity_mom, (int, float)) and isinstance(rates_mom, (int, float)):
        if commodity_mom - rates_mom > 0.5:
            short_candidates.append({
                "name": "商品强势/利率承压",
                "horizon": "short",
                "timeframe": timeframe_map.get("short"),
                "asset_class": "全球",
                "narrative": "商品动量显著强于利率资产，短期偏资源对冲",
                "operation": "提高商品/资源暴露，降低长久期风险",
                "lifecycle": "emerging",
                "cycle": "资源相对占优",
                "risk_mode": risk_mode,
                "macro_cycle": macro_cycle,
                "status": "active",
                "started_at": today,
                "start_signal": f"commodities={commodity_mom}, rates={rates_mom}",
                "end_triggers": ["商品动量回落", "利率资产反弹"],
                "end_signal": "商品动量回落",
                "driver": "cross-asset",
                "confidence": 0.54,
                "catalysts": catalysts[:1],
                "risks": risks,
                "targets": [{"name": "商品/资源", "type": "asset"}],
                "strategies": [{"name": "相对强弱", "detail": "商品强于利率时短期偏配"}],
                "estimated_end": "1-3月",
                "contingency": "动量反转时快速降低配置",
                "evidence": [f"commodities={commodity_mom}", f"rates={rates_mom}"],
                "score": commodity_mom - rates_mom,
                "update_reason": "asset_groups",
            })

    lines.extend(_select_lines(short_candidates, "short", desired=2))

    # 超短期主线（事件驱动）多条
    ultra_candidates: list[dict] = []
    if events or news_items:
        top_event = events[0] if events else None
        ultra_candidates.append({
            "name": "事件驱动扰动",
            "horizon": "ultra_short",
            "timeframe": timeframe_map.get("ultra_short"),
            "asset_class": "全球",
            "narrative": f"近期事件/新闻驱动波动，关注{top_event.get('event') if isinstance(top_event, dict) else '关键宏观事件'}",
            "operation": "保留对冲/控制隔夜风险",
            "lifecycle": "emerging",
            "cycle": "事件驱动",
            "risk_mode": risk_mode,
            "macro_cycle": macro_cycle,
            "status": "active",
            "started_at": today,
            "start_signal": f"事件日历/新闻高频触发: {top_event.get('event') if isinstance(top_event, dict) else '宏观事件'}",
            "end_triggers": ["事件风险显著降温", "波动率回落"],
            "end_signal": "事件风险降温且波动率回落",
            "driver": "event",
            "confidence": 0.5,
            "catalysts": catalysts[:2],
            "risks": ["事件不确定性", "流动性收缩"],
            "targets": [{"name": "波动率/避险资产", "type": "hedge"}],
            "strategies": [{"name": "事件对冲", "detail": "降低隔夜敞口"}],
            "estimated_end": "1-2周内",
            "contingency": "事件缓和后恢复常态仓位",
            "evidence": [
                f"event={top_event.get('event') if isinstance(top_event, dict) else '无'}",
                f"news_count={len(news_items)}",
            ],
            "score": len(events) + len(news_items),
            "update_reason": "event-driven",
        })

    vix_trend = _trend("^VIX")
    if vix_trend in {"↑", "→"} or risk_mode == "risk_off":
        ultra_candidates.append({
            "name": "波动率/流动性防守",
            "horizon": "ultra_short",
            "timeframe": timeframe_map.get("ultra_short"),
            "asset_class": "全球",
            "narrative": "波动率偏高或风险模式偏弱，超短期以防守与对冲为主",
            "operation": "降低隔夜敞口，保留对冲仓位",
            "lifecycle": "emerging",
            "cycle": "风险控制",
            "risk_mode": risk_mode,
            "macro_cycle": macro_cycle,
            "status": "active",
            "started_at": today,
            "start_signal": f"VIX趋势={vix_trend or '无数据'}",
            "end_triggers": ["VIX显著回落", "risk_mode转为risk_on"],
            "end_signal": "波动率回落",
            "driver": "volatility",
            "confidence": 0.5,
            "catalysts": catalysts[:1],
            "risks": ["流动性收缩"],
            "targets": [{"name": "避险资产", "type": "hedge"}],
            "strategies": [{"name": "降波动", "detail": "减少隔夜风险，保持防守仓位"}],
            "estimated_end": "1-2周内",
            "contingency": "VIX回落后逐步恢复仓位",
            "evidence": [f"VIX趋势={vix_trend or '无数据'}"],
            "score": 1.0 if risk_mode == "risk_off" else 0.6,
            "update_reason": "volatility",
        })

    lines.extend(_select_lines(ultra_candidates, "ultra_short", desired=2))

    return lines


def _a_share_mainlines(snapshot: dict, global_lines: list[dict]) -> list[dict]:
    lines: list[dict] = []
    today = snapshot.get("date") or datetime.now().strftime("%Y-%m-%d")
    hot = snapshot.get("hot_themes") if isinstance(snapshot, dict) else []
    market = snapshot.get("market") if isinstance(snapshot, dict) else {}
    fried = market.get("fried") if isinstance(market, dict) else None
    limit_down = market.get("limit_down") if isinstance(market, dict) else None

    def lifecycle_from_theme(limitup: int, net_yi: float) -> str:
        if fried is not None and fried >= 30:
            return "peak"
        if limitup >= 12 or net_yi >= 8:
            return "accelerating"
        if limitup >= 6 or net_yi >= 3:
            return "emerging"
        if limit_down is not None and limit_down >= 10:
            return "declining"
        return "nascent"

    def cycle_from_lifecycle(lifecycle: str) -> str:
        mapping = {
            "nascent": "启动期",
            "emerging": "上行期",
            "accelerating": "加速期",
            "peak": "高潮/见顶",
            "declining": "退潮期",
        }
        return mapping.get(lifecycle, "未定")

    # map resonance
    global_names = [g.get("name") for g in global_lines if isinstance(g, dict) and g.get("name")]

    def _build_global_index(names: list[str]) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {
            "ai": [],
            "energy": [],
            "geo": [],
            "rates": [],
            "macro": [],
            "risk": [],
            "balance": [],
            "all": list(names),
        }

        def _has(text: str, keywords: list[str]) -> bool:
            return any(kw in text for kw in keywords)

        for name in names:
            text = str(name)
            if _has(text, ["AI", "算力", "半导体", "芯片", "GPU", "软件", "通信", "云计算", "数据中心"]):
                index["ai"].append(name)
            if _has(text, ["能源", "资源", "商品", "油", "气", "煤", "有色", "金属", "化工", "电力", "新能源", "光伏", "风电", "储能"]):
                index["energy"].append(name)
            if _has(text, ["地缘", "国防", "军工", "安全"]):
                index["geo"].append(name)
            if _has(text, ["政策", "利率", "央行", "加息", "降息"]):
                index["rates"].append(name)
            if _has(text, ["滞胀", "通胀", "软着陆", "去通胀", "复苏", "过热", "宏观"]):
                index["macro"].append(name)
            if _has(text, ["风险", "波动", "事件"]):
                index["risk"].append(name)
            if _has(text, ["均衡", "多资产"]):
                index["balance"].append(name)

        # de-dup while keeping order
        for key, items in index.items():
            seen = set()
            deduped = []
            for item in items:
                if item in seen:
                    continue
                seen.add(item)
                deduped.append(item)
            index[key] = deduped
        return index

    global_index = _build_global_index(global_names)

    def resonance(name: str) -> str:
        if not name:
            return ""
        mapping = {
            "AI": ["AI/算力与半导体", "AI"],
            "算力": ["AI/算力与半导体", "AI"],
            "芯片": ["AI/算力与半导体", "AI"],
            "半导体": ["AI/算力与半导体", "AI"],
            "软件": ["AI/算力与半导体", "AI"],
            "通信": ["AI/算力与半导体", "AI"],
            "云计算": ["AI/算力与半导体", "AI"],
            "新能源": ["能源安全与资源周期", "商品强势/利率承压", "能源"],
            "光伏": ["能源安全与资源周期", "商品强势/利率承压", "能源"],
            "储能": ["能源安全与资源周期", "商品强势/利率承压", "能源"],
            "电力": ["能源安全与资源周期", "商品强势/利率承压", "能源"],
            "电池": ["能源安全与资源周期", "商品强势/利率承压", "能源"],
            "氢能": ["能源安全与资源周期", "能源"],
            "氢能源": ["能源安全与资源周期", "能源"],
            "基础化工": ["商品强势/利率承压", "能源安全与资源周期"],
            "化学原料": ["商品强势/利率承压", "能源安全与资源周期"],
            "有色": ["商品强势/利率承压", "能源安全与资源周期"],
            "稀土": ["商品强势/利率承压", "能源安全与资源周期"],
            "军工": ["地缘安全与国防周期", "地缘与国防"],
            "国防": ["地缘安全与国防周期", "地缘与国防"],
            "航天": ["地缘安全与国防周期", "地缘与国防"],
            "油气": ["能源安全与资源周期", "能源与资源品", "能源"],
            "煤炭": ["能源安全与资源周期", "能源与资源品", "能源"],
            "银行": ["政策利率路径", "风险中性"],
            "保险": ["政策利率路径", "风险中性"],
            "券商": ["政策利率路径", "风险中性"],
            "高股息": ["政策利率路径", "风险中性"],
        }
        for key, candidates in mapping.items():
            if key in name:
                for gname in global_names:
                    if not gname:
                        continue
                    if any(cand in gname for cand in candidates):
                        return gname

        categories: list[str] = []
        if any(kw in name for kw in ["AI", "算力", "半导体", "芯片", "软件", "通信", "云计算", "数据中心"]):
            categories.append("ai")
        if any(kw in name for kw in ["新能源", "光伏", "风电", "储能", "电力", "电网", "电池", "锂", "稀土", "煤炭", "油气", "天然气", "有色", "钢铁", "化工", "资源", "黄金", "铜", "铝"]):
            categories.append("energy")
        if any(kw in name for kw in ["军工", "国防", "航天", "地缘", "安全", "军民"]):
            categories.append("geo")
        if any(kw in name for kw in ["银行", "保险", "券商", "利率", "债", "高股息", "分红"]):
            categories.append("rates")
        if any(kw in name for kw in ["消费", "医药", "农业", "食品", "地产", "基建", "通胀", "复苏", "周期"]):
            categories.append("macro")
        if any(kw in name for kw in ["情绪", "波动", "避险", "恐慌", "风险"]):
            categories.append("risk")

        for cat in categories:
            if global_index.get(cat):
                return global_index[cat][0]

        return global_names[0] if global_names else ""

    if isinstance(hot, list):
        for item in hot[:3]:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            limitup = int(item.get("limitup_count") or 0)
            net_yi = float(item.get("net_yi") or 0)
            lifecycle = lifecycle_from_theme(limitup, net_yi)
            status = "active" if lifecycle in {"emerging", "accelerating"} else "monitor" if lifecycle == "peak" else "exit" if lifecycle == "declining" else "observe"
            lines.append({
                "name": name,
                "horizon": "ultra_short",
                "timeframe": "1-2周",
                "asset_class": "A股",
                "narrative": f"{name} 资金净流入 {net_yi:.2f} 亿, 涨停 {limitup}",
                "operation": "顺势参与，分批试错" if lifecycle in {"emerging", "accelerating"} else "回避追高",
                "lifecycle": lifecycle,
                "cycle": cycle_from_lifecycle(lifecycle),
                "status": status,
                "started_at": today,
                "start_signal": f"净流入 {net_yi:.2f} 亿/涨停 {limitup}",
                "end_triggers": ["跌停扩散>10", "炸板显著上升", "资金净流入转负"],
                "end_signal": "跌停扩散或资金净流入转负",
                "global_link": resonance(name),
                "driver": "capital",
                "confidence": 0.55,
                "catalysts": [f"{name} 题材活跃", f"资金净流入 {net_yi:.2f} 亿"],
                "risks": ["情绪退潮", "监管风险"],
                "targets": [{"name": name, "type": "theme"}],
                "strategies": [{"name": "短线节奏", "detail": "分批试错，严格止损"}],
                "estimated_end": "1-2周",
                "contingency": "跌停扩散或资金转负立即退出",
                "evidence": [
                    f"limitup={limitup}",
                    f"net_yi={net_yi:.2f}",
                ],
                "update_reason": f"limitup={limitup}, net_yi={net_yi:.2f}",
            })

    return lines


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _market_risk(snapshot: dict[str, Any]) -> dict[str, Any]:
    market = snapshot.get("market") if isinstance(snapshot, dict) else {}
    if not isinstance(market, dict):
        market = {}
    sentiment = _safe_float(market.get("sentiment_index"))
    limit_down = _safe_float(market.get("limit_down"))
    fried = _safe_float(market.get("fried"))
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
    level = "red" if score >= 5 else "orange" if score >= 3 else "yellow" if score >= 1 else "green"
    status = "LOCKOUT" if level in {"red", "orange"} else "FULL"
    return {
        "risk_score": score,
        "risk_level": level,
        "themesurfer_status": status,
        "allow_new_positions": status == "FULL",
        "reasons": reasons,
        "inputs": {
            "sentiment_index": sentiment,
            "limit_down": limit_down,
            "fried": fried,
        },
    }


def _store_themes(store: dict[str, Any]) -> list[dict[str, Any]]:
    themes = store.get("themes") if isinstance(store, dict) else {}
    if isinstance(themes, dict):
        return [theme for theme in themes.values() if isinstance(theme, dict)]
    if isinstance(themes, list):
        return [theme for theme in themes if isinstance(theme, dict)]
    return []


def _payload_themes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    themes = payload.get("themes")
    return [theme for theme in themes if isinstance(theme, dict)] if isinstance(themes, list) else []


def _snapshot_theme_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sectors = _summarize_sectors(snapshot)
    for item in sectors.get("strong", []):
        row = dict(item)
        row.setdefault("status", "active")
        row.setdefault("lifecycle", "emerging")
        rows.append(row)
    hot = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else []
    for item in hot:
        if not isinstance(item, dict):
            continue
        rows.append({
            "name": item.get("name"),
            "status": "active",
            "lifecycle": "accelerating" if (_safe_float(item.get("limitup_count")) or 0) >= 3 else "emerging",
            "net_yi": item.get("net_yi"),
            "limitup_count": item.get("limitup_count"),
            "top_stocks": item.get("top_stocks") if isinstance(item.get("top_stocks"), list) else [],
        })
    return [row for row in rows if row.get("name")]


def _build_event_analysis(command: str, payload: dict[str, Any], prewarm: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    if not events:
        events = prewarm.get("tushare_eco_cal") if isinstance(prewarm.get("tushare_eco_cal"), list) else []
    if not events:
        events = prewarm.get("jin10_important_news") if isinstance(prewarm.get("jin10_important_news"), list) else []
    themes = _payload_themes(payload) or _snapshot_theme_rows(snapshot)
    impacted: list[dict[str, Any]] = []
    for event in events[:30]:
        if not isinstance(event, dict):
            continue
        text = " ".join(str(event.get(key) or "") for key in ("title", "event", "summary", "content"))
        matched = []
        for theme in themes:
            name = str(theme.get("name") or "")
            if name and name in text:
                matched.append(name)
        risk_flag = any(keyword in text for keyword in ("加息", "制裁", "冲突", "衰退", "CPI", "通胀", "风险"))
        impacted.append({
            "event": event.get("title") or event.get("event") or text[:80],
            "matched_themes": matched,
            "risk_flag": risk_flag,
            "source": event.get("source") or "payload/prewarm",
        })
    return {
        "events": impacted,
        "theme_count": len(themes),
        "source": "payload.events/prewarm.events + themes",
    }


def _build_rebalance_check(payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    store = _load_theme_store()
    themes = _payload_themes(payload) or _store_themes(store) or _snapshot_theme_rows(snapshot)
    risk = _market_risk(snapshot)
    actions: list[dict[str, Any]] = []
    for theme in themes[:30]:
        lifecycle = str(theme.get("lifecycle") or theme.get("cycle") or "")
        status = str(theme.get("status") or "")
        action = "hold"
        reason = "theme remains active"
        if risk["themesurfer_status"] == "LOCKOUT":
            action = "no_new_adds"
            reason = "market risk lockout"
        if lifecycle in {"declining", "exit"} or status == "exit":
            action = "review_exit"
            reason = "theme lifecycle weakening"
        actions.append({
            "theme": theme.get("name"),
            "action": action,
            "reason": reason,
            "paper_only": True,
        })
    return {
        "risk": risk,
        "actions": actions,
        "source": "theme-store/snapshot + market risk",
    }


def _build_theme_tracker(payload: dict[str, Any]) -> dict[str, Any]:
    store = _load_theme_store()
    themes = _store_themes(store)
    status_filter = payload.get("status")
    horizon_filter = payload.get("horizon")
    if status_filter:
        themes = [theme for theme in themes if theme.get("status") == status_filter]
    if horizon_filter:
        themes = [theme for theme in themes if theme.get("horizon") == horizon_filter]
    return {
        "themes": themes,
        "count": len(themes),
        "store_path": str(_theme_store_path()),
        "source": "theme-store",
    }


def _build_themesurfer_check(command: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    risk = _market_risk(snapshot)
    return {
        "status": risk["themesurfer_status"],
        "allow_new_positions": risk["allow_new_positions"],
        "risk_level": risk["risk_level"],
        "risk_score": risk["risk_score"],
        "reasons": risk["reasons"],
        "inputs": risk["inputs"],
        "source": "hhxg_snapshot.market",
    }


def _build_themesurfer_weekly_stats() -> dict[str, Any]:
    themes = _store_themes(_load_theme_store())
    lifecycle_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    updates = 0
    for theme in themes:
        lifecycle = str(theme.get("lifecycle") or "unknown")
        status = str(theme.get("status") or "unknown")
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        history = theme.get("history") if isinstance(theme.get("history"), list) else []
        updates += len(history)
    return {
        "theme_count": len(themes),
        "lifecycle_counts": lifecycle_counts,
        "status_counts": status_counts,
        "history_events": updates,
        "source": "theme-store",
    }


def _incomplete_reasons(command: str, result: dict[str, Any]) -> list[str]:
    if command == "discover-themes":
        if not result.get("themes") and not result.get("weak"):
            return ["theme_snapshot_missing"]
    if command == "sector-cycle-panorama":
        snapshot = result.get("cycle_snapshot") if isinstance(result.get("cycle_snapshot"), dict) else {}
        if not snapshot.get("strong") and not snapshot.get("weak"):
            return ["sector_cycle_snapshot_missing"]
    if command == "event-analysis":
        if not result.get("events"):
            return ["event_inputs_missing"]
    if command == "theme-tracker":
        if not result.get("themes"):
            return ["theme_store_missing"]
    if command == "rebalance-check":
        if not result.get("actions"):
            return ["theme_inputs_missing"]
    if command in {"themesurfer-check", "themesurfer-signal"}:
        inputs = result.get("inputs") if isinstance(result.get("inputs"), dict) else {}
        if not any(value is not None for value in inputs.values()):
            return ["market_risk_inputs_missing"]
    if command == "themesurfer-weekly-stats":
        if not result.get("theme_count"):
            return ["theme_store_missing"]
    if command == "mainline-update":
        if not result.get("updated"):
            return ["mainline_inputs_missing"]
    if command == "macro-analysis":
        if not result.get("global") and not result.get("domestic"):
            return ["macro_inputs_missing"]
    if command == "global-medium-long-strategy":
        if not result.get("mainlines") and not result.get("global_assets") and not result.get("risk_budget"):
            return ["global_strategy_inputs_missing"]
    return []


def _wrap_result(command: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    errors = _incomplete_reasons(command, result)
    if errors:
        return _fail(command, payload, errors)
    output = _base_output(command, payload)
    output["sources"] = _normalize_sources(result.get("source"))
    if result.get("store_path"):
        output["artifacts"] = [str(result["store_path"])]
    output["result"] = result
    return output


def _build_result(command: str, payload: dict[str, Any], prewarm: dict) -> dict:
    snapshot = _extract_snapshot(prewarm)

    if command == "discover-themes":
        sectors = _summarize_sectors(snapshot)
        return {
            "themes": sectors.get("strong", []),
            "weak": sectors.get("weak", []),
            "source": "hhxg_snapshot.sectors",
        }

    if command == "sector-cycle-panorama":
        sectors = _summarize_sectors(snapshot)
        return {
            "cycle_snapshot": sectors,
            "note": "no cycle model; using net_yi bias as proxy",
            "source": "hhxg_snapshot.sectors",
        }

    if command == "event-analysis":
        return _build_event_analysis(command, payload, prewarm, snapshot)

    if command == "rebalance-check":
        return _build_rebalance_check(payload, snapshot)

    if command == "theme-tracker":
        return _build_theme_tracker(payload)

    if command == "themesurfer-check":
        return _build_themesurfer_check(command, snapshot)

    if command == "themesurfer-signal":
        result = _build_themesurfer_check(command, snapshot)
        result["signal_version"] = "themesurfer-v1"
        result["source"] = "hhxg_snapshot.market"
        return result

    if command == "themesurfer-weekly-stats":
        return _build_themesurfer_weekly_stats()

    if command == "mainline-update":
        store = _load_theme_store()
        global_result = _call_macro_regime("global-macro-analysis") or {}
        policy_items = prewarm.get("tushare_policy") if isinstance(prewarm.get("tushare_policy"), list) else []
        research_reports = prewarm.get("tushare_research_report") if isinstance(prewarm.get("tushare_research_report"), list) else []
        global_lines = _global_mainlines(
            global_result,
            global_result.get("global_assets", []),
            global_result.get("global_news", []),
            policy_items,
            research_reports,
            global_result.get("global_events", []),
            store=store,
        )
        a_share_lines = _a_share_mainlines(snapshot, global_lines)

        updated = []
        for line in global_lines + a_share_lines:
            updated.append(_upsert_theme(store, line))
        _save_theme_store(store)
        return {
            "updated": len(updated),
            "themes": updated,
            "store_path": str(_theme_store_path()),
        }

    if command == "global-medium-long-strategy":
        store = _load_theme_store()
        global_result = _call_macro_regime("global-macro-analysis") or {}
        global_lines = []
        themes = store.get("themes") if isinstance(store, dict) else {}
        if isinstance(themes, dict):
            global_lines = [t for t in themes.values() if isinstance(t, dict) and str(t.get("asset_class", "")).startswith("全球")]
        risk_mode = global_result.get("risk_mode") or "neutral"
        allocation = {
            "risk_on": {"equity": 0.45, "bond": 0.2, "gold": 0.1, "commodity": 0.1, "cash": 0.15},
            "neutral": {"equity": 0.35, "bond": 0.25, "gold": 0.1, "commodity": 0.1, "cash": 0.2},
            "risk_off": {"equity": 0.15, "bond": 0.3, "gold": 0.2, "commodity": 0.05, "cash": 0.3},
        }.get(risk_mode, {"equity": 0.35, "bond": 0.25, "gold": 0.1, "commodity": 0.1, "cash": 0.2})
        return {
            "risk_mode": risk_mode,
            "macro_cycle": global_result.get("macro_cycle"),
            "risk_budget": global_result.get("risk_budget"),
            "asset_trends": global_result.get("asset_trends"),
            "global_assets": (global_result.get("global_assets") or [])[:12],
            "mainlines": global_lines[:8],
            "allocation_hint": allocation,
            "source": "macro-regime.global-macro-analysis + theme-store",
        }

    if command == "macro-analysis":
        global_result = _call_macro_regime("global-macro-analysis") or {}
        domestic_result = _call_macro_regime("domestic-macro") or {}
        return {
            "global": global_result,
            "domestic": domestic_result,
            "source": "macro-regime",
        }

    raise ValueError(f"unknown_command:{command}")


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

    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
        prewarm = _load_latest_prewarm()
        result = _build_result(args.command, payload, prewarm)
        output = _wrap_result(args.command, payload, result)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
