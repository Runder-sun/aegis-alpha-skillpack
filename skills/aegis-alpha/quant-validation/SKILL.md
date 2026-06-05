---
name: quant-validation
description: "Research-only offline backtesting, strategy comparison, bounded parameter grid search, and nightly validation for investment hypotheses."
metadata: {"openclaw": {"skillKey": "quant-validation", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# quant-validation

Use this skill when an investment hypothesis, signal, strategy, or parameter set
needs quantitative validation before it can enter research reporting or review.

This skill does not approve live trading. Every command returns
`decision_allowed=false`, `requires_human_confirmation=true`, and
`max_action_level=research_validation_only`.

## Safety Rules

- Missing historical price/return series fails closed.
- Invalid, too-short, non-numeric, or non-positive series fails closed.
- Backtest and optimization results are paper/research evidence only.
- Parameter optimization is bounded; large grids fail closed.
- Ranking a strategy never means it can be executed without independent
  out-of-sample validation and human review.

## Supported Series

Payload may provide one of:

- `price_series`: list of objects with `close`, `price`, `value`, `equity`, or
  `nav`
- `returns`: list of numeric period returns or objects with `return`
- `series_path`: JSON file under the active workspace

Optional fields include `periods_per_year`, `cost_bps`, `signals`, and strategy
configuration.

## Commands

### `strategy-backtest`

Backtests one strategy and compares it against buy-and-hold.

Supported strategy types:

- `buy_and_hold`
- `cash`
- `ma_cross`
- `threshold`
- explicit `signals`

### `agent-validation-backtest`

Runs `strategy-backtest` plus validation gates:

- `min_periods`
- `min_total_return_pct`
- `max_drawdown_pct`

### `batch-backtest`

Runs multiple strategies against the same series and ranks valid results.

### `strategy-compare`

Ranks supplied backtest results, or runs `batch-backtest` when `strategies` and
series are supplied.

### `grid-search-advisor`

Runs bounded parameter search. Default strategy is moving-average cross. The
result is a paper-only research candidate.

### `parameter-optimization-biweekly`

Packages the grid-search result as a biweekly parameter review with
`next_review_days=14`.

### `nightly-eval-12m`

Uses explicit payload history when provided. If no series is supplied and a
legacy `scripts/backtest_monthly.py` is available, it runs that script. If
neither exists, it fails closed.

## Output Contract

See `references/contracts.md`. All commands return a common envelope with
`as_of`, `freshness`, `source`, `artifacts`, `warnings`, `errors`,
`missing_critical_inputs`, and `result`.
