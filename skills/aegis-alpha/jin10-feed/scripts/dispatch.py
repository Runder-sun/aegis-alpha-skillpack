from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any
import signal


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _pid_path() -> Path:
    return _workspace_dir() / "memory" / "jin10" / "daemon.pid"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _run_node(args: list[str]) -> dict:
    script = Path(__file__).resolve().parent / "jin10_feed.mjs"
    cmd = ["node", str(script), *args]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    raw = (proc.stdout or "").strip()
    try:
        payload = json.loads(raw) if raw else {}
        return {"ok": proc.returncode == 0, "data": payload, "raw": raw}
    except Exception:
        return {"ok": proc.returncode == 0, "raw": raw}


def _daemon_start() -> dict:
    pid_path = _pid_path()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = pid_path.parent / "daemon.log"
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            if _is_running(pid):
                return {"status": "already_running", "pid": pid}
        except Exception:
            pass
        try:
            pid_path.unlink()
        except Exception:
            pass

    script = Path(__file__).resolve().parent / "jin10_feed.mjs"
    cmd = ["node", str(script), "--daemon"]
    log_fh = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    return {"status": "started", "pid": proc.pid, "log": str(log_path)}


def _daemon_stop() -> dict:
    pid_path = _pid_path()
    if not pid_path.exists():
        return {"status": "not_running"}
    try:
        pid = int(pid_path.read_text().strip())
    except Exception:
        pid_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        return {"status": "pid_invalid"}

    if not _is_running(pid):
        pid_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        return {"status": "not_running"}

    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as exc:
        return {"status": "kill_failed", "error": str(exc), "pid": pid}

    try:
        pid_path.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass
    return {"status": "stopped", "pid": pid}


def _daemon_status() -> dict:
    pid_path = _pid_path()
    if not pid_path.exists():
        return {"status": "not_running"}
    try:
        pid = int(pid_path.read_text().strip())
    except Exception:
        return {"status": "pid_invalid"}
    return {"status": "running" if _is_running(pid) else "not_running", "pid": pid}


def _build_result(command: str, payload: dict) -> dict:
    if command == "jin10-snapshot":
        limit = payload.get("limit", 50)
        res = _run_node([f"--once", f"--limit={int(limit)}"])
        return res
    if command == "jin10-daemon-start":
        return _daemon_start()
    if command == "jin10-daemon-stop":
        return _daemon_stop()
    if command == "jin10-daemon-status":
        return _daemon_status()
    return {"note": "command not implemented"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = _load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", [])}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    payload = json.loads(args.payload or "{}")
    result = _build_result(args.command, payload)

    print(json.dumps({
        "package": "jin10-feed",
        "command": args.command,
        "payload": payload,
        "result": result,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
