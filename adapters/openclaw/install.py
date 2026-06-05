#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR.parent / "common"))

from install_lib import copy_canonical_package, env_home, parse_args, print_success  # noqa: E402


def main() -> int:
    home = env_home("OPENCLAW_HOME", Path.home() / ".openclaw")
    args = parse_args(home / "skills" / "aegis-alpha", "Install Aegis Alpha OpenClaw skill package.")
    copy_canonical_package(args.target.expanduser(), args.force)
    print_success("OpenClaw", args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
