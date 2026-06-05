# theme-cycle Contracts

All commands return:

```json
{
  "package": "theme-cycle",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "theme-cycle freshness is inherited from latest prewarm artifact, theme store, and macro-regime outputs"
  },
  "decision_allowed": false,
  "max_action_level": "research_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Safety Rules

- Theme-cycle outputs are research constraints only.
- The skill never authorizes executable rebalancing or buy/sell actions.
- Missing theme, event, market-risk, macro, or theme-store evidence returns
  `ok=false`.
- Missing data must not be interpreted as no active themes, no rotation risk, or
  permission to trade.
- `rebalance-check` actions are paper-only review labels.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `discover-themes` | implemented | prewarm sector snapshot | active and weak themes |
| `sector-cycle-panorama` | implemented | prewarm sectors | strong/weak cycle snapshot |
| `event-analysis` | implemented | payload/prewarm events plus themes | event-theme matches and risk flags |
| `theme-tracker` | implemented | local theme store | tracked themes and filters |
| `mainline-update` | implemented | macro regime plus prewarm theme data | persisted mainline updates |
| `themesurfer-check` | implemented | snapshot market risk fields | `FULL`/`LOCKOUT` gate |
| `themesurfer-signal` | implemented | snapshot market risk fields | versioned gate signal |
| `themesurfer-weekly-stats` | implemented | local theme store | lifecycle/status/history counts |
| `rebalance-check` | implemented | themes/store/snapshot plus market risk | paper-only rotation review actions |
| `macro-analysis` | implemented | macro-regime command contracts | global/domestic macro bundle |
| `global-medium-long-strategy` | implemented | macro-regime plus theme store | global mainline references |

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["market_risk_inputs_missing"],
  "result": {
    "note": "Theme-cycle evidence is incomplete; do not infer rotation, theme status, or portfolio action.",
    "missing_critical_inputs": ["market_risk_inputs_missing"]
  }
}
```
