---
name: weekly-stock-pool
description: "Weekly stock pool consolidation and candidate summary."
metadata:
  openclaw:
    skillKey: weekly-stock-pool
    packageProfile: invest-core-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: equity-screening
---

# weekly-stock-pool

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### weekly-stock-pool
Legacy mapping: `weekly_stock_pool`
Builds a research-only weekly stock-pool snapshot from recent pipeline artifacts.

Use this command only as a consolidation step after the weekly pipeline has
already produced auditable artifacts. It does not fetch missing data, infer
missing candidates, or downgrade failures into an empty opportunity set.

## Runtime Notes
### Data Sources
- Weekly pipeline runs: `memory/pipeline_runs/weekly-*.json`.
- Weekly pipeline context: `memory/pipeline_context/weekly-context-*.json`.
- Prewarm snapshot: `memory/prewarm/nightly-prewarm-*.json`.

### Outputs
- Returns a common envelope with `ok`, `decision_allowed`, `requires_human_confirmation`,
  `max_action_level`, `as_of`, `freshness`, `sources`, `artifacts`, `warnings`,
  `errors`, `missing_critical_inputs`, and `result`.
- On success, writes JSON summaries to `memory/stock_pool/weekly-stock-pool-<timestamp>.json`
  unless `write_artifact=false`.
- `decision_allowed` is always false and `max_action_level` is always `research_only`.

### Failure & Fallback
- Missing weekly pipeline runs fail closed with `weekly_pipeline_runs_missing`.
- Missing weekly pipeline context fails closed with `weekly_pipeline_context_missing`.
- Missing prewarm snapshot fails closed with `prewarm_snapshot_missing`.
- Zero extracted candidates fails closed with `candidates_missing`.
- Never interpret missing data as an empty stock pool or a "no opportunity" signal.
- Do not issue executable trade advice from this command; downstream humans must
  review evidence, constraints, and sizing before any action.
