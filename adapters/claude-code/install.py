#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR.parent / "common"))

from install_lib import install_wrapper_skillset, parse_args, print_success  # noqa: E402


def default_target() -> Path:
    explicit = os.environ.get("CLAUDE_CODE_SKILLS_HOME")
    if explicit:
        return Path(explicit).expanduser()
    return Path.cwd() / ".claude" / "skills"


def main() -> int:
    args = parse_args(default_target(), "Install Aegis Alpha Claude Code skill wrappers.")
    install_wrapper_skillset(ADAPTER_DIR, args.target.expanduser(), args.force)
    print_success("Claude Code", args.target.expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
