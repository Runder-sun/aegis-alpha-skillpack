# quality-gate Contracts

## Common Envelope

All commands return a quality-validation envelope:

```json
{
  "package": "quality-gate",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {"status": "runtime_artifact_check"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "quality_validation_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

| command | legacy_functions |
|---|---|
| `nightly-quality-gate` | `nightly_quality_gate` |
| `backtest-loop` | `backtest_loop` |

Cross-package calls are only allowed through command-level data contracts.
Do not import internal implementation files from another package directly.

## Failure Rules

- Missing prewarm, pipeline run, report, or backtest artifact returns `ok=false`.
- A failing validation gate is explicit evidence of quality failure; it is not a
  reason to continue with executable advice.
- Delegation to `quant-validation` must preserve its `decision_allowed=false`
  and research-validation-only semantics.
- No command may mark stale or missing artifacts as passed.
