from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PrewarmUnavailableError(RuntimeError):
    pass


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_latest_prewarm() -> tuple[dict[str, Any], Path]:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        raise PrewarmUnavailableError(f"prewarm directory not found: {prewarm_dir}")
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise PrewarmUnavailableError(f"prewarm artifact not found under: {prewarm_dir}")
    latest = files[0]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PrewarmUnavailableError(f"prewarm artifact is not valid JSON: {latest}") from exc
    if not isinstance(payload, dict):
        raise PrewarmUnavailableError(f"prewarm artifact must decode to an object: {latest}")
    return payload, latest


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "market-data",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "artifact_derived",
            "as_of": as_of,
            "policy": "market data is read only from the latest prewarm artifact; missing artifact or missing field fails closed",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "data_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Required market data artifact or field is missing; do not infer market data from an empty result.",
        "missing_critical_inputs": errors,
    }
    return output


def _wrap(command: str, payload: dict[str, Any], result: object, artifact: Path) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["source"] = [str(artifact)]
    output["sources"] = [str(artifact)]
    output["artifacts"] = [str(artifact)]
    output["result"] = result
    return output


def _market_data_surface(prewarm: dict) -> dict:
    return prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else {}


def _build_result(command: str, prewarm: dict) -> object:
    market_data = _market_data_surface(prewarm)

    if command == "snapshot-full":
        result = market_data.get("hhxg_snapshot") or prewarm.get("hhxg_snapshot")
        if not result:
            raise PrewarmUnavailableError("hhxg_snapshot_missing")
        return result
    if command == "margin-full":
        result = market_data.get("hhxg_margin") or prewarm.get("hhxg_margin")
        if not result:
            raise PrewarmUnavailableError("hhxg_margin_missing")
        return result
    if command == "calendar-week":
        result = market_data.get("hhxg_calendar") or prewarm.get("hhxg_calendar")
        if not result:
            raise PrewarmUnavailableError("hhxg_calendar_missing")
        return result
    if command == "macro-pmi":
        result = market_data.get("akshare_macro_pmi") or market_data.get("akshare_macro_pmi_yearly") or prewarm.get("akshare_macro_pmi") or prewarm.get("akshare_macro_pmi_yearly")
        if not result:
            raise PrewarmUnavailableError("macro_pmi_missing")
        return result
    if command == "macro-cpi":
        result = market_data.get("akshare_macro_cpi") or market_data.get("akshare_macro_cpi_monthly") or prewarm.get("akshare_macro_cpi") or prewarm.get("akshare_macro_cpi_monthly")
        if not result:
            raise PrewarmUnavailableError("macro_cpi_missing")
        return result
    if command == "macro-ppi":
        result = market_data.get("akshare_macro_ppi") or market_data.get("akshare_macro_ppi_yearly") or prewarm.get("akshare_macro_ppi") or prewarm.get("akshare_macro_ppi_yearly")
        if not result:
            raise PrewarmUnavailableError("macro_ppi_missing")
        return result
    if command == "index-daily":
        result = (
            market_data.get("baostock_index_daily")
            or prewarm.get("baostock_index_daily")
            or market_data.get("tushare_index_daily")
            or prewarm.get("tushare_index_daily")
        )
        if not result:
            raise PrewarmUnavailableError("index_daily_missing")
        return result
    raise ValueError(f"unknown command: {command}")


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

    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
    except ValueError as exc:
        print(json.dumps(_fail(args.command, {}, [str(exc)]), ensure_ascii=False))
        return 0

    try:
        prewarm, artifact = _load_latest_prewarm()
        result = _build_result(args.command, prewarm)
        output = _wrap(args.command, payload, result, artifact)
    except PrewarmUnavailableError as exc:
        output = _fail(args.command, payload, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
