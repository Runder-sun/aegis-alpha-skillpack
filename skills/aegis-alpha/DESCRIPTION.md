---
description: AI investment workflow skills with a consolidated public surface and internal data/adapter layer.
---

# Aegis Alpha

Multi-agent, research-only investment skillpack for Codex, Hermes,
OpenClaw, Claude Code, and other agent runtimes that can load local skill
instructions and dispatch scripts.

## Default Public Surface

Prefer these high-level skills when asking an agent to work on investment
research, planning, reporting, or workflow orchestration:

- `information-retrieval`
- `market-data`
- `market-intel`
- `macro-regime`
- `theme-cycle`
- `equity-screening`
- `equity-research`
- `trade-planning`
- `portfolio-ops`
- `advice-lifecycle`
- `pipeline`
- `quality-gate`
- `quant-validation`
- `report-evolution`
- `execution-automation`

## Internal Layer

Low-level providers, parsers, storage shims, and compatibility wrappers are
marked with `metadata.hermes.internal: true`. They remain readable for explicit
maintenance and are used by public facade skills, but they are hidden from the
default agent skill prompt and slash-command surface.

## Financial Safety

This package is research-only by default. Missing critical evidence must fail
closed. Do not interpret missing data as an empty stock pool, empty portfolio, or
valid "no opportunity" signal.

## Data Quality Policy

Public investment outputs must preserve `source`, `as_of`, `freshness`,
`warnings`, `errors`, and `missing_critical_inputs`. Critical facts must be
traceable to a payload field, workspace artifact, provider artifact, URL, or
document path.

Data source changes are not silent fallback. Provider substitutions, parser
fallbacks, stale artifacts, mixed date frequencies, mixed adjustment bases, or
missing unit metadata must be surfaced as warnings or hard errors. If unit,
frequency, trading-calendar, or price-adjustment basis is not present in the
source artifact, downstream skills must either carry the gap forward or fail
closed for decisions that depend on it.

Allowed action levels are `data_only`, `research_only`, `paper_plan_only`,
`analysis_only`, `quality_validation_only`, `report_review_only`, and
`automation_only`. They do not authorize live trading. Any trade, allocation, or
external-send workflow requires explicit human confirmation outside the skill
output.
