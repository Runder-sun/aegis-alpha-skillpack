# trade-planning Contracts

All commands return:

```json
{
  "package": "trade-planning",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "trade plan freshness is inherited from candidates, technical levels, market gate, and supplied research evidence"
  },
  "decision_allowed": false,
  "max_action_level": "paper_plan_only",
  "requires_human_confirmation": true,
  "source": [],
  "sources": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Safety Rules

- This skill never authorizes trade execution.
- `decision_allowed` is always false.
- `requires_human_confirmation` is always true.
- Missing candidates, themes, or technical levels fail closed for their sections.
- Market filter `LOCKOUT` or unknown status restricts new positions.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `short-term-analysis` | implemented | candidates or prewarm snapshot | scored candidates, caps, market gate |
| `theme-identification` | implemented | themes or prewarm snapshot | active themes |
| `theme-targets` | implemented | candidates or prewarm snapshot | targets grouped by theme |
| `stock-technical-scan` | implemented | `price`, `ma20`, optional levels | trend, entry zone, stop reference |
| `strategy-advisor` | implemented | candidates and risk/filter context | paper-only strategy rules |
| `full-investment-plan` | implemented | candidates/themes/technical context | composed paper plan |
| `trading-strategy-v2` | implemented | same as full plan | versioned strategy envelope |

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "errors": ["candidates_missing"],
  "result": {
    "note": "Trade plan inputs are incomplete; do not infer an executable plan.",
    "missing_critical_inputs": ["candidates_missing"]
  }
}
```
