# advice-lifecycle Contracts

This skill manages advice as a paper-only research lifecycle artifact.

## Common Envelope

All public commands return:

```json
{
  "package": "advice-lifecycle",
  "command": "<command>",
  "payload": {},
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current|partial|unavailable",
    "as_of": "<utc-runtime>",
    "policy": "<freshness statement>"
  },
  "ok": true,
  "decision_allowed": false,
  "requires_human_confirmation": true,
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

`source` and `sources` are both present for compatibility. New callers should use `source`.

## Safety Semantics

- `decision_allowed=false` means no output is executable advice.
- `requires_human_confirmation=true` means a human must review any downstream action.
- `max_action_level=research_only` means advice records, reports, and stats are research artifacts only.
- `ok=false` with `missing_critical_inputs` means the caller must stop the investment chain for that command.
- Missing advice ledger fails closed except when `investment-advice` creates the initial ledger from explicit recommendations.
- No command silently fetches fallback prices or substitutes data providers.

## Commands

| command | status | contract summary |
|---|---|---|
| `investment-advice` | implemented | Records explicit paper-only recommendation objects into `memory/advice/advice-ledger.json`. |
| `advice-history` | implemented | Reads the advice ledger with optional `status` and `limit`. |
| `advice-update-prices` | implemented | Updates current prices from explicit payload by id/code/name. |
| `update-daily-advice` | implemented | Applies explicit status/note updates by advice id. |
| `advice-expire-check` | implemented | Detects expired active advice; mutates only with `apply=true`. |
| `advice-track-report` | implemented | Returns row-level lifecycle and return tracking. |
| `advice-track-stats` | implemented | Returns status counts and priced return statistics. |
| `nightly-strategy` | implemented | Builds a 7-section evidence-bound strategy prompt. |
| `nightly-section` | implemented | Builds one evidence-bound nightly section prompt. |
| `morning-briefing` | implemented | Builds a morning briefing prompt. |
| `weekly-asset-report` | implemented | Builds a weekly macro/asset prompt. |
| `market-review` | implemented | Builds a post-market review prompt. |

## Failure Examples

Missing ledger:

```json
{
  "ok": false,
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "research_only",
  "errors": ["advice_ledger_missing"],
  "missing_critical_inputs": ["advice_ledger_missing"],
  "freshness": {"status": "unavailable"}
}
```

Missing explicit prices:

```json
{
  "ok": false,
  "errors": ["prices_required"],
  "missing_critical_inputs": ["prices_required"]
}
```

Prompt data gaps:

```json
{
  "ok": true,
  "warnings": ["critical_data_gaps_present"],
  "missing_critical_inputs": [
    {"field": "macro_regime.global.risk_mode", "reason": "missing", "sources": ["macro-regime::global-macro-analysis"]}
  ],
  "freshness": {"status": "partial"}
}
```

## Cross-Package Boundaries

Cross-package calls are allowed only through command-level payload/result contracts.
Do not import internal implementation files from another package directly.

Report commands may consume pipeline/prewarm/theme artifacts, but they must keep data gaps visible instead of filling them with inferred facts.
