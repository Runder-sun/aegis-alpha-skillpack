#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR.parent / "common"))

from install_lib import copy_wrapper_package, parse_args, print_success  # noqa: E402


def default_target() -> Path:
    explicit = os.environ.get("CLAUDE_CODE_SKILLS_HOME")
    if explicit:
        return Path(explicit).expanduser() / "aegis-alpha"
    return Path.cwd() / ".claude" / "skills" / "aegis-alpha"


def main() -> int:
    args = parse_args(default_target(), "Install Aegis Alpha Claude Code project wrapper.")
    copy_wrapper_package(ADAPTER_DIR, args.target.expanduser(), args.force, ["CLAUDE.md"])
    print_success("Claude Code", args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
