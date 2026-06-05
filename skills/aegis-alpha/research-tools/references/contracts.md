# research-tools Contracts

`research-tools` is now a narrow information-retrieval router. It does not own
investment analysis commands.

All commands return:

```json
{
  "package": "research-tools",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "decision_allowed": false,
  "max_action_level": "research_only",
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "result": {}
}
```

## Public Commands

| command | status | target |
|---|---|---|
| `analysis-history` | implemented | workspace memory artifacts |
| `help` | implemented | local command catalog |
| `search-and-extract` | implemented | `search-layer::search` or `content-extract::extract-url` |
| `set-preference` | implemented | `memory/research/preferences.json` |
| `web-content-fetch` | implemented | `content-extract::extract-url` |

## Rehomed Commands

| retired command | replacement |
|---|---|
| `asset-allocation` | `macro-regime`, `theme-cycle`, `trade-planning` |
| `asset-bull-bear` | `macro-regime` |
| `global-asset-scan` | `macro-regime::global-macro-analysis` |
| `grok-search` | `search-layer` |

## Safety Rules

- This skill never returns investment advice.
- Missing search/extraction evidence returns `ok=false`.
- Do not treat failed retrieval as proof that no evidence exists.
