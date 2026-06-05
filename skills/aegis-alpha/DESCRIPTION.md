---
description: AI investment workflow skills with a consolidated public surface and internal data/adapter layer.
---

# Aegis Alpha

Multi-agent, research-only investment skillpack for Codex, Hermes,
OpenClaw, Claude Code, and other agent runtimes that can load local skill
instructions and dispatch scripts.

## Conductor Runtime

The aggregate `aegis-alpha` skill acts as the conductor for first-run bootstrap,
provider selection, and optional automation setup. Use
`scripts/bootstrap_runtime.py` to create the runtime profile,
`scripts/provider_resolver.py` to choose agent-native/API/cache/manual data
providers, and `references/automation-playbook.md` when configuring recurring
work through the current agent's own automation capability.

The runtime profile uses product presets plus independent capability axes. A
user chooses a workflow preset such as `quick-research`, `daily-desk`,
`portfolio-desk`, `report-review`, or `full-institutional`, then chooses data
provider priority, portfolio source, and heartbeat mode separately. Provider
choices are composable: agent-native acquisition, skill APIs, prewarm/cache, and
manual payloads can all be enabled in priority order.

Presets are default operating profiles, not feature gates. All public skills
remain available after any preset. Requests outside the selected preset should
still be routed to the relevant public skill, with provider resolution,
missing-input prompts, and fail-closed safety applied as usual.

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
