# Aegis Alpha

Aegis Alpha is a public, multi-agent investment skillpack. It keeps one
canonical skill source under `skills/aegis-alpha` and uses lightweight adapters
to install that source into Codex, Hermes, OpenClaw, Claude Code, or another
agent runtime.

The skillpack is research-only. It must not authorize live trading, allocation,
external sending, or execution without explicit human confirmation outside the
skill output.

## Public Surface

The default agent-facing surface is limited to 15 public skills:

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

Low-level providers and compatibility shims remain internal.

## Conductor Runtime

The aggregate `aegis-alpha` skill is the conductor. It owns first-run bootstrap,
provider selection, and automation guidance:

- `scripts/bootstrap_runtime.py` creates `runtime-profile.json` under
  `AEGIS_ALPHA_WORKSPACE`.
- `scripts/provider_resolver.py` selects between `agent_native`, `skill_api`,
  and `workspace_cache` evidence paths by runtime profile and capability.
- `references/automation-playbook.md` tells the current agent how to configure
  recurring work with its own automation capability when available.
- `data/automation-jobs.json` defines standard morning, heartbeat, nightly, and
  weekly workflow jobs.

First-run configuration is split into orthogonal axes:

- product preset: `quick-research`, `daily-desk`, `portfolio-desk`,
  `report-review`, or `full-institutional`.
- data provider priority: any ordered combination of `agent_native` and
  `skill_api`.
- cache policy: `none`, `read-if-fresh`, `cache-first`, `refresh-if-stale`, or
  `prewarm-required`.
- manual input policy: `ask-when-missing` or `disabled`.
- portfolio source: `none`, `manual-ledger`, `imported-file`, or
  `read-only-api`.
- heartbeat mode: `none`, `manual`, `daily-prewarm`, `market-heartbeat`, or
  `full`.

Portfolio source only describes where holdings and trade records come from:
`none` means no known portfolio state, `manual-ledger` means a local
user-maintained ledger, `imported-file` means a CSV/JSON-style position file,
and `read-only-api` means a read-only portfolio API. It never enables order
execution.

Agent-native acquisition and skill APIs are compatible. For example, a Codex
installation can use `full-institutional` with `skill_api,agent_native`
provider priority. The skill API can supply structured quotes, fundamentals,
time series, parsing, or configured feeds while agent-native tools verify
sources, search fresh news, inspect filings/pages, and fill gaps the API cannot
cover.

Workspace cache/prewarm is not a provider. It is an evidence artifact policy:
use it to reuse or prepare auditable data before a workflow. Manual user input
is also not a provider; it only controls whether the conductor may ask the user
for explicit files, holdings, or facts when configured channels cannot prove a
critical input.

Presets are default operating profiles, not feature gates. All 15 public skills
remain available after any preset is selected. If a user asks for work outside
the selected preset, the conductor should route to the relevant public skill,
resolve providers from the runtime profile, ask for missing inputs when needed,
and fail closed when critical evidence is unavailable.

Heartbeat configuration is capability-gated. The skill does not assume it can
programmatically wake Codex or Claude Code unless the current agent exposes a
native automation mechanism.

## Install

Codex and Claude Code install a native public skillset, not a second full copy
per skill:

- `.aegis-alpha-core` contains the shared canonical source.
- `aegis-alpha` is the aggregate cross-skill wrapper.
- `aegis-alpha-<public-skill>` exposes each public skill as a native skill
  directory with its own `SKILL.md` and bundled `scripts/`, `data/`, and
  `references/` resources.

This keeps one maintained skillpack core while preserving direct invocation of
individual public skills such as `aegis-alpha-market-data` or
`aegis-alpha-equity-research`.

By default, public skill resources are symlinked to `.aegis-alpha-core` so the
agent sees a native layout without duplicating the package. Use
`--link-mode copy` only when symlinks are unavailable.

Install Codex native skills into `$CODEX_HOME/skills` or `~/.codex/skills`:

```bash
python3 adapters/codex/install.py
```

Install Hermes package:

```bash
python3 adapters/hermes/install.py
```

Install OpenClaw package:

```bash
python3 adapters/openclaw/install.py
```

Install Claude Code native skills into the current project's
`.claude/skills` directory:

```bash
python3 adapters/claude-code/install.py
```

For Codex and Claude Code, `--target <path>` points to a skills root directory.
For Hermes and OpenClaw, `--target <path>` points to the package directory.
Existing Aegis Alpha targets are not overwritten unless `--force` is provided.

## Validate

Run the full local acceptance set:

```bash
python3 skills/aegis-alpha/scripts/bootstrap_runtime.py --dry-run
python3 skills/aegis-alpha/scripts/provider_resolver.py --capability research_search --profile /dev/null
python3 tools/audit_capabilities.py --output-dir audit
python3 tools/check_public_contracts.py --output-dir audit
python3 tools/check_pipeline_integrity.py --output-dir audit
python3 tools/smoke_portfolio_position_research.py --output-dir audit
python3 tools/smoke_investment_closed_loop.py --output-dir audit
python3 tools/check_final_acceptance.py --audit-dir audit
```

## Repository Hygiene

This repository is public. Do not commit `.env`, API keys, local workspace
state, prewarm artifacts, positions, ledgers, reports, runtime memory, or any
other personal/account data.
