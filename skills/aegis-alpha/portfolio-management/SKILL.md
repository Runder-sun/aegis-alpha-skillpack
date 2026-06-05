---
name: portfolio-management
description: "Portfolio state management and trade record operations."
metadata:
  openclaw:
    skillKey: portfolio-management
    packageProfile: invest-core-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: portfolio-ops
---

# portfolio-management

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### portfolio-add
Legacy mapping: `portfolio_add`
Create or merge a local position in `memory/positions.json`.

Required payload:
- `code` (string)
- `quantity` (number, > 0)

Optional payload:
- `name`
- `price` or `buy_price`
- `date`
- `notes`
- `merge` (boolean, default true)

### portfolio-advice
Legacy mapping: `portfolio_advice`
Return conservative portfolio hygiene advice. This command does not produce
trade recommendations because fresh market data, macro regime, and risk budget
must be supplied by upstream skills first.

### portfolio-remove
Legacy mapping: `portfolio_remove`
Remove a local position and append a removal event to `memory/trades.jsonl`.

Required payload:
- `code` (string)

Optional payload:
- `reason`
- `price`

### portfolio-report
Legacy mapping: `portfolio_report`
Summarize known positions, cost basis, and market value when positions include
`current_price`.

### portfolio-view
Legacy mapping: `portfolio_view`
Load local portfolio positions. Missing state fails closed and must not be
interpreted as an empty portfolio.

### record-trade
Legacy mapping: `record_trade`
Record a buy or sell trade and update local position quantities.

Required payload:
- `code` (string)
- `side` (`buy` or `sell`)
- `quantity` (number, > 0)
- `price` (number, >= 0)

Optional payload:
- `name`
- `notes`
- `allow_negative` (boolean, default false)

## Runtime Notes

### State
- Reads and writes `memory/positions.json` under `AEGIS_ALPHA_WORKSPACE`.
- Appends trade events to `memory/trades.jsonl`.
- If `AEGIS_ALPHA_WORKSPACE` is unset, uses `~/.aegis-alpha/workspace`.

### Safety
- `decision_allowed` is always false; this package manages state and produces
  portfolio hygiene analysis only.
- Missing portfolio state returns `ok=false` with `portfolio_state_known=false`.
- Do not infer an empty portfolio from missing or invalid state.
- Sell trades fail closed when the position is unknown or quantity is
  insufficient unless `allow_negative=true` is explicitly supplied.
