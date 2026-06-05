# quant-validation Contracts

Cross-package calls are only allowed through command-level data contracts. Do
not import internal implementation files from another package directly.

## Common Envelope

Every command returns:

```json
{
  "package": "quant-validation",
  "command": "strategy-backtest",
  "ok": false,
  "as_of": "2026-06-04T00:00:00Z",
  "freshness": {"status": "unavailable"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "research_validation_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": ["historical_series_required"],
  "missing_critical_inputs": ["historical_series_required"],
  "result": {
    "note": "Quant validation cannot prove the strategy without explicit, sufficient historical data."
  }
}
```

`ok=true` means the research validation operation completed. It never means a
strategy is approved for live trading.

## Command Table

| Command | Purpose | Critical inputs | Failure behavior |
|---|---|---|---|
| `strategy-backtest` | Backtest one explicit strategy | price/return series | Missing/invalid/short series fails closed |
| `agent-validation-backtest` | Backtest plus validation gates | series plus gate thresholds | Failing gates return `ok=true` with `validation.grade=fail`; missing data returns `ok=false` |
| `batch-backtest` | Run multiple strategies | `strategies` plus shared series | No valid strategy results fails closed |
| `strategy-compare` | Rank supplied results or strategies | comparable metrics or strategies+series | No comparable results fails closed |
| `grid-search-advisor` | Bounded parameter grid search | series plus grid/params | Missing grid or too many combinations fails closed |
| `parameter-optimization-biweekly` | Biweekly parameter review | same as grid search | Result is paper-only and requires future review |
| `nightly-eval-12m` | Nightly validation | explicit series or legacy backtest script | Fails closed if neither evidence path exists |

## Metrics

Single strategy backtests return:

- `total_return_pct`
- `annualized_return_pct`
- `max_drawdown_pct`
- `volatility_pct`
- `sharpe`
- `win_rate`
- `ending_equity`
- `score`

Benchmark metrics use buy-and-hold over the same series.

## Allowed Fallbacks

Allowed:

- `nightly-eval-12m` may use the legacy monthly backtest script when explicit
  history is not supplied and the script exists.

Not allowed:

- Missing historical series becomes a successful backtest.
- Parameter optimization writes deployable strategy weights without validation.
- Ranking output is treated as executable advice.
- Any output sets `decision_allowed=true`.

## Minimal Examples

Strategy backtest:

```json
{
  "price_series": [
    {"date": "2026-01-01", "close": 10},
    {"date": "2026-01-02", "close": 10.5},
    {"date": "2026-01-03", "close": 10.2}
  ],
  "strategy": {"type": "buy_and_hold"}
}
```

Grid search:

```json
{
  "price_series": [
    {"close": 10}, {"close": 11}, {"close": 12}, {"close": 11}, {"close": 13}
  ],
  "grid": {"short_window": [1, 2], "long_window": [3, 4]}
}
```
