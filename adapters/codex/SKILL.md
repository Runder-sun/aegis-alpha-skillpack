---
name: aegis-alpha
description: Use for research-only investment workflows that require market data provenance, macro regime analysis, theme rotation, equity screening, equity research, paper trade planning, portfolio/risk review, advice lifecycle tracking, pipeline orchestration, quality gates, quant validation, report evolution, and strict fail-closed financial safety. Never use for live trading or executable advice.
metadata:
  short-description: Research-only investment workflow skillpack
---

# Aegis Alpha

This aggregate wrapper exposes the shared canonical skillpack installed at
`../.aegis-alpha-core`.

## Public Surface

Prefer the individual native public skills when the request clearly matches one area:

- `aegis-alpha-information-retrieval`
- `aegis-alpha-market-data`
- `aegis-alpha-market-intel`
- `aegis-alpha-macro-regime`
- `aegis-alpha-theme-cycle`
- `aegis-alpha-equity-screening`
- `aegis-alpha-equity-research`
- `aegis-alpha-trade-planning`
- `aegis-alpha-portfolio-ops`
- `aegis-alpha-advice-lifecycle`
- `aegis-alpha-pipeline`
- `aegis-alpha-quality-gate`
- `aegis-alpha-quant-validation`
- `aegis-alpha-report-evolution`
- `aegis-alpha-execution-automation`

Use this aggregate wrapper for cross-skill investment workflows or when the
right public skill is unclear. Internal skills are adapters only. Do not route
user work directly to them unless performing maintenance.

## Safety Rules

- Treat every output as research-only unless it explicitly says otherwise.
- `decision_allowed` must remain `false`.
- Missing critical evidence must fail closed.
- Do not treat an empty result as no opportunity, no risk, or empty holdings.
- Trade plans are paper plans and require human confirmation outside the skill.

## How To Call

Read `../.aegis-alpha-core/data/surface-map.json` to choose a public skill.
Then inspect `../.aegis-alpha-core/<skill>/data/command-manifest.json` and
`../.aegis-alpha-core/<skill>/references/contracts.md`.

Run commands from this wrapper directory with:

```bash
python3 ../.aegis-alpha-core/<skill>/scripts/dispatch.py --command <command> --payload '<json>'
```

Set `AEGIS_ALPHA_WORKSPACE` to control runtime artifacts. If unset, dispatchers
use `~/.aegis-alpha/workspace`.
