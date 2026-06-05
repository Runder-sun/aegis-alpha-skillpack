# portfolio-ops Contracts

## Common Envelope

All commands return a non-decision envelope:

```json
{
  "package": "portfolio-ops",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {"status": "delegated"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "analysis_only",
  "source": "<internal-skill>::<command>",
  "sources": ["<internal-skill>::<command>"],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {"delegated": {}}
}
```

| command | routes to | status |
|---|---|---|
| `portfolio-add` | `portfolio-management::portfolio-add` | implemented |
| `portfolio-remove` | `portfolio-management::portfolio-remove` | implemented |
| `portfolio-view` | `portfolio-management::portfolio-view` | implemented |
| `portfolio-report` | `portfolio-management::portfolio-report` | implemented |
| `record-trade` | `portfolio-management::record-trade` | implemented |
| `portfolio-risk-check` | `position-ops::portfolio-risk-check` | implemented |
| `position-sizing-advisor` | `position-ops::position-sizing-advisor` | implemented |
| `position-management` | `position-ops::position-management-v2` | implemented |

## Safety Rules

- Missing portfolio state fails closed and must not be interpreted as empty
  holdings.
- Unknown position, oversell, invalid quantity, corrupt state, or missing risk
  budget returns `ok=false`.
- Sizing guidance is paper-only, requires explicit risk inputs, and never
  authorizes execution.
- Position values must identify whether they come from cost basis, explicit
  market price, or another supplied valuation source.

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["portfolio_state_missing"],
  "missing_critical_inputs": ["portfolio_state_missing"],
  "result": {
    "note": "Portfolio state is unavailable; do not infer an empty portfolio."
  }
}
```
