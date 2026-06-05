from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SKILLPACK = REPO_ROOT / "skills" / "aegis-alpha"


def parse_args(default_target: Path, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--target", type=Path, default=default_target)
    parser.add_argument("--force", action="store_true", help="Replace an existing target directory.")
    return parser.parse_args()


def replace_or_fail(target: Path, force: bool) -> None:
    if not target.exists():
        return
    if not force:
        raise SystemExit(f"target already exists: {target} (use --force to replace it)")
    if not target.is_dir():
        raise SystemExit(f"target exists and is not a directory: {target}")
    shutil.rmtree(target)


def copy_canonical_package(target: Path, force: bool) -> None:
    replace_or_fail(target, force)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CANONICAL_SKILLPACK, target)


def copy_wrapper_package(adapter_dir: Path, target: Path, force: bool, wrapper_files: list[str]) -> None:
    replace_or_fail(target, force)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CANONICAL_SKILLPACK, target / "skillpack")
    for name in wrapper_files:
        src = adapter_dir / name
        if src.exists():
            dst = target / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def env_home(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else fallback


def print_success(agent: str, target: Path) -> None:
    print(f"Installed Aegis Alpha for {agent}: {target}")
