---
name: aegis-alpha
description: Use for research-only investment workflows that require market data provenance, macro regime analysis, theme rotation, equity screening, equity research, paper trade planning, portfolio/risk review, advice lifecycle tracking, pipeline orchestration, quality gates, quant validation, report evolution, and strict fail-closed financial safety. Never use for live trading or executable advice.
metadata:
  short-description: Research-only investment workflow skillpack
---

# Aegis Alpha

This conductor skill exposes the shared canonical skillpack installed at
`../.aegis-alpha-core` and coordinates first-run bootstrap, provider selection,
automation configuration, and cross-skill investment workflows.

## First Run

If `AEGIS_ALPHA_WORKSPACE/config/runtime-profile.json` is missing or the user
asks to initialize/configure Aegis Alpha, run:

```bash
python3 scripts/bootstrap_runtime.py --agent codex --preset <preset> --data-providers <provider_priority> --portfolio-source <portfolio_source> --heartbeat <heartbeat_mode>
```

Ask the user for the intended product experience first:

- `quick-research`: one-off research and evidence collection.
- `daily-desk`: morning/nightly market desk workflow.
- `portfolio-desk`: holdings, trade ledger, risk review, and advice tracking.
- `report-review`: evidence capture, report review, and outcome alignment.
- `full-institutional`: the full research, market, portfolio, validation, and reporting loop.

Then configure the orthogonal capability axes:

- `data-providers`: comma-separated priority such as
  `agent_native,skill_api,cache_or_prewarm,manual_payload`. Agent-native web
  and skill APIs are compatible; they are not mutually exclusive.
- `portfolio-source`: `none`, `manual-ledger`, `imported-file`, or
  `read-only-api`.
- `heartbeat`: `none`, `manual`, `daily-prewarm`, `market-heartbeat`, or
  `full`.

Portfolio source describes where holdings and trade records come from:
`none` means no known portfolio state, `manual-ledger` means a local
user-maintained ledger, `imported-file` means a CSV/JSON-style position file,
and `read-only-api` means a read-only portfolio API. It never enables order
execution.

Presets are defaults, not feature gates. After any preset, all public skills
remain available. If the user asks for work outside the selected preset, route
to the relevant public skill, resolve providers, ask for missing inputs when
needed, and fail closed if critical evidence is unavailable.

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

## Provider Selection

Before network-dependent research, resolve the data provider:

```bash
python3 scripts/provider_resolver.py --capability <capability>
```

Use the runtime profile's `data_provider_priority` together with the current
Codex capability map. Agent-native web/search, skill APIs, prewarm/cache, and
manual payloads can be combined in priority order. Missing critical evidence
must fail closed.

## Automation

When configuring heartbeat or recurring workflows, read
`references/automation-playbook.md` and `data/automation-jobs.json`. Configure
Codex-native automation only if the current Codex runtime exposes automation
tools. Otherwise use manual mode or an OS scheduler fallback; do not claim that
Codex wakeups are configured unless they actually are.

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
