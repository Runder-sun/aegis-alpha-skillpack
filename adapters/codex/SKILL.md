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
asks to initialize/configure Aegis Alpha, route to the public
`aegis-alpha-initialization` skill before any other public skill. Do not run
research, portfolio, pipeline, automation, or provider commands until
initialization has either completed or the user explicitly asks for a dry-run
plan only.

`aegis-alpha-initialization` owns the first-run conversation: explaining
capabilities, the global required `market_data` baseline, required setup axes,
optional API groups, prewarm/cache, heartbeat automation, portfolio sources,
and external push before writing runtime state. This aggregate wrapper should
not duplicate or shortcut that conversation.

Portfolio source describes where holdings and trade records come from:
`none` means no known portfolio state, `manual-ledger` means a local
user-maintained ledger, `imported-file` means a CSV/JSON-style position file,
and `read-only-api` means a read-only portfolio API. It never enables order
execution.

Workspace cache/prewarm is not a provider; it is an evidence artifact policy.
Manual input is not a provider; it only controls whether Codex may ask the user
for explicit files, holdings, or facts when configured acquisition channels
cannot prove a critical input.

Presets are defaults, not feature gates. After any preset, all public skills
remain available. If the user asks for work outside the selected preset, route
to the relevant public skill, resolve providers, ask for missing inputs when
needed, and fail closed if critical evidence is unavailable.

Before asking the user to configure API keys, read
`../.aegis-alpha-core/data/capability-guide.json` or the generated
`profile.onboarding` block. Explain that `market_data` is globally required:
`TUSHARE_TOKEN` for A-share/China data via `$tushare`, and LongBridge/LongPort
credentials for overseas data via `$longbridge` (`LONGPORT_APP_KEY`,
`LONGPORT_APP_SECRET`, `LONGPORT_ACCESS_TOKEN`), with `FINNHUB_API_KEY` only as
fallback. Then explain which other API groups are recommended or optional for
the selected preset. Do not ask the user to choose raw API names before
explaining the investment capabilities they unlock.

## Public Surface

Prefer the individual native public skills when the request clearly matches one area:

- `aegis-alpha-initialization`
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
Codex capability map. `agent_native` and `skill_api` can be enabled together
and ordered by capability. `workspace_cache` is controlled by `cache_policy`,
and user-supplied evidence is controlled by `manual_input_policy`. Missing
critical evidence must fail closed.

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
