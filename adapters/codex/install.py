#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR.parent / "common"))

from install_lib import env_home, install_wrapper_skillset, parse_args, print_success  # noqa: E402


def main() -> int:
    home = env_home("CODEX_HOME", Path.home() / ".codex")
    args = parse_args(home / "skills", "Install Aegis Alpha Codex wrapper skillset.")
    install_wrapper_skillset(ADAPTER_DIR, args.target.expanduser(), args.force)
    print_success("Codex", args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
