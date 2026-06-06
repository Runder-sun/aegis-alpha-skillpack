# Jin10 Feed Contracts

## Common Envelope

All commands return a data-only envelope:

```json
{
  "package": "jin10-feed",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "Jin10 feed data is collected at command runtime or daemon runtime"
  },
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "data_only",
  "source": ["https://www.jin10.com/"],
  "sources": ["https://www.jin10.com/"],
  "artifacts": ["<workspace>/memory/jin10/snapshot.json"],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Commands

| command | purpose | writes state |
|---|---|---|
| `jin10-snapshot` | Fetch one-shot important news snapshot | yes, snapshot artifact |
| `jin10-daemon-start` | Start daemon monitor | yes, PID/log artifacts |
| `jin10-daemon-stop` | Stop daemon monitor | yes, PID artifact |
| `jin10-daemon-status` | Inspect daemon PID status | no |

## Safety Rules

- `decision_allowed` is always `false`.
- Missing Playwright, network failure, or invalid output must return `ok=false`
  with `freshness.status=unavailable`.
- Empty or unavailable news must not be interpreted as no market risk.
- Downstream market-intel callers must preserve `source`, `freshness`, and
  `missing_critical_inputs` when Jin10 evidence is required.
