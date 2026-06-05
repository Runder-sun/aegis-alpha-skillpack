from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = "portfolio-management"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE", "")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _memory_dir() -> Path:
    return _workspace_dir() / "memory"


def _positions_path() -> Path:
    return _memory_dir() / "positions.json"


def _trades_path() -> Path:
    return _memory_dir() / "trades.jsonl"


def _load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "portfolio_state_missing"
    except json.JSONDecodeError:
        return None, "portfolio_state_invalid_json"
    except OSError as exc:
        return None, f"portfolio_state_read_failed: {exc}"


def _load_positions() -> tuple[list[dict[str, Any]] | None, list[str]]:
    payload, error = _read_json(_positions_path())
    if error:
        return None, [error]
    if isinstance(payload, list):
        positions = payload
    elif isinstance(payload, dict) and isinstance(payload.get("positions"), list):
        positions = payload["positions"]
    else:
        return None, ["portfolio_state_invalid_shape"]
    clean = [item for item in positions if isinstance(item, dict)]
    return clean, []


def _save_positions(positions: list[dict[str, Any]]) -> Path:
    path = _positions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": _now(),
        "positions": positions,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _append_trade(trade: dict[str, Any]) -> Path:
    path = _trades_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8") if not path.exists() else None
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(trade, ensure_ascii=False) + "\n")
    return path


def _to_float(payload: dict[str, Any], *keys: str, required: bool = False) -> float | None:
    for key in keys:
        if payload.get(key) is None:
            continue
        try:
            return float(payload[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key}_must_be_number")
    if required:
        raise ValueError(f"{keys[0]}_required")
    return None


def _code(payload: dict[str, Any]) -> str:
    code = str(payload.get("code") or payload.get("symbol") or "").strip()
    if not code:
        raise ValueError("code_required")
    return code


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "package": PACKAGE,
        "command": command,
        "payload": payload,
        "ok": True,
        "decision_allowed": False,
        "max_action_level": "analysis_only",
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "result": {},
    }


def _fail(
    command: str,
    payload: dict[str, Any],
    errors: list[str],
    warnings: list[str] | None = None,
    portfolio_state_known: bool = False,
) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["errors"] = errors
    output["warnings"] = warnings or []
    output["result"] = {
        "portfolio_state_known": portfolio_state_known,
        "positions": None,
        "note": (
            "Portfolio state is unavailable; do not infer an empty portfolio."
            if not portfolio_state_known
            else "Portfolio state is known, but the requested operation is not allowed."
        ),
    }
    return output


def _find_position(positions: list[dict[str, Any]], code: str) -> tuple[int | None, dict[str, Any] | None]:
    for idx, position in enumerate(positions):
        if str(position.get("code") or position.get("symbol") or "").strip() == code:
            return idx, position
    return None, None


