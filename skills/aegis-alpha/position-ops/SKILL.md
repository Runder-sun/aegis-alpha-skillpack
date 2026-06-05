---
name: position-ops
description: "Position sizing and risk operations."
metadata:
  openclaw:
    skillKey: position-ops
    packageProfile: invest-core-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: portfolio-ops
---

# position-ops

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### portfolio-risk-check
Legacy mapping: `portfolio_risk_check`
Check position concentration and missing-value risk from known positions.

Payload:
- `max_single_position_pct` (number, optional, default `0.2`)

### position-management-v2
Legacy mapping: `position_management_v2`
Load known positions from workspace state.

Payload: `{}`

## Runtime Notes
### Data Sources
- Reads `memory/positions.json` under `AEGIS_ALPHA_WORKSPACE`.
- Optional legacy SQLite fallback is only used when `AI_INVEST_LEGACY_MEMORY_DB`
  is explicitly configured.

### Outputs
- Common JSON envelope with `ok`, `decision_allowed`, `warnings`, `errors`,
  `sources`, and `result`.
- Position outputs include `portfolio_state_known`.

### Failure & Fallback
- If state is missing or invalid, returns `ok=false` and does not infer an empty
  portfolio.
- `decision_allowed` is always false; this skill supports analysis and paper
  planning only.

### position-sizing-advisor
Legacy mapping: `position_sizing_advisor`
Calculate a paper-plan position size from risk budget and stop-loss distance.

Required payload:
- `portfolio_value`
- `risk_budget_pct`
- `stop_loss_pct`

Optional payload:
- `max_single_position_pct` (default `0.2`)
- `current_exposure`
