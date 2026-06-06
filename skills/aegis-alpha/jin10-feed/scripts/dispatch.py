from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any
import signal
from datetime import datetime, timezone


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _pid_path() -> Path:
    return _workspace_dir() / "memory" / "jin10" / "daemon.pid"


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    memory_dir = _workspace_dir() / "memory" / "jin10"
    return {
        "package": "jin10-feed",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "Jin10 feed data is collected at command runtime or daemon runtime",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "data_only",
        "source": ["https://www.jin10.com/"],
        "sources": ["https://www.jin10.com/"],
        "artifacts": [
            str(memory_dir / "snapshot.json"),
            str(memory_dir / "news.jsonl"),
            str(memory_dir / "daemon.pid"),
        ],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], raw: str = "") -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Jin10 feed data is unavailable; do not infer market news from an empty result.",
        "raw": raw,
    }
    return output


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


def _build_result(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    output = _base_output(command, payload)
    if command == "jin10-snapshot":
        limit = payload.get("limit", 50)
        res = _run_node([f"--once", f"--limit={int(limit)}"])
        if not res.get("ok"):
            return _fail(command, payload, ["jin10_snapshot_failed"], str(res.get("raw") or ""))
        data = res.get("data") if isinstance(res.get("data"), dict) else {}
        output["result"] = data
        return output
    if command == "jin10-daemon-start":
        output["result"] = _daemon_start()
        return output
    if command == "jin10-daemon-stop":
        output["result"] = _daemon_stop()
        return output
    if command == "jin10-daemon-status":
        output["result"] = _daemon_status()
        return output
    return _fail(command, payload, [f"unimplemented_command:{command}"])


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
    output = _build_result(args.command, payload)
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
