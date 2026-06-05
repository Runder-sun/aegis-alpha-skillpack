# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from dataclasses import dataclass


SECTION_THEMES = {
    "dashboard": "indigo",
    "core": "blue",
    "risk": "red",
    "macro": "turquoise",
    "global": "purple",
    "scan": "orange",
    "portfolio": "green",
    "decision": "carmine",
    "default": "blue",
}


def md_element(content: str, element_id: str = "") -> dict:
    el = {"tag": "markdown", "content": content}
    if element_id:
        el["element_id"] = element_id
    return el


def hr_element() -> dict:
    return {"tag": "hr"}


def note_element(texts: list[str]) -> dict:
    content = " · ".join(texts)
    return md_element(f"<font color='grey'>{content}</font>")


def column_set(columns: list[dict], flex_mode: str = "none",
               background_style: str = "default") -> dict:
    return {
        "tag": "column_set",
        "flex_mode": flex_mode,
        "background_style": background_style,
        "columns": columns,
    }


def column(elements: list[dict], width: str = "weighted",
           weight: int = 1, vertical_align: str = "top") -> dict:
    return {
        "tag": "column",
        "width": width,
        "weight": weight,
        "vertical_align": vertical_align,
        "elements": elements,
    }


def metric_column(label: str, value: str) -> dict:
    md = f"**{label}**\n{value}"
    return column([md_element(md)], weight=1, vertical_align="center")


def metric_row(metrics: list[tuple[str, str]]) -> dict:
    cols = [metric_column(lbl, val) for lbl, val in metrics]
    return column_set(cols, flex_mode="bisect" if len(cols) == 2
                      else "trisect" if len(cols) == 3 else "none",
                      background_style="grey")


def build_card(
    title: str,
    elements: list[dict],
    theme: str = "blue",
    subtitle: str = "",
    icon: str = "",
) -> dict:
    header = {
        "title": {"tag": "plain_text", "content": f"{icon} {title}" if icon else title},
        "template": theme,
    }
    if subtitle:
        header["subtitle"] = {"tag": "plain_text", "content": subtitle}

    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": header,
        "body": {"elements": elements},
    }


@dataclass
class ReportSection:
    number: int
    title: str
    content: str
    theme: str = "blue"
    icon: str = ""


def parse_report_sections(report_text: str) -> list[ReportSection]:
    section_pattern = re.compile(
        r'^###\s+Section\s+(\d+)\s*[:：]\s*(.+?)$',
        re.MULTILINE
    )
    matches = list(section_pattern.finditer(report_text))
    if not matches:
        return [ReportSection(0, "报告", report_text, "blue", "📋")]

    section_config = {
        1: ("core", "🎯"),
        2: ("risk", "⚠️"),
        3: ("macro", "🌍"),
        4: ("global", "🌐"),
        5: ("scan", "🔍"),
        6: ("portfolio", "📂"),
        7: ("decision", "📊"),
    }

    sections: list[ReportSection] = []
    for i, match in enumerate(matches):
        sec_num = int(match.group(1))
        sec_title_raw = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report_text)
        content = report_text[start:end].strip()
        theme_key, icon = section_config.get(sec_num, ("default", "📋"))
        title_has_emoji = any(ord(c) > 0x1F000 for c in sec_title_raw[:3])
        display_icon = "" if title_has_emoji else icon
        sections.append(ReportSection(
            number=sec_num,
            title=sec_title_raw,
            content=content,
            theme=SECTION_THEMES.get(theme_key, "blue"),
            icon=display_icon,
        ))
    return sections


def _extract_dashboard_value(
    report_text: str,
    labels: list[str],
    *,
    prefer_bold: bool = False,
    shorten: bool = False,
    wrap_bold: bool = False,
) -> str:
    for label in labels:
        match = re.search(rf'\*\*{re.escape(label)}\*\*\s*[:：]\s*(.+?)(?:\n|$)', report_text)
        if not match:
            continue
        raw = match.group(1).strip()
        if prefer_bold:
            bold_match = re.search(r'\*\*(.+?)\*\*', raw)
            if bold_match:
                value = bold_match.group(1).strip()
                return f"**{value}**" if wrap_bold else value
        if shorten:
            raw = re.split(r'[—–；;，,。]', raw, maxsplit=1)[0].strip()
        return f"**{raw}**" if wrap_bold else raw
    return "—"


