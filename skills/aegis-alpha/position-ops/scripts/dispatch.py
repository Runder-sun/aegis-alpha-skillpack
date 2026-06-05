from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any


PACKAGE = "position-ops"


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE", "")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _positions_path() -> Path:
    return _workspace_dir() / "memory" / "positions.json"


def _legacy_db_path() -> Path | None:
    raw = os.environ.get("AI_INVEST_LEGACY_MEMORY_DB", "")
    return Path(raw).expanduser() if raw else None


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "package": PACKAGE,
        "command": command,
        "payload": payload,
        "ok": True,
        "decision_allowed": False,
        "max_action_level": "analysis_only",
        "sources": [],
        "warnings": [],
        "errors": [],
        "result": {},
    }


def _fail(
    command: str,
    payload: dict[str, Any],
    errors: list[str],
    warnings: list[str] | None = None,
    portfolio_state_known: bool | None = False,
    note: str | None = None,
) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["warnings"] = warnings or []
    output["errors"] = errors
    output["result"] = {
        "portfolio_state_known": portfolio_state_known,
        "positions": None,
        "note": note or "Position state is unavailable; do not infer an empty portfolio.",
    }
    return output


def _read_workspace_positions() -> tuple[list[dict[str, Any]] | None, list[str], list[str]]:
    path = _positions_path()
    if not path.exists():
        return None, ["positions_state_missing"], []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, ["positions_state_invalid_json"], [str(path)]
    except OSError as exc:
        return None, [f"positions_state_read_failed: {exc}"], [str(path)]
    if isinstance(payload, list):
        positions = payload
    elif isinstance(payload, dict) and isinstance(payload.get("positions"), list):
        positions = payload["positions"]
    else:
        return None, ["positions_state_invalid_shape"], [str(path)]
    return [p for p in positions if isinstance(p, dict)], [], [str(path)]


def _read_legacy_positions() -> tuple[list[dict[str, Any]] | None, list[str], list[str]]:
    db_path = _legacy_db_path()
    if db_path is None:
        return None, [], []
    if not db_path.exists():
        return None, ["legacy_memory_db_missing"], [str(db_path)]
    con = None
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT code, name, buy_price, quantity, buy_date, current_price, pnl_pct, notes FROM portfolio")
        rows = cur.fetchall()
    except Exception as exc:
        return None, [f"legacy_memory_db_read_failed: {exc}"], [str(db_path)]
    finally:
        if con is not None:
            con.close()

    positions: list[dict[str, Any]] = []
    for row in rows:
        code, name, buy_price, quantity, buy_date, current_price, pnl_pct, notes = row
        if not code:
            continue
        positions.append({
            "code": code,
            "name": name or "",
            "cost_basis": buy_price,
            "quantity": quantity,
            "opened_at": buy_date or "",
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "notes": notes or "",
        })
    return positions, [], [str(db_path)]


def _load_positions(allow_legacy: bool = True) -> tuple[list[dict[str, Any]] | None, list[str], list[str], list[str]]:
    positions, errors, sources = _read_workspace_positions()
    warnings: list[str] = []
    if positions is not None:
        return positions, errors, warnings, sources
    if allow_legacy:
        legacy_positions, legacy_errors, legacy_sources = _read_legacy_positions()
        if legacy_positions is not None:
            warnings.append("using_legacy_memory_db_from_env")
            return legacy_positions, [], warnings, legacy_sources
        errors.extend(legacy_errors)
        sources.extend(legacy_sources)
    return None, errors, warnings, sources


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position_value(position: dict[str, Any]) -> tuple[float | None, str]:
    quantity = _float(position.get("quantity"))
    if quantity is None:
        return None, "missing_quantity"
    price = _float(position.get("current_price"))
    if price is not None:
        return quantity * price, "market_value"
    cost = _float(position.get("cost_basis") or position.get("buy_price"))
    if cost is not None:
        return quantity * cost, "cost_value"
    return None, "missing_price"


