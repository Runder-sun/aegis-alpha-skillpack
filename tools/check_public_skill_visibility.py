#!/usr/bin/env python3
"""Verify Aegis Alpha public/internal surface declarations."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "skills" / "aegis-alpha"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end < 0:
        return ""
    return text[3:end]


def _frontmatter_name(frontmatter: str, fallback: str) -> str:
    match = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        return fallback
    value = match.group(1).strip()
    if value and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _is_internal(frontmatter: str) -> bool:
    return bool(re.search(r"^\s*internal:\s*true\s*$", frontmatter, re.MULTILINE))


def check_visibility(source: Path) -> dict[str, Any]:
    surface = _load_json(source / "data" / "surface-map.json")
    public = set(surface.get("public_skills") or [])
    internal = set((surface.get("internal_skills") or {}).keys())
    public_limit = int(surface.get("public_skill_limit") or 15)

    observed: dict[str, dict[str, Any]] = {}
    for skill_md in sorted(source.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        fm = _frontmatter(_read_text(skill_md))
        name = _frontmatter_name(fm, skill_dir.name)
        observed[name] = {
            "path": str(skill_dir),
            "internal": _is_internal(fm),
        }

    observed_names = set(observed)
    missing_public = sorted(public - observed_names)
    missing_internal = sorted(internal - observed_names)
    undeclared_visible = sorted(name for name, meta in observed.items() if not meta["internal"] and name not in public)
    public_marked_internal = sorted(name for name in public if observed.get(name, {}).get("internal") is True)
    internal_not_marked = sorted(name for name in internal if observed.get(name, {}).get("internal") is not True)

    listed_public = sorted(name for name in public if name in observed and not observed[name]["internal"])
    return {
        "ok": not missing_public
        and not missing_internal
        and not undeclared_visible
        and not public_marked_internal
        and not internal_not_marked
        and len(public) <= public_limit,
        "public_limit": public_limit,
        "public_count_listed": len(listed_public),
        "listed_public": listed_public,
        "missing_public": missing_public,
        "missing_internal": missing_internal,
        "undeclared_visible": undeclared_visible,
        "public_marked_internal": public_marked_internal,
        "internal_not_marked": internal_not_marked,
    }


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Public Skill Visibility Check",
        "",
        f"- OK: {result.get('ok')}",
        f"- Public limit: {result.get('public_limit')}",
        f"- Public count listed: {result.get('public_count_listed')}",
        "",
        "## Listed Public Skills",
        "",
    ]
    lines.extend(f"- `{name}`" for name in result.get("listed_public", []))
    for key in ("missing_public", "missing_internal", "undeclared_visible", "public_marked_internal", "internal_not_marked"):
        values = result.get(key) or []
        if values:
            lines.extend(["", f"## {key}", ""])
            lines.extend(f"- `{name}`" for name in values)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = check_visibility(args.source.expanduser().resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "public-skill-visibility.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(result, args.output_dir / "public-skill-visibility.md")
    print(json.dumps({"ok": result.get("ok")}, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