def build_dashboard_card(report_text: str, date_str: str = "") -> dict:
    elements = []
    risk_val = _extract_dashboard_value(
        report_text,
        ["风险等级", "全球风险等级"],
        prefer_bold=True,
    )
    pos_val = _extract_dashboard_value(
        report_text,
        ["仓位上限", "仓位上限（硬约束）"],
        prefer_bold=True,
    )
    tone_val = _extract_dashboard_value(
        report_text,
        ["整体基调", "基调"],
        prefer_bold=True,
        shorten=True,
        wrap_bold=True,
    )
    elements.append(metric_row([
        ("🎯 整体基调", tone_val),
        ("⚠️ 风险等级", risk_val),
        ("💰 仓位上限", pos_val),
    ]))
    elements.append(hr_element())
    footer_text = f"🕐 {date_str}" if date_str else "📋 详细分析见后续消息"
    elements.append(note_element([footer_text, "Aegis Alpha"]))
    return build_card(
        title="🌙 策略速览",
        elements=elements,
        theme=SECTION_THEMES["dashboard"],
        subtitle=date_str,
    )


def build_section_card(section: ReportSection) -> dict:
    elements: list[dict] = []
    content = section.content
    max_bytes = 28000
    if len(content.encode("utf-8")) <= max_bytes:
        elements.append(md_element(content))
    else:
        parts = re.split(r'\n(?=\*\*\d+\.\d+|\n#{1,4}\s)', content)
        current = ""
        for p in parts:
            test = current + "\n" + p if current else p
            if len(test.encode("utf-8")) > max_bytes:
                if current:
                    elements.append(md_element(current))
                    elements.append(hr_element())
                current = p
            else:
                current = test
        if current:
            elements.append(md_element(current))
    elements.append(hr_element())
    elements.append(note_element([f"Section {section.number}", "Aegis Alpha"]))
    display_title = f"{section.icon} {section.title}".strip() if section.icon else section.title
    return build_card(title=display_title, elements=elements, theme=section.theme)


def build_report_cards(report_text: str, date_str: str = "", include_dashboard: bool = True) -> list[dict]:
    cards: list[dict] = []
    if include_dashboard:
        cards.append(build_dashboard_card(report_text, date_str))
    sections = parse_report_sections(report_text)
    for sec in sections:
        cards.append(build_section_card(sec))
    return cards


PUSH_THEMES = {
    "nightly": ("indigo", "🌙"),
    "morning": ("wathet", "☀️"),
    "intraday": ("green", "📊"),
    "weekly": ("purple", "📋"),
    "heartbeat": ("orange", "💓"),
    "alert": ("red", "🚨"),
    "chat": ("blue", "🤖"),
}


def build_push_card(content: str, push_type: str = "chat", title: str = "", date_str: str = "") -> dict:
    theme, icon = PUSH_THEMES.get(push_type, ("blue", "🤖"))
    default_titles = {
        "nightly": "晚间策略规划",
        "morning": "盘前计划确认",
        "intraday": "收盘复盘",
        "weekly": "周度绩效报告",
        "heartbeat": "盘中心跳监控",
        "alert": "盘中风险预警",
        "chat": "Aegis Alpha",
    }
    card_title = title or default_titles.get(push_type, "Aegis Alpha")
    elements = [md_element(content)]
    elements.append(hr_element())
    footer_parts = []
    if date_str:
        footer_parts.append(f"🕐 {date_str}")
    footer_parts.append("Aegis Alpha")
    elements.append(note_element(footer_parts))
    return build_card(title=f"{icon} {card_title}", elements=elements, theme=theme, subtitle=date_str)


def cards_to_payloads(cards: list[dict]) -> list[dict]:
    return [{"msg_type": "interactive", "content": json.dumps(card, ensure_ascii=False)} for card in cards]
