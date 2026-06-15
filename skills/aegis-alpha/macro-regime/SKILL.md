---
name: macro-regime
description: "Analyze macro regime, liquidity, cross-asset risk mode, A-share capital flow, concept heat, and sector rotation with fail-closed investment safety."
metadata: {"openclaw": {"skillKey": "macro-regime", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# macro-regime

Use this package when the task needs upstream market regime context before theme
selection, screening, portfolio risk review, or paper-only trade planning.

For dynamic theme work, use macro outputs as a gate rather than a discovery
substitute. Strong regime can increase theme-expression confidence; weak regime
can downgrade aggressiveness, but it does not by itself validate or invalidate
an industry theme.

## Runtime

Run commands through `scripts/dispatch.py` with `--command <name>` and optional
JSON `--payload`. The dispatcher reads `AEGIS_ALPHA_WORKSPACE` when set;
otherwise it uses `~/.aegis-alpha/workspace`.

## Public Commands

- `macro-regime-query`: compact regime bundle with risk mode, risk budget
  reference, capital flow, sector rotation, and concept heat.
- `macro-alert-check`: risk alerts from sentiment, limit-down, fried-board, and
  promotion-rate inputs.
- `concept-heat`: hot theme/sector heat ranking.
- `sector-rotation`: strong/weak sector rotation snapshot.
- `capital-flow-analysis`: hot-money and sector capital-flow summary.
- `market-review`: market summary plus domestic macro context.
- `domestic-macro`: China PMI/CPI/PPI, liquidity, credit, and growth snapshot.
- `global-macro-analysis`: global cross-asset regime, macro cycle, risk budget,
  news, and events.

## Data Sources

Primary local source is the latest
`memory/prewarm/nightly-prewarm-*.json`, especially `hhxg_snapshot`. Some macro
commands can enrich from configured providers such as Jin10, Tushare, Finnhub,
Yahoo, AkShare, QVeris, or xreach when available.

Provider enrichment is not authorization to continue when evidence is missing.
If critical inputs are absent, commands return `ok=false`.

## Outputs

All commands return `ok`, `decision_allowed`, `max_action_level`, `sources`,
`warnings`, `errors`, and `result`. `decision_allowed` is always false and
`max_action_level` is `research_only`.

Regime output is an upstream constraint, not a trade instruction. Downstream
skills may use it to filter themes, size paper plans, or block new-position
ideas, but final investment decisions require human confirmation.

## Failure Rules

- Missing snapshot inputs for A-share regime/flow/heat commands return
  `ok=false`.
- Missing global macro inputs return `ok=false` for global regime analysis.
- Missing domestic macro indicators return `ok=false` for domestic macro.
- Never treat missing macro data as neutral, low risk, or permission to trade.
