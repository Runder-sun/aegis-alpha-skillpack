from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _workspace_dir() -> Path:
    return Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))


def load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "quant-validation",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "backtest freshness is inherited from the supplied price/return series",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "research_validation_only",
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
    output["errors"] = errors
    output["warnings"] = warnings or []
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Quant validation cannot prove the strategy without explicit, sufficient historical data.",
        "missing_critical_inputs": errors,
    }
    return output


def _wrap(command: str, payload: dict[str, Any], result: dict[str, Any], sources: list[str] | None = None, artifacts: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["result"] = result
    output["sources"] = sources or []
    output["source"] = sources or []
    output["artifacts"] = artifacts or []
    output["warnings"] = warnings or []
    gaps = result.get("critical_gaps")
    if isinstance(gaps, list) and gaps:
        output["missing_critical_inputs"] = gaps
        output["warnings"] = sorted(set(output["warnings"] + ["critical_data_gaps_present"]))
        output["freshness"]["status"] = "partial"
    return output


def _repo_root() -> Path | None:
    env_repo = os.environ.get("AEGIS_ALPHA_REPO")
    if env_repo:
        candidate = Path(env_repo).expanduser()
        if (candidate / "scripts" / "backtest_monthly.py").exists():
            return candidate
    try:
        import ai_invest_openclaw  # type: ignore

        module_path = Path(ai_invest_openclaw.__file__).resolve()
        for parent in module_path.parents:
            if (parent / "scripts" / "backtest_monthly.py").exists():
                return parent
    except Exception:
        pass
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "backtest_monthly.py").exists():
            return parent
    candidate = Path(__file__).resolve().parents[5] / "aegis-alpha"
    if (candidate / "scripts" / "backtest_monthly.py").exists():
        return candidate
    return None


def _resolve_workspace_path(raw_path: Any) -> Path:
    workspace = _workspace_dir().resolve()
    candidate = Path(str(raw_path)).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("series_path_outside_workspace") from exc
    return resolved


