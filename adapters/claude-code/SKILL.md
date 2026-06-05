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
python3 scripts/bootstrap_runtime.py --agent claude-code --mode <mode> --data-source <source> --heartbeat <mode>
```

Ask the user which runtime mode they want before selecting arguments:

- `offline-research`
- `agent-native`
- `api-assisted`
- `manual-portfolio`
- `report-review`
- `full-institutional`

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
right public skill is unclear.

## Provider Selection

Before network-dependent research, resolve the data provider:

```bash
python3 scripts/provider_resolver.py --capability <capability>
```

Use agent-native web/search when the runtime profile and current Claude Code
tools allow it. Use skill APIs or cache/prewarm only when configured. Missing
critical evidence must fail closed.

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
