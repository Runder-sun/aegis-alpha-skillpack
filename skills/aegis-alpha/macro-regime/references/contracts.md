# macro-regime Contracts

All commands return:

```json
{
  "package": "macro-regime",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "macro-regime freshness is inherited from latest prewarm artifact, macro cache, and explicit provider timestamps"
  },
  "decision_allowed": false,
  "max_action_level": "research_only",
  "source": [],
  "sources": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Safety Rules

- Macro outputs are research constraints only.
- The skill never authorizes buy/sell actions or executable allocation.
- Missing macro, risk, flow, heat, or sector evidence returns `ok=false`.
- Missing data must not be interpreted as neutral regime, low risk, or no alert.
- Risk budgets are references for downstream paper planning, not portfolio
  instructions.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `macro-regime-query` | implemented | prewarm `hhxg_snapshot` | risk, risk budget reference, capital flow, sector rotation, concept heat |
| `macro-alert-check` | implemented | snapshot market risk fields | alert list and risk mode |
| `concept-heat` | implemented | `hot_themes` or strong sectors | ranked concept heat |
| `sector-rotation` | implemented | snapshot sectors | strong/weak sector rotation |
| `capital-flow-analysis` | implemented | hotmoney and sectors | capital flow summary |
| `market-review` | implemented | snapshot summary and domestic macro | market review bundle |
| `domestic-macro` | implemented | prewarm/provider macro indicators | PMI/CPI/PPI/liquidity/credit/growth |
| `global-macro-analysis` | implemented | provider/global asset data and optional prewarm news | cross-asset regime and events |

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["macro_regime_inputs_missing"],
  "result": {
    "note": "Macro evidence is incomplete; do not infer a market regime or portfolio action.",
    "missing_critical_inputs": ["macro_regime_inputs_missing"]
  }
}
```
