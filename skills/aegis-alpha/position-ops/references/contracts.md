# position-ops Contracts

All commands return:

```json
{
  "package": "position-ops",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "decision_allowed": false,
  "max_action_level": "analysis_only",
  "sources": [],
  "warnings": [],
  "errors": [],
  "result": {}
}
```

## Safety Rules

- This skill never authorizes trade execution.
- Missing position state returns `ok=false`.
- Missing position state must not be interpreted as empty holdings.
- Legacy SQLite import is opt-in via `AI_INVEST_LEGACY_MEMORY_DB`; no host path is hardcoded.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `position-management-v2` | implemented | none | known positions and source path |
| `portfolio-risk-check` | implemented | optional `max_single_position_pct` | concentration flags and value-source warnings |
| `position-sizing-advisor` | implemented | `portfolio_value`, `risk_budget_pct`, `stop_loss_pct` | paper-plan sizing limits |

## Failure Output

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["positions_state_missing"],
  "result": {
    "portfolio_state_known": false,
    "positions": null,
    "note": "Position state is unavailable; do not infer an empty portfolio."
  }
}
```
