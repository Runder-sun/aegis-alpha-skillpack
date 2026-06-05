# portfolio-management Contracts

All commands return a common envelope:

```json
{
  "package": "portfolio-management",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "decision_allowed": false,
  "max_action_level": "analysis_only",
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "result": {}
}
```

## Safety Rules

- This package never authorizes trades.
- `decision_allowed` is always `false`.
- Missing or invalid portfolio state returns `ok=false`.
- Missing portfolio state must not be interpreted as an empty portfolio.
- Sell trades fail closed when the target position is unknown.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `portfolio-add` | implemented | `code`, `quantity`, optional `price` | updated position and artifacts |
| `portfolio-advice` | implemented | none | analysis-only hygiene advice and missing critical inputs |
| `portfolio-remove` | implemented | `code` | removed position and artifacts |
| `portfolio-report` | implemented | none | cost and market-value summary |
| `portfolio-view` | implemented | none | known positions |
| `record-trade` | implemented | `code`, `side`, `quantity`, `price` | updated positions and trade artifact |

## State Files

- `memory/positions.json`: canonical local position state.
- `memory/trades.jsonl`: append-only trade event log.

State is resolved under `AEGIS_ALPHA_WORKSPACE`, falling back to
`~/.aegis-alpha/workspace`.

## Failure Outputs

Missing state:

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["portfolio_state_missing"],
  "result": {
    "portfolio_state_known": false,
    "positions": null,
    "note": "Portfolio state is unavailable; do not infer an empty portfolio."
  }
}
```

Unknown sell target:

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["position_not_found"]
}
```
