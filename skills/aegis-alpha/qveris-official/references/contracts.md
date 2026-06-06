# QVeris Official Contracts

## Common Envelope

All commands return a data-only envelope:

```json
{
  "package": "qveris-official",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "QVeris wrapper output is evaluated at command runtime"
  },
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "data_only",
  "source": ["https://qveris.ai/api/v1"],
  "sources": ["https://qveris.ai/api/v1"],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Commands

| command | purpose | writes state |
|---|---|---|
| `search` | Search QVeris for tools matching a capability query | no |
| `get-by-ids` | Fetch metadata for known tool IDs | no |
| `execute` | Execute a selected tool with explicit parameters | no |

## Safety Rules

- `decision_allowed` is always `false`.
- `QVERIS_API_KEY` is required and must never be logged or written to disk.
- Failed search, metadata lookup, or execution must return `ok=false` with
  `freshness.status=unavailable`.
- Empty QVeris results are not proof that evidence, risk, or opportunity is
  absent. Callers must preserve `missing_critical_inputs` when QVeris is needed.
