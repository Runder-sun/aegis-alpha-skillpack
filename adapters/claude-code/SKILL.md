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

Do not equate "runtime profile exists" with "initialization complete." For
`prewarm-required`, prewarm must either be run or explicitly deferred/skipped by
the user. For requested heartbeat modes, a real supported automation must be
configured or the user must explicitly choose manual/no heartbeat. Otherwise
describe the state as runtime profile written but initialization incomplete.

`aegis-alpha-initialization` owns the first-run conversation: explaining
capabilities, the global required `market_data` baseline, required setup axes,
optional API groups, prewarm/cache, heartbeat automation, portfolio sources,
and external push before writing runtime state. This aggregate wrapper should
not duplicate or shortcut that conversation.

For initialization or reconfiguration, start by running
`aegis-alpha-initialization` `init-guide`. Guide the user through the current
pending step only, record each explicit configure/skip/defer/manual decision
with `record-choice`, and continue until `init-guide` or `init-status` returns
`initialized=true`.

Portfolio source describes where holdings and trade records come from:
`none` means no known portfolio state, `manual-ledger` means a local
user-maintained ledger, `imported-file` means a CSV/JSON-style position file,
and `read-only-api` means a read-only portfolio API. It never enables order
execution.

Workspace cache/prewarm is not a provider; it is an evidence artifact policy.
Manual input is not a provider; it only controls whether Claude Code may ask the
user for explicit files, holdings, or facts when configured acquisition
channels cannot prove a critical input.

Presets are defaults, not feature gates. After any preset, all public skills
remain available. If the user asks for work outside the selected preset, route
to the relevant public skill, resolve providers, ask for missing inputs when
needed, and fail closed if critical evidence is unavailable.

Before asking the user to configure API keys, read
`../.aegis-alpha-core/data/capability-guide.json` or the generated
`profile.onboarding` block. Explain that `market_data` is globally required:
`TUSHARE_TOKEN` for A-share/China data via `$tushare`, and LongBridge/LongPort
for overseas data via `$longbridge`: either `LONGPORT_APP_KEY`,
`LONGPORT_APP_SECRET`, and `LONGPORT_ACCESS_TOKEN`, or an installed and
authenticated LongBridge CLI session verified by `longbridge auth status`.
`FINNHUB_API_KEY` is only a fallback. Include setup URLs when asking for
credentials, especially LongBridge `https://open.longbridge.com/skill/` and
Tushare `https://tushare.pro`; use `capability-guide.json` `setup_urls` for
other API groups. Then explain which other API groups are recommended or
optional for the selected preset. Do not ask the user to choose raw API names
before explaining the investment capabilities they unlock.

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
right public skill is unclear.

## Provider Selection

Before network-dependent research, resolve the data provider:

```bash
python3 scripts/provider_resolver.py --capability <capability>
```

Use the runtime profile's `data_provider_priority` together with the current
Claude Code capability map. `agent_native` and `skill_api` can be enabled
together and ordered by capability. `workspace_cache` is controlled by
`cache_policy`, and user-supplied evidence is controlled by
`manual_input_policy`. Missing critical evidence must fail closed.

## Automation

When configuring heartbeat or recurring workflows, read
`references/automation-playbook.md` and `data/automation-jobs.json`. Configure
Claude Code-native automation only if the current runtime exposes a native
scheduler. Otherwise use manual mode or an OS scheduler fallback; do not claim
Claude wakeups are configured unless they actually are.

## Safety Rules

- Treat every output as research-only unless it explicitly says otherwise.
- Keep `decision_allowed=false`.
- Missing critical evidence must fail closed.
- Do not infer empty portfolios, empty opportunities, or no risk from missing data.
- Paper trade plans require human confirmation outside the skill.

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
