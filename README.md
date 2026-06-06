# Aegis Alpha

Aegis Alpha is a public, multi-agent investment skillpack. It keeps one
canonical skill source under `skills/aegis-alpha` and uses lightweight adapters
to install that source into Codex, Hermes, OpenClaw, Claude Code, or another
agent runtime.

The skillpack is research-only. It must not authorize live trading, allocation,
external sending, or execution without explicit human confirmation outside the
skill output.

## Public Surface

The default agent-facing surface is limited to 16 public skills:

- `initialization`
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
- `data/capability-guide.json` explains what the skillpack can do, what
  agent-native tools can and cannot cover, and which API groups unlock each
  capability.
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

## Capability And API Discovery

Do not ask users to guess API names. On first run, the agent should read
`data/capability-guide.json` or inspect `profile.onboarding` from
`scripts/bootstrap_runtime.py`. That onboarding block tells the agent:

- why Aegis Alpha requires a global `market_data` baseline before full initialization.
- what the current agent can usually cover with `agent_native` tools.
- which API groups are recommended for the selected preset.
- which specific tasks require matching APIs, cache, or user-provided evidence.
- what remains unavailable and must fail closed.

API groups are capability-specific:

| API group | Env vars | Unlocks | Required when |
|---|---|---|---|
| `research_search` | `TAVILY_API_KEYS`, `QVERIS_API_KEY` | source discovery and search expansion | current agent lacks usable web/search tools or the user requests API-backed search |
| `document_parse` | `MINERU_API_KEY` | complex PDF/report parsing | agent-native file reading cannot parse the document reliably |
| `market_data` | `TUSHARE_TOKEN`; overseas via `LONGPORT_APP_KEY`, `LONGPORT_APP_SECRET`, `LONGPORT_ACCESS_TOKEN` or an authenticated LongBridge CLI; fallback `FINNHUB_API_KEY` | A-share data via `$tushare`, overseas data via `$longbridge` / LongPort, quotes, historical bars, fundamentals, screening and quant inputs | always required before full initialization |
| `market_intel` | `JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY` | news, macro events, theme catalysts | the task needs provider-backed market intelligence |
| `external_push` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID` | confirmed Feishu delivery | the user explicitly enables confirmed external push |

The full skillpack can install without API keys, but it is not fully
initialized until the global `market_data` baseline is configured. For A-share
and China market data, use the existing `$tushare` convention:
`TUSHARE_TOKEN`. For overseas market data, prefer the existing `$longbridge` /
LongPort convention: either `LONGPORT_APP_KEY`, `LONGPORT_APP_SECRET`, and
`LONGPORT_ACCESS_TOKEN`, or an installed and authenticated LongBridge CLI
session verified by `longbridge auth status`; `FINNHUB_API_KEY` is only a
fallback. Other API groups remain capability-specific accelerators or optional
integrations.

Presets are default operating profiles, not feature gates. All 16 public skills
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

## Runtime Initialization

Initialization is a dedicated public skill-mediated workflow. On first use, if
`runtime-profile.json` is missing, agents should route to
`aegis-alpha-initialization` before any research, portfolio, pipeline, or
automation skill. The initialization skill must ask the user to choose the
intended product experience and capability axes before writing a runtime
profile.

Before asking the user to configure API keys or automation, the agent should
explain:

- the five presets and what workflows they enable.
- the global required `market_data` baseline: `TUSHARE_TOKEN` for A-share data
  plus LongBridge/LongPort credentials for overseas data, with Finnhub only as
  fallback.
- the required initialization axes: data providers, cache/prewarm policy,
  manual-input policy, portfolio source, and heartbeat mode.
- which API groups are recommended or required for specific capabilities.
- what remains usable without APIs, prewarm artifacts, automation, portfolio
  data, or external-push credentials.

Choosing a preset such as `full-institutional` does not by itself authorize API
setup, prewarm execution, recurring wakeups, portfolio ledger creation, or
external push. Those items must be explained and confirmed separately.

The bootstrap script is the deterministic executor for the confirmed choices:

```bash
python3 skills/aegis-alpha/scripts/bootstrap_runtime.py --agent codex --preset quick-research
```

The script refuses to write implicit `quick-research` defaults when `--preset`
is omitted. Use `--accept-defaults` only after the user explicitly confirms the
default initialization after hearing the capability and dependency
explanation. `--dry-run` remains available for inspection without writing
runtime state.

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