def _portfolio_add(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    code = _code(payload)
    quantity = _to_float(payload, "quantity", "shares", required=True)
    price = _to_float(payload, "price", "buy_price", "cost_basis")
    if quantity is None or quantity <= 0:
        raise ValueError("quantity_must_be_positive")

    positions, errors = _load_positions()
    if positions is None:
        positions = []
        errors = []
    idx, existing = _find_position(positions, code)
    merge = bool(payload.get("merge", True))
    now = _now()
    if existing and not merge:
        return _fail(command, payload, ["position_exists"], ["set merge=true to combine quantities"])

    if existing:
        old_qty = float(existing.get("quantity") or 0)
        old_cost = existing.get("cost_basis")
        old_cost_float = float(old_cost) if old_cost is not None else None
        total_qty = old_qty + quantity
        if total_qty <= 0:
            raise ValueError("merged_quantity_invalid")
        if price is not None and old_cost_float is not None:
            cost_basis = ((old_qty * old_cost_float) + (quantity * price)) / total_qty
        else:
            cost_basis = price if price is not None else old_cost_float
        existing.update({
            "code": code,
            "name": payload.get("name") or existing.get("name") or "",
            "quantity": total_qty,
            "cost_basis": cost_basis,
            "updated_at": now,
            "notes": payload.get("notes", existing.get("notes", "")),
        })
        position = existing
    else:
        position = {
            "code": code,
            "name": payload.get("name") or "",
            "quantity": quantity,
            "cost_basis": price,
            "opened_at": payload.get("date") or now,
            "updated_at": now,
            "notes": payload.get("notes", ""),
        }
        positions.append(position)

    pos_path = _save_positions(positions)
    trade_path = _append_trade({
        "timestamp": now,
        "side": "add",
        "code": code,
        "name": position.get("name", ""),
        "quantity": quantity,
        "price": price,
        "source_command": command,
    })
    output = _base_output(command, payload)
    output["artifacts"] = [str(pos_path), str(trade_path)]
    output["result"] = {
        "portfolio_state_known": True,
        "position": position,
        "position_count": len(positions),
    }
    return output


def _portfolio_remove(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    code = _code(payload)
    positions, errors = _load_positions()
    if positions is None:
        return _fail(command, payload, errors)
    idx, position = _find_position(positions, code)
    if idx is None or position is None:
        return _fail(
            command,
            payload,
            ["position_not_found"],
            ["portfolio state was loaded but target code was absent"],
            portfolio_state_known=True,
        )
    removed = positions.pop(idx)
    now = _now()
    pos_path = _save_positions(positions)
    trade_path = _append_trade({
        "timestamp": now,
        "side": "remove",
        "code": code,
        "quantity": removed.get("quantity"),
        "price": payload.get("price"),
        "reason": payload.get("reason", ""),
        "source_command": command,
    })
    output = _base_output(command, payload)
    output["artifacts"] = [str(pos_path), str(trade_path)]
    output["result"] = {
        "portfolio_state_known": True,
        "removed": removed,
        "position_count": len(positions),
    }
    return output


def _record_trade(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    code = _code(payload)
    side = str(payload.get("side") or "").lower().strip()
    if side not in {"buy", "sell"}:
        raise ValueError("side_must_be_buy_or_sell")
    quantity = _to_float(payload, "quantity", "shares", required=True)
    price = _to_float(payload, "price", required=True)
    if quantity is None or quantity <= 0:
        raise ValueError("quantity_must_be_positive")
    if price is None or price < 0:
        raise ValueError("price_must_be_non_negative")

    positions, errors = _load_positions()
    if positions is None:
        positions = []
        if side == "sell":
            return _fail(command, payload, errors)
    idx, position = _find_position(positions, code)
    now = _now()

    if side == "buy":
        add_payload = dict(payload)
        add_payload.setdefault("buy_price", price)
        return _portfolio_add(command, add_payload)

    if position is None or idx is None:
        return _fail(
            command,
            payload,
            ["position_not_found"],
            ["cannot record sell without known position"],
            portfolio_state_known=True,
        )
    old_qty = float(position.get("quantity") or 0)
    if quantity > old_qty and not payload.get("allow_negative"):
        return _fail(
            command,
            payload,
            ["sell_quantity_exceeds_position"],
            ["set allow_negative=true only for explicit short/borrow workflows"],
            portfolio_state_known=True,
        )
    new_qty = old_qty - quantity
    if new_qty <= 0:
        positions.pop(idx)
    else:
        position["quantity"] = new_qty
        position["updated_at"] = now
    pos_path = _save_positions(positions)
    trade_path = _append_trade({
        "timestamp": now,
        "side": side,
        "code": code,
        "quantity": quantity,
        "price": price,
        "source_command": command,
    })
    output = _base_output(command, payload)
    output["artifacts"] = [str(pos_path), str(trade_path)]
    output["result"] = {
        "portfolio_state_known": True,
        "position_count": len(positions),
        "remaining_quantity": max(new_qty, 0),
    }
    return output


def _portfolio_view(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    positions, errors = _load_positions()
    if positions is None:
        return _fail(command, payload, errors)
    output = _base_output(command, payload)
    output["sources"] = [str(_positions_path())]
    output["result"] = {
        "portfolio_state_known": True,
        "positions": positions,
        "position_count": len(positions),
    }
    return output


def _portfolio_report(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    positions, errors = _load_positions()
    if positions is None:
        return _fail(command, payload, errors)

    rows: list[dict[str, Any]] = []
    total_cost = 0.0
    market_value_known = True
    total_market_value = 0.0
    warnings: list[str] = []
    for position in positions:
        quantity = float(position.get("quantity") or 0)
        cost_basis = position.get("cost_basis")
        current_price = position.get("current_price")
        cost_value = quantity * float(cost_basis) if cost_basis is not None else None
        market_value = quantity * float(current_price) if current_price is not None else None
        if cost_value is not None:
            total_cost += cost_value
        if market_value is not None:
            total_market_value += market_value
        else:
            market_value_known = False
        rows.append({
            "code": position.get("code"),
            "name": position.get("name", ""),
            "quantity": quantity,
            "cost_basis": cost_basis,
            "current_price": current_price,
            "cost_value": cost_value,
            "market_value": market_value,
        })
    if not market_value_known:
        warnings.append("market_value_incomplete_without_current_price")
    output = _base_output(command, payload)
    output["sources"] = [str(_positions_path())]
    output["warnings"] = warnings
    output["result"] = {
        "portfolio_state_known": True,
        "position_count": len(positions),
        "positions": rows,
        "total_cost": total_cost,
        "total_market_value": total_market_value if market_value_known else None,
    }
    return output


def _portfolio_advice(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = _portfolio_report(command, payload)
    if not report["ok"]:
        return report
    positions = report["result"].get("positions") or []
    warnings = list(report.get("warnings") or [])
    warnings.append("requires_fresh_market_data_for_trade_advice")
    warnings.append("requires_macro_regime_and_risk_budget_for_position_advice")
    output = _base_output(command, payload)
    output["sources"] = report.get("sources", [])
    output["warnings"] = warnings
    output["result"] = {
        "portfolio_state_known": True,
        "position_count": len(positions),
        "advice": [
            "Review concentration by single-name and theme exposure.",
            "Do not size new trades until fresh market data and macro regime are available.",
            "Use portfolio-risk-check after market data is refreshed.",
        ],
        "missing_critical_inputs": [
            "fresh_market_prices",
            "macro_regime",
            "risk_budget",
        ],
    }
    return output


def _run(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command == "portfolio-add":
        return _portfolio_add(command, payload)
    if command == "portfolio-remove":
        return _portfolio_remove(command, payload)
    if command == "portfolio-view":
        return _portfolio_view(command, payload)
    if command == "portfolio-report":
        return _portfolio_report(command, payload)
    if command == "portfolio-advice":
        return _portfolio_advice(command, payload)
    if command == "record-trade":
        return _record_trade(command, payload)
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
