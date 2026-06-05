---
name: trade-planning
description: "Trade setup planning and strategy generation."
metadata: {"openclaw": {"skillKey": "trade-planning", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# trade-planning

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### full-investment-plan
Legacy mapping: `full_investment_plan`
Compose short-term setup, themes, targets, strategy, and technical references
into a paper-only plan.

### short-term-analysis
Legacy mapping: `short_term_analysis`
Score short-term candidates under market filter and risk caps.

### stock-technical-scan
Legacy mapping: `stock_technical_scan`
Calculate technical trend, entry zone, stop reference, and invalidation triggers
from supplied levels.

### strategy-advisor
Legacy mapping: `strategy_advisor`
Generate paper-only strategy rules from market filter, risk level, and top
candidates.

### theme-identification
Legacy mapping: `theme_identification`
Identify active themes from payload or latest market prewarm snapshot.

### theme-targets
Legacy mapping: `theme_targets`
Group candidate targets by theme for paper-only planning.

### trading-strategy-v2
Legacy mapping: `trading_strategy_v2`
Return the full investment plan under a versioned strategy schema.

## Runtime Notes
### Data Sources
- Prewarm `hhxg_snapshot` for hotmoney candidates.
- Prewarm `themesurfer_signal` for LOCKOUT/FULL gate.

### Outputs
- Common envelope with `ok`, `decision_allowed`,
  `requires_human_confirmation`, `warnings`, `errors`, and `result`.
- `short-term-analysis` returns gate status, candidates, risk caps, and a
  paper-only planning note.
- Candidate scoring schema (event/trend/heat/sentiment + risk_penalty) is included for auditability.

### Failure & Fallback
- If ThemeSurfer is missing, new positions are restricted.
- Missing candidates/themes/technical levels fail closed for the relevant
  section.
- `decision_allowed` is always false and `requires_human_confirmation` is
  always true.

### Config
- Optional weights file: `workspace/config/trade_weights.json`
  - Keys: `event`, `trend`, `heat`, `sentiment` (will be normalized to sum=1).
  - If missing, defaults to 0.3/0.3/0.2/0.2.
