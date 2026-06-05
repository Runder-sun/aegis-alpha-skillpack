# weekly-stock-pool Contracts

| command | legacy_functions | status | payload | result |
|---|---|---|---|---|
| `weekly-stock-pool` | `weekly_stock_pool` | implemented | `min_candidates`, `max_age_minutes`, `write_artifact` | common research-only envelope |

Cross-package calls are only allowed through command-level data contracts.
Do not import internal implementation files from another package directly.

## Common Envelope

Every response includes:

- `ok`: boolean success flag.
- `decision_allowed`: always `false`.
- `requires_human_confirmation`: always `true`.
- `max_action_level`: always `research_only`.
- `as_of`, `freshness`, `sources`, `artifacts`.
- `warnings`, `errors`, `missing_critical_inputs`.
- `result`: command-specific payload.

## Success Result

`result` contains:

- `candidate_count`: number of extracted candidates.
- `candidates`: candidate objects from weekly pipeline/context artifacts.
- `filters`: applied upstream filter markers.
- `pool_state`: `available`.
- `prewarm_keys`: top-level keys observed in the prewarm snapshot.
- `source`: artifact glob map used by the command.

## Fail-Closed Errors

The command fails closed when any critical input is missing or unreadable:

- `weekly_pipeline_runs_missing`
- `weekly_pipeline_context_missing`
- `prewarm_snapshot_missing`
- `artifact_read_error`
- `candidates_missing`

On failure, `result.candidates` is `null`, not an empty list, so callers cannot
mistake missing evidence for an empty market opportunity set.
