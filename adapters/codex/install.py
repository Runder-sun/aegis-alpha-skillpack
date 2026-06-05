#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR.parent / "common"))

from install_lib import copy_wrapper_package, env_home, parse_args, print_success  # noqa: E402


def main() -> int:
    home = env_home("CODEX_HOME", Path.home() / ".codex")
    args = parse_args(home / "skills" / "aegis-alpha", "Install Aegis Alpha Codex wrapper skill.")
    copy_wrapper_package(ADAPTER_DIR, args.target.expanduser(), args.force, ["SKILL.md"])
    print_success("Codex", args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