def _position_management(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    positions, errors, warnings, sources = _load_positions()
    if positions is None:
        return _fail(command, payload, errors, warnings)
    output = _base_output(command, payload)
    output["sources"] = sources
    output["warnings"] = warnings
    output["result"] = {
        "portfolio_state_known": True,
        "positions": positions,
        "count": len(positions),
    }
    return output


def _portfolio_risk_check(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    positions, errors, warnings, sources = _load_positions()
    if positions is None:
        return _fail(command, payload, errors, warnings)

    max_single = float(payload.get("max_single_position_pct", 0.2))
    rows: list[dict[str, Any]] = []
    total_value = 0.0
    value_mode_counts: dict[str, int] = {}
    for position in positions:
        value, value_mode = _position_value(position)
        value_mode_counts[value_mode] = value_mode_counts.get(value_mode, 0) + 1
        rows.append({
            "code": position.get("code"),
            "name": position.get("name", ""),
            "value": value,
            "value_mode": value_mode,
        })
        if value is not None:
            total_value += value

    if total_value <= 0:
        return _fail(command, payload, ["position_values_unavailable"], warnings)

    risk_flags: list[dict[str, Any]] = []
    for row in rows:
        value = row.get("value")
        if value is None:
            risk_flags.append({"code": row.get("code"), "risk": "missing_position_value"})
            continue
        weight = value / total_value
        row["weight"] = weight
        if weight > max_single:
            risk_flags.append({
                "code": row.get("code"),
                "risk": "single_position_concentration",
                "weight": round(weight, 4),
                "limit": max_single,
            })

    if value_mode_counts.get("cost_value"):
        warnings.append("risk_check_uses_cost_value_when_current_price_missing")
    if value_mode_counts.get("missing_price"):
        warnings.append("some_positions_missing_value")

    output = _base_output(command, payload)
    output["sources"] = sources
    output["warnings"] = warnings
    output["result"] = {
        "portfolio_state_known": True,
        "position_count": len(positions),
        "total_value_estimate": total_value,
        "max_single_position_pct": max_single,
        "positions": rows,
        "risk_flags": risk_flags,
        "risk_flag_count": len(risk_flags),
    }
    return output


def _position_sizing_advisor(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    required = ["portfolio_value", "risk_budget_pct", "stop_loss_pct"]
    missing = [key for key in required if _float(payload.get(key)) is None]
    if missing:
        return _fail(
            command,
            payload,
            [f"missing_required_input:{key}" for key in missing],
            portfolio_state_known=None,
            note="Sizing inputs are incomplete; do not use a derived position size.",
        )

    portfolio_value = float(payload["portfolio_value"])
    risk_budget_pct = float(payload["risk_budget_pct"])
    stop_loss_pct = float(payload["stop_loss_pct"])
    max_single_pct = float(payload.get("max_single_position_pct", 0.2))
    current_exposure = _float(payload.get("current_exposure")) or 0.0
    if portfolio_value <= 0 or risk_budget_pct <= 0 or stop_loss_pct <= 0:
        return _fail(
            command,
            payload,
            ["portfolio_value_risk_budget_and_stop_loss_must_be_positive"],
            portfolio_state_known=None,
            note="Sizing inputs are invalid; do not use a derived position size.",
        )

    risk_budget_value = portfolio_value * risk_budget_pct
    stop_loss_size_cap = risk_budget_value / stop_loss_pct
    single_position_cap = portfolio_value * max_single_pct
    remaining_single_cap = max(single_position_cap - current_exposure, 0.0)
    suggested_position_value = min(stop_loss_size_cap, remaining_single_cap)

    output = _base_output(command, payload)
    output["max_action_level"] = "paper_plan_only"
    output["warnings"] = ["sizing_requires_fresh_price_and_human_review_before_execution"]
    output["result"] = {
        "portfolio_state_known": None,
        "portfolio_value": portfolio_value,
        "risk_budget_pct": risk_budget_pct,
        "stop_loss_pct": stop_loss_pct,
        "risk_budget_value": risk_budget_value,
        "stop_loss_size_cap": stop_loss_size_cap,
        "single_position_cap": single_position_cap,
        "current_exposure": current_exposure,
        "suggested_position_value": suggested_position_value,
        "decision_allowed": False,
    }
    return output


def _run(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command == "position-management-v2":
        return _position_management(command, payload)
    if command == "portfolio-risk-check":
        return _portfolio_risk_check(command, payload)
    if command == "position-sizing-advisor":
        return _position_sizing_advisor(command, payload)
    raise ValueError(f"unknown_command: {command}")


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
        output = _run(args.command, payload)
    except ValueError as exc:
        output = _fail(args.command, {}, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