def _read_json_path(raw_path: Any) -> Any:
    path = _resolve_workspace_path(raw_path)
    if not path.exists():
        raise ValueError("series_path_missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("series_path_invalid_json") from exc


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _records_from_payload(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    data: Any = None
    source = "payload"
    if payload.get("series_path"):
        data = _read_json_path(payload.get("series_path"))
        source = str(payload.get("series_path"))
    else:
        for key in ("price_series", "prices", "equity_curve", "returns", "data", "records"):
            if key in payload:
                data = payload.get(key)
                source = f"payload.{key}"
                break
    if isinstance(data, dict):
        for key in ("price_series", "prices", "equity_curve", "returns", "data", "records"):
            if isinstance(data.get(key), list):
                data = data.get(key)
                source = f"{source}.{key}"
                break
    if not isinstance(data, list):
        raise ValueError("historical_series_required")
    records: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if isinstance(item, dict):
            records.append(dict(item))
        else:
            records.append({"index": index, "value": item})
    return records, source


def _extract_prices(payload: dict[str, Any]) -> tuple[list[float], list[str], str]:
    records, source = _records_from_payload(payload)
    prices: list[float] = []
    dates: list[str] = []
    is_returns = bool(payload.get("series_type") == "returns" or payload.get("returns") is not None)
    if is_returns:
        equity = 1.0
        prices.append(equity)
        dates.append("0")
        for index, row in enumerate(records):
            value = _number(row.get("return") if isinstance(row, dict) else None)
            if value is None:
                value = _number(row.get("value"))
            if value is None:
                raise ValueError("return_series_contains_non_numeric_value")
            equity *= 1.0 + value
            prices.append(equity)
            dates.append(str(row.get("date") or row.get("datetime") or index + 1))
        return prices, dates, source

    for index, row in enumerate(records):
        value = None
        for key in ("close", "price", "value", "equity", "nav"):
            value = _number(row.get(key))
            if value is not None:
                break
        if value is None:
            raise ValueError("price_series_contains_non_numeric_value")
        if value <= 0:
            raise ValueError("price_series_contains_non_positive_value")
        prices.append(value)
        dates.append(str(row.get("date") or row.get("datetime") or index))
    if len(prices) < 3:
        raise ValueError("historical_series_too_short")
    return prices, dates, source


def _period_returns(prices: list[float]) -> list[float]:
    returns: list[float] = []
    for prev, current in zip(prices, prices[1:]):
        if prev <= 0:
            raise ValueError("price_series_contains_non_positive_value")
        returns.append(current / prev - 1.0)
    return returns


def _moving_average(values: list[float], end_index: int, window: int) -> float | None:
    if window <= 0 or end_index + 1 < window:
        return None
    segment = values[end_index + 1 - window : end_index + 1]
    return sum(segment) / len(segment)


def _positions_for_strategy(prices: list[float], payload: dict[str, Any], strategy: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    returns = _period_returns(prices)
    allow_short = bool(payload.get("allow_short") or strategy.get("allow_short"))

    signals = strategy.get("signals") or payload.get("signals")
    if isinstance(signals, list):
        if len(signals) not in {len(prices), len(returns)}:
            raise ValueError("signals_length_mismatch")
        raw = signals[:-1] if len(signals) == len(prices) else signals
        positions = []
        for value in raw:
            number = _number(value)
            if number is None:
                raise ValueError("signals_contain_non_numeric_value")
            if not allow_short:
                number = max(0.0, min(1.0, number))
            else:
                number = max(-1.0, min(1.0, number))
            positions.append(number)
        return positions, {"type": "explicit_signals"}

    strategy_type = str(strategy.get("type") or payload.get("strategy_type") or "buy_and_hold")
    if strategy_type == "buy_and_hold":
        return [1.0 for _ in returns], {"type": "buy_and_hold"}
    if strategy_type == "cash":
        return [0.0 for _ in returns], {"type": "cash"}
    if strategy_type == "ma_cross":
        short_window = int(strategy.get("short_window") or payload.get("short_window") or 5)
        long_window = int(strategy.get("long_window") or payload.get("long_window") or 20)
        if short_window <= 0 or long_window <= 0 or short_window >= long_window:
            raise ValueError("invalid_ma_windows")
        positions = []
        for return_index in range(len(returns)):
            price_index = return_index
            short_ma = _moving_average(prices, price_index, short_window)
            long_ma = _moving_average(prices, price_index, long_window)
            if short_ma is None or long_ma is None:
                positions.append(0.0)
            else:
                positions.append(1.0 if short_ma > long_ma else 0.0)
        return positions, {"type": "ma_cross", "short_window": short_window, "long_window": long_window}
    if strategy_type == "threshold":
        lookback = int(strategy.get("lookback") or payload.get("lookback") or 5)
        threshold = float(strategy.get("threshold") or payload.get("threshold") or 0)
        if lookback <= 0:
            raise ValueError("invalid_threshold_lookback")
        positions = []
        for return_index in range(len(returns)):
            if return_index < lookback:
                positions.append(0.0)
                continue
            momentum = prices[return_index] / prices[return_index - lookback] - 1.0
            positions.append(1.0 if momentum > threshold else 0.0)
        return positions, {"type": "threshold", "lookback": lookback, "threshold": threshold}
    raise ValueError("unsupported_strategy_type")


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 1.0
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(0.0, variance))


def _metrics(period_returns: list[float], periods_per_year: int = 252) -> dict[str, Any]:
    equity = [1.0]
    for value in period_returns:
        equity.append(equity[-1] * (1.0 + value))
    total_return = equity[-1] - 1.0
    periods = len(period_returns)
    annualized = (equity[-1] ** (periods_per_year / periods) - 1.0) if periods and equity[-1] > 0 else None
    volatility = _stdev(period_returns) * math.sqrt(periods_per_year) if periods else None
    mean = sum(period_returns) / periods if periods else 0.0
    std = _stdev(period_returns)
    sharpe = (mean / std * math.sqrt(periods_per_year)) if std > 0 else None
    wins = [value for value in period_returns if value > 0]
    return {
        "period_count": periods,
        "total_return_pct": round(total_return * 100, 4),
        "annualized_return_pct": round(annualized * 100, 4) if annualized is not None else None,
        "max_drawdown_pct": round(_max_drawdown(equity) * 100, 4),
        "volatility_pct": round(volatility * 100, 4) if volatility is not None else None,
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "win_rate": round(len(wins) / periods, 4) if periods else None,
        "ending_equity": round(equity[-1], 6),
    }


def _score(metrics: dict[str, Any]) -> float:
    total = float(metrics.get("total_return_pct") or 0.0)
    drawdown = abs(float(metrics.get("max_drawdown_pct") or 0.0))
    sharpe = float(metrics.get("sharpe") or 0.0)
    return round(total - drawdown * 0.7 + sharpe * 2.0, 4)


def _run_backtest(payload: dict[str, Any], strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    prices, dates, source = _extract_prices(payload)
    selected_strategy = dict(strategy or payload.get("strategy") or {})
    positions, normalized_strategy = _positions_for_strategy(prices, payload, selected_strategy)
    returns = _period_returns(prices)
    if len(positions) != len(returns):
        raise ValueError("position_return_length_mismatch")
    cost_bps = float(selected_strategy.get("cost_bps") or payload.get("cost_bps") or 0.0)
    strategy_returns: list[float] = []
    prev_position = 0.0
    turnover = 0.0
    for position, period_return in zip(positions, returns):
        change = abs(position - prev_position)
        turnover += change
        cost = change * cost_bps / 10000.0
        strategy_returns.append(position * period_return - cost)
        prev_position = position
    benchmark_returns = returns
    periods_per_year = int(payload.get("periods_per_year") or 252)
    strategy_metrics = _metrics(strategy_returns, periods_per_year=periods_per_year)
    benchmark_metrics = _metrics(benchmark_returns, periods_per_year=periods_per_year)
    strategy_metrics["score"] = _score(strategy_metrics)
    benchmark_metrics["score"] = _score(benchmark_metrics)
    return {
        "strategy_id": selected_strategy.get("id") or payload.get("strategy_id") or normalized_strategy.get("type"),
        "strategy": normalized_strategy,
        "series_source": source,
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "periods_per_year": periods_per_year,
        "cost_bps": cost_bps,
        "exposure": round(sum(abs(value) for value in positions) / len(positions), 4) if positions else 0,
        "turnover": round(turnover, 4),
        "metrics": strategy_metrics,
        "benchmark": benchmark_metrics,
        "interpretation": _interpret_metrics(strategy_metrics, benchmark_metrics),
    }


def _interpret_metrics(metrics: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    alpha = float(metrics.get("total_return_pct") or 0.0) - float(benchmark.get("total_return_pct") or 0.0)
    drawdown = abs(float(metrics.get("max_drawdown_pct") or 0.0))
    if alpha > 0 and drawdown <= max(25.0, abs(float(benchmark.get("max_drawdown_pct") or 0.0))):
        verdict = "promising_research_candidate"
    elif alpha > 0:
        verdict = "higher_return_higher_risk"
    else:
        verdict = "not_validated"
    return {
        "alpha_total_return_pct": round(alpha, 4),
        "verdict": verdict,
        "paper_only": True,
    }


def _validation_gate(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else dict()
    min_return = float(payload.get("min_total_return_pct") if payload.get("min_total_return_pct") is not None else 0.0)
    max_drawdown = float(payload.get("max_drawdown_pct") if payload.get("max_drawdown_pct") is not None else 30.0)
    min_periods = int(payload.get("min_periods") or 20)
    periods = int(metrics.get("period_count") or 0)
    total = float(metrics.get("total_return_pct") or 0.0)
    drawdown = abs(float(metrics.get("max_drawdown_pct") or 0.0))
    checks = [
        {"name": "min_periods", "ok": periods >= min_periods, "actual": periods, "threshold": min_periods},
        {"name": "min_total_return_pct", "ok": total >= min_return, "actual": total, "threshold": min_return},
        {"name": "max_drawdown_pct", "ok": drawdown <= max_drawdown, "actual": drawdown, "threshold": max_drawdown},
    ]
    passed = all(check["ok"] for check in checks)
    return {
        "passed": passed,
        "grade": "pass" if passed else "fail",
        "checks": checks,
        "decision_allowed": False,
    }


def _write_backtest_artifact(command: str, result: dict[str, Any]) -> str:
    out_dir = _workspace_dir() / "memory" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{command}-{stamp}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def _strategy_backtest(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _run_backtest(payload)
    artifact = _write_backtest_artifact(command, result) if payload.get("write_artifact") else None
    return _wrap(command, payload, result, sources=[result["series_source"]], artifacts=[artifact] if artifact else [])


def _agent_validation_backtest(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _run_backtest(payload)
    result["validation"] = _validation_gate(result, payload)
    artifact = _write_backtest_artifact(command, result) if payload.get("write_artifact") else None
    return _wrap(command, payload, result, sources=[result["series_source"]], artifacts=[artifact] if artifact else [])


def _batch_backtest(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    strategies = payload.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        return _fail(command, payload, ["strategies_required"])
    if len(strategies) > 50:
        return _fail(command, payload, ["too_many_strategies"])
    results = []
    for index, strategy in enumerate(strategies):
        if not isinstance(strategy, dict):
            return _fail(command, payload, [f"invalid_strategy:{index}"])
        strategy_payload = dict(payload)
        strategy_payload.pop("strategies", None)
        try:
            item = _run_backtest(strategy_payload, strategy=strategy)
        except ValueError as exc:
            item = {"strategy_id": strategy.get("id") or index, "ok": False, "error": str(exc)}
        results.append(item)
    valid = [item for item in results if isinstance(item.get("metrics"), dict)]
    ranked = sorted(valid, key=lambda item: item.get("metrics", {}).get("score", -999999), reverse=True)
    result = {
        "count": len(results),
        "valid_count": len(valid),
        "results": results,
        "ranking": [{"strategy_id": item.get("strategy_id"), "score": item.get("metrics", {}).get("score")} for item in ranked],
        "best": ranked[0] if ranked else None,
    }
    if not valid:
        return _fail(command, payload, ["no_valid_backtest_results"])
    artifact = _write_backtest_artifact(command, result) if payload.get("write_artifact") else None
    return _wrap(command, payload, result, sources=["payload.strategies"], artifacts=[artifact] if artifact else [])


def _strategy_compare(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw_results = payload.get("results")
    if raw_results is None and isinstance(payload.get("strategies"), list):
        batch = _batch_backtest("batch-backtest", payload)
        if not batch.get("ok"):
            return batch
        raw_results = batch.get("result", {}).get("results")
    if not isinstance(raw_results, list) or not raw_results:
        return _fail(command, payload, ["results_or_strategies_required"])
    comparable = []
    for item in raw_results:
        if not isinstance(item, dict) or not isinstance(item.get("metrics"), dict):
            continue
        metrics = dict(item.get("metrics") or {})
        if "score" not in metrics:
            metrics["score"] = _score(metrics)
        comparable.append({
            "strategy_id": item.get("strategy_id"),
            "score": metrics.get("score"),
            "total_return_pct": metrics.get("total_return_pct"),
            "max_drawdown_pct": metrics.get("max_drawdown_pct"),
            "sharpe": metrics.get("sharpe"),
            "verdict": (item.get("interpretation") or {}).get("verdict") if isinstance(item.get("interpretation"), dict) else None,
        })
    if not comparable:
        return _fail(command, payload, ["no_comparable_results"])
    comparable.sort(key=lambda item: item.get("score", -999999), reverse=True)
    result = {
        "ranking": comparable,
        "best": comparable[0],
        "paper_only": True,
    }
    return _wrap(command, payload, result, sources=["payload.results"])


def _grid_values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    grid = payload.get("grid") or payload.get("params")
    if not isinstance(grid, dict):
        grid = {
            "short_window": payload.get("short_windows") or [3, 5, 10],
            "long_window": payload.get("long_windows") or [15, 20, 30],
        }
    normalized: dict[str, list[Any]] = {}
    for key, value in grid.items():
        if isinstance(value, list):
            normalized[key] = value
        else:
            normalized[key] = [value]
    keys = sorted(normalized)
    combos = []
    for values in itertools.product(*(normalized[key] for key in keys)):
        item = dict(zip(keys, values))
        if "short_window" in item and "long_window" in item:
            try:
                if int(item["short_window"]) >= int(item["long_window"]):
                    continue
            except Exception:
                continue
        combos.append(item)
    return combos


def _grid_search(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    combos = _grid_values(payload)
    if not combos:
        return _fail(command, payload, ["grid_parameters_required"])
    if len(combos) > int(payload.get("max_combinations") or 100):
        return _fail(command, payload, ["too_many_grid_combinations"])
    strategies = []
    for combo in combos:
        strategy = {"type": payload.get("strategy_type") or "ma_cross", **combo}
        strategy["id"] = strategy.get("id") or "-".join(f"{key}{value}" for key, value in sorted(combo.items()))
        strategies.append(strategy)
    batch_payload = dict(payload)
    batch_payload["strategies"] = strategies
    batch = _batch_backtest("batch-backtest", batch_payload)
    if not batch.get("ok"):
        return batch
    result = {
        "evaluated": batch.get("result", {}).get("valid_count"),
        "grid": combos,
        "ranking": batch.get("result", {}).get("ranking"),
        "best": batch.get("result", {}).get("best"),
        "recommendation": {
            "paper_only": True,
            "note": "Use the best parameters only as research input; do not deploy without out-of-sample validation.",
        },
    }
    artifact = _write_backtest_artifact(command, result) if payload.get("write_artifact") else None
    return _wrap(command, payload, result, sources=["payload.grid", "payload.price_series"], artifacts=[artifact] if artifact else [])


def _parameter_optimization(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = _grid_search("grid-search-advisor", payload)
    if not result.get("ok"):
        return result
    inner = result.get("result", {})
    optimized = {
        "cadence": "biweekly",
        "best": inner.get("best"),
        "ranking": inner.get("ranking"),
        "next_review_days": 14,
        "paper_only": True,
    }
    artifact = _write_backtest_artifact(command, optimized) if payload.get("write_artifact") else None
    return _wrap(command, payload, optimized, sources=result.get("sources", []), artifacts=[artifact] if artifact else [])


def _parse_legacy_output(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw.splitlines()[-1]) if raw else dict()
    except Exception:
        return {"ok": False, "raw": raw}


def _legacy_nightly_eval(payload: dict[str, Any]) -> dict[str, Any] | None:
    repo_root = _repo_root()
    if repo_root is None:
        return None
    script = repo_root / "scripts" / "backtest_monthly.py"
    if not script.exists():
        return None
    months = int(payload.get("months", 12))
    iterations = int(payload.get("iterations", 40))
    target_pass = float(payload.get("target_return_pass", 1.0))
    target_excellent = float(payload.get("target_return_excellent", 3.0))
    max_drawdown = float(payload.get("max_drawdown", 0.3))
    auto_optimize = bool(payload.get("auto_optimize", True))
    weights_path = _workspace_dir() / "config" / "trade_weights.json"

    def _run(cmd: list[str]) -> dict:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return _parse_legacy_output(proc.stdout.strip())

    eval_cmd = [
        "python3", str(script),
        "--mode", "eval",
        "--months", str(months),
        "--target-return-pass", str(target_pass),
        "--target-return-excellent", str(target_excellent),
        "--max-drawdown", str(max_drawdown),
        "--iterations", "1",
        "--max-iterations", "1",
        "--target-score", "0",
    ]
    eval_result = _run(eval_cmd)
    best = (eval_result.get("best") or {}) if isinstance(eval_result, dict) else {}
    optimize_result = None
    if auto_optimize and best.get("grade") == "fail":
        opt_cmd = [
            "python3", str(script),
            "--mode", "optimize",
            "--months", str(months),
            "--target-return-pass", str(target_pass),
            "--target-return-excellent", str(target_excellent),
            "--max-drawdown", str(max_drawdown),
            "--iterations", str(iterations),
            "--max-iterations", str(max(iterations, 60)),
            "--write-weights", str(weights_path),
        ]
        optimize_result = _run(opt_cmd)
        eval_result = _run(eval_cmd)
        best = (eval_result.get("best") or {}) if isinstance(eval_result, dict) else best
    return {
        "mode": "legacy_backtest_monthly",
        "eval": eval_result,
        "optimize": optimize_result,
        "best": best,
        "weights_path": str(weights_path),
    }


def _nightly_eval(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    has_inline_series = any(key in payload for key in ("price_series", "prices", "equity_curve", "returns", "data", "records", "series_path"))
    if has_inline_series:
        return _agent_validation_backtest(command, payload)
    legacy = _legacy_nightly_eval(payload)
    if legacy is None:
        return _fail(command, payload, ["historical_series_or_legacy_backtest_required"])
    return _wrap(command, payload, legacy, sources=["scripts/backtest_monthly.py"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", [])}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")
        if args.command == "agent-validation-backtest":
            output = _agent_validation_backtest(args.command, payload)
        elif args.command == "batch-backtest":
            output = _batch_backtest(args.command, payload)
        elif args.command == "grid-search-advisor":
            output = _grid_search(args.command, payload)
        elif args.command == "parameter-optimization-biweekly":
            output = _parameter_optimization(args.command, payload)
        elif args.command == "strategy-backtest":
            output = _strategy_backtest(args.command, payload)
        elif args.command == "strategy-compare":
            output = _strategy_compare(args.command, payload)
        elif args.command == "nightly-eval-12m":
            output = _nightly_eval(args.command, payload)
        else:
            output = _fail(args.command, payload, ["unknown_command"])
    except ValueError as exc:
        output = _fail(args.command, payload, [str(exc)])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
