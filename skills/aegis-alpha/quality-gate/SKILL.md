---
name: quality-gate
description: "Nightly quality checks and backtest loops."
metadata: {"openclaw": {"skillKey": "quality-gate", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# quality-gate

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

For dynamic theme and stock-pool workflows, quality checks should audit evidence
coverage, stale themes, stale candidates, over-promoted lifecycle states, and
valuation/crowding mismatches. These checks support the theme system but should
not replace the package's broader nightly quality and backtest duties.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### nightly-quality-gate
Legacy mapping: `nightly_quality_gate`
Evaluates nightly prewarm/pipeline/report artifacts and stores a structured summary.

### backtest-loop
Legacy mapping: `backtest_loop`
Runs the nightly quant backtest loop and stores a structured summary.

## Runtime Notes
### Data Sources
- Prewarm snapshot: `memory/prewarm/nightly-prewarm-*.json`.
- Pipeline runs: `memory/pipeline_runs/nightly-*.json`.
- Reports: `memory/reports/nightly-strategy-report-*.md` or `memory/reports/nightly-report-*.md`.

### Outputs
- Writes JSON summaries to:
  - `memory/quality_gate/quality-gate-<timestamp>.json`
  - `memory/backtests/backtest-<timestamp>.json`

### Failure & Fallback
- Missing artifacts produce safe defaults and `ok=false` checks.
- Backtest loop stores the raw quant-validation output even on failure.
