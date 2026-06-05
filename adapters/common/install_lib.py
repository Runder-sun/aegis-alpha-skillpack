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
RESOURCE_DIRS = ("data", "references", "assets", "examples", "agents", "scripts")


def parse_args(default_target: Path, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--target", type=Path, default=default_target)
    parser.add_argument("--force", action="store_true", help="Replace existing Aegis Alpha install directories.")
    parser.add_argument(
        "--link-mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="For Codex/Claude native skill installs, expose bundled resources as symlinks or copied files.",
    )
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


def _original_skill_body(skill: str) -> str:
    skill_file = CANONICAL_SKILLPACK / skill / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for idx, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "\n".join(lines[idx + 1 :]).strip() + "\n"
    return text.strip() + "\n"


def _native_skill_body(skill: str) -> str:
    description = _public_description(skill)
    native_description = (
        f"Use this Aegis Alpha native public skill for {description} "
        "Research-only; never use for live trading, executable advice, "
        "allocation authorization, or external order execution."
    )
    original_body = _original_skill_body(skill)
    return f"""---
name: aegis-alpha-{skill}
description: {json.dumps(native_description)}
metadata:
  short-description: Aegis Alpha {skill}
---

# Aegis Alpha / {skill}

This native public skill is materialized from the canonical Aegis Alpha skill
`{skill}`. Bundled resources in this directory are linked or copied from the
shared runtime core at `../{CORE_DIR_NAME}/{skill}`.

## Safety Rules

- Treat every output as research-only unless it explicitly says otherwise.
- Keep `decision_allowed=false`.
- Missing critical evidence must fail closed.
- Do not infer empty portfolios, empty opportunities, or no risk from missing data.
- Paper trade plans require human confirmation outside the skill.

## Resource Layout

- `scripts/`: deterministic command dispatchers.
- `data/`: command manifests and machine-readable contracts.
- `references/`: contract docs and domain references.
- `assets/`, `examples/`, `agents/`: optional bundled skill resources.

Run commands from this skill directory with:

```bash
python3 scripts/dispatch.py --command <command> --payload '<json>'
```

Set `AEGIS_ALPHA_WORKSPACE` to control runtime artifacts. If unset, dispatchers
use `~/.aegis-alpha/workspace`.

## Canonical Skill Instructions

{original_body}
"""


def _relative_symlink(src: Path, dst: Path) -> None:
    rel = os.path.relpath(src, dst.parent)
    os.symlink(rel, dst, target_is_directory=src.is_dir())


def _write_dispatch_shim(target: Path, skill: str) -> None:
    scripts_dir = target / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shim = f"""#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path


CORE_DISPATCH = Path(__file__).resolve().parents[2] / "{CORE_DIR_NAME}" / "{skill}" / "scripts" / "dispatch.py"
runpy.run_path(str(CORE_DISPATCH), run_name="__main__")
"""
    dispatch = scripts_dir / "dispatch.py"
    dispatch.write_text(shim, encoding="utf-8")
    dispatch.chmod(0o755)


def _materialize_resources(target: Path, core_skill: Path, skill: str, link_mode: str) -> None:
    for name in RESOURCE_DIRS:
        src = core_skill / name
        if not src.exists():
            continue
        dst = target / name
        if link_mode == "symlink":
            _relative_symlink(src, dst)
        elif name == "scripts":
            _write_dispatch_shim(target, skill)
        else:
            shutil.copytree(src, dst)


def write_native_public_skills(skills_root: Path, link_mode: str) -> list[Path]:
    written: list[Path] = []
    for skill in load_public_skills():
        target = skills_root / f"aegis-alpha-{skill}"
        core_skill = skills_root / CORE_DIR_NAME / skill
        if not core_skill.exists():
            raise SystemExit(f"shared core skill is missing: {core_skill}")
        target.mkdir(parents=True, exist_ok=False)
        (target / "SKILL.md").write_text(_native_skill_body(skill), encoding="utf-8")
        _materialize_resources(target, core_skill, skill, link_mode)
        written.append(target)
    return written


def install_native_skillset(adapter_dir: Path, skills_root: Path, force: bool, link_mode: str = "symlink") -> list[Path]:
    skills_root = skills_root.expanduser()
    skills_root.mkdir(parents=True, exist_ok=True)
    public_targets = [skills_root / f"aegis-alpha-{skill}" for skill in load_public_skills()]
    targets = [skills_root / CORE_DIR_NAME, skills_root / "aegis-alpha", *public_targets]
    ensure_targets_available(targets, force)
    installed = [copy_shared_core(skills_root), install_aggregate_skill(adapter_dir, skills_root)]
    installed.extend(write_native_public_skills(skills_root, link_mode))
    return installed


def install_wrapper_skillset(adapter_dir: Path, skills_root: Path, force: bool, link_mode: str = "symlink") -> list[Path]:
    return install_native_skillset(adapter_dir, skills_root, force, link_mode)


def env_home(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else fallback


def print_success(agent: str, target: Path) -> None:
    print(f"Installed Aegis Alpha for {agent}: {target}")
