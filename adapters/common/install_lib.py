from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SKILLPACK = REPO_ROOT / "skills" / "aegis-alpha"
MANIFEST = REPO_ROOT / "skillpack.json"
CORE_DIR_NAME = ".aegis-alpha-core"


def parse_args(default_target: Path, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--target", type=Path, default=default_target)
    parser.add_argument("--force", action="store_true", help="Replace existing Aegis Alpha install directories.")
    return parser.parse_args()


def replace_or_fail(target: Path, force: bool) -> None:
    if not target.exists():
        return
    if not force:
        raise SystemExit(f"target already exists: {target} (use --force to replace it)")
    if not target.is_dir():
        raise SystemExit(f"target exists and is not a directory: {target}")
    shutil.rmtree(target)


def ensure_targets_available(targets: list[Path], force: bool) -> None:
    existing = [target for target in targets if target.exists()]
    if existing and not force:
        rendered = "\n".join(f"- {target}" for target in existing)
        raise SystemExit(f"target already exists (use --force to replace):\n{rendered}")
    for target in existing:
        if not target.is_dir():
            raise SystemExit(f"target exists and is not a directory: {target}")
        shutil.rmtree(target)


def copy_canonical_package(target: Path, force: bool) -> None:
    replace_or_fail(target, force)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CANONICAL_SKILLPACK, target)


def load_public_skills() -> list[str]:
    with MANIFEST.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    skills = manifest.get("public_skills", [])
    if not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills):
        raise SystemExit("skillpack.json public_skills must be a string list")
    return skills


def copy_shared_core(skills_root: Path) -> Path:
    target = skills_root / CORE_DIR_NAME
    shutil.copytree(CANONICAL_SKILLPACK, target)
    return target


def install_aggregate_skill(adapter_dir: Path, skills_root: Path) -> Path:
    target = skills_root / "aegis-alpha"
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(adapter_dir / "SKILL.md", target / "SKILL.md")
    return target


def _public_description(skill: str) -> str:
    skill_file = CANONICAL_SKILLPACK / skill / "SKILL.md"
    if not skill_file.exists():
        raise SystemExit(f"public skill is missing SKILL.md: {skill}")
    in_frontmatter = False
    for line in skill_file.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if in_frontmatter and line.startswith("description:"):
            value = line.split(":", 1)[1].strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value
    return f"Aegis Alpha public skill: {skill}."


def _wrapper_body(skill: str) -> str:
    description = _public_description(skill)
    wrapper_description = (
        f"Use this Aegis Alpha public skill wrapper for {description} "
        "Research-only; never use for live trading, executable advice, "
        "allocation authorization, or external order execution."
    )
    return f"""---
name: aegis-alpha-{skill}
description: {json.dumps(wrapper_description)}
metadata:
  short-description: Aegis Alpha {skill}
---

# Aegis Alpha / {skill}

This wrapper exposes the canonical public skill `{skill}` from
`../{CORE_DIR_NAME}/{skill}`.

## Safety Rules

- Treat every output as research-only unless it explicitly says otherwise.
- Keep `decision_allowed=false`.
- Missing critical evidence must fail closed.
- Do not infer empty portfolios, empty opportunities, or no risk from missing data.
- Paper trade plans require human confirmation outside the skill.

## How To Use

Read `../{CORE_DIR_NAME}/{skill}/SKILL.md` only after this wrapper is triggered.
Inspect `../{CORE_DIR_NAME}/{skill}/data/command-manifest.json` and
`../{CORE_DIR_NAME}/{skill}/references/contracts.md` when choosing a command.

Run commands from this wrapper directory with:

```bash
python3 ../{CORE_DIR_NAME}/{skill}/scripts/dispatch.py --command <command> --payload '<json>'
```

Set `AEGIS_ALPHA_WORKSPACE` to control runtime artifacts. If unset, dispatchers
use `~/.aegis-alpha/workspace`.
"""


def write_public_skill_wrappers(skills_root: Path) -> list[Path]:
    written: list[Path] = []
    for skill in load_public_skills():
        target = skills_root / f"aegis-alpha-{skill}"
        target.mkdir(parents=True, exist_ok=False)
        (target / "SKILL.md").write_text(_wrapper_body(skill), encoding="utf-8")
        written.append(target)
    return written


def install_wrapper_skillset(adapter_dir: Path, skills_root: Path, force: bool) -> list[Path]:
    skills_root = skills_root.expanduser()
    skills_root.mkdir(parents=True, exist_ok=True)
    public_targets = [skills_root / f"aegis-alpha-{skill}" for skill in load_public_skills()]
    targets = [skills_root / CORE_DIR_NAME, skills_root / "aegis-alpha", *public_targets]
    ensure_targets_available(targets, force)
    installed = [copy_shared_core(skills_root), install_aggregate_skill(adapter_dir, skills_root)]
    installed.extend(write_public_skill_wrappers(skills_root))
    return installed


def env_home(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else fallback


def print_success(agent: str, target: Path) -> None:
    print(f"Installed Aegis Alpha for {agent}: {target}")
