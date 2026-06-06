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
asks to initialize/configure Aegis Alpha, treat initialization as a
skill-mediated workflow, not as a silent script default. The script is only the
executor that writes the confirmed runtime profile.

Do not run the bootstrap command until the user has enough context to choose.
If the user only says "initialize" or "configure Aegis Alpha", first explain
the available capabilities, what each preset is for, which configuration items
are required for initialization, which API groups or automations are optional,
and what remains unavailable without them. Then ask the user what to configure.

Initialization conversation order:

1. Explain the five product experiences:

- `quick-research`: one-off research and evidence collection.
- `daily-desk`: morning/nightly market desk workflow.
- `portfolio-desk`: holdings, trade ledger, risk review, and advice tracking.
- `report-review`: evidence capture, report review, and outcome alignment.
- `full-institutional`: the full research, market, portfolio, validation, and reporting loop.

2. Explain the required initialization choices:

- `data-providers`: comma-separated priority such as
  `agent_native,skill_api`. Agent-native web and skill APIs are compatible;
  they are not mutually exclusive.
- `cache-policy`: `none`, `read-if-fresh`, `cache-first`,
  `refresh-if-stale`, or `prewarm-required`.
- `manual-input`: `ask-when-missing` or `disabled`.
- `portfolio-source`: `none`, `manual-ledger`, `imported-file`, or
  `read-only-api`.
- `heartbeat`: `none`, `manual`, `daily-prewarm`, `market-heartbeat`, or
  `full`.

3. Explain optional capability unlocks before asking for API keys:

- `research_search` (`TAVILY_API_KEYS`, `QVERIS_API_KEY`): source discovery and search expansion. Optional when Codex can use native web/search tools.
- `document_parse` (`MINERU_API_KEY`): large PDF/report parsing. Optional unless native file reading is insufficient.
- `market_data` (`TUSHARE_TOKEN`, `FINNHUB_API_KEY`): quotes, bars, fundamentals, screening data, and quant inputs. Required for structured screening or quant validation unless the user provides a dataset/cache.
- `market_intel` (`JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY`): provider-backed market news, macro events, and theme catalysts. Recommended for desk workflows.
- `external_push` (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID`): confirmed Feishu delivery. Required only if the user explicitly wants external push.

4. Explain operational options separately from the preset:

- Prewarm/cache jobs prepare auditable evidence artifacts; choosing a preset
  does not mean prewarm has already run.
- Heartbeat/recurring workflows require Codex-native automation support or an
  OS scheduler fallback; choosing `market-heartbeat` does not configure actual
  wakeups by itself.
- Portfolio setup requires a source (`manual-ledger`, `imported-file`, or
  `read-only-api`) before portfolio review can rely on holdings.
- External push is disabled unless the user explicitly enables it and provides
  credentials.

5. Ask the user to choose the preset and required axes. If they choose a preset
such as `full-institutional`, do not assume they also approved APIs, prewarm
runs, heartbeat automation, portfolio ledger creation, or external push. Ask
about those items explicitly.

After the user confirms the product experience and capability axes, run:

```bash
python3 scripts/bootstrap_runtime.py --agent codex --preset <preset> --data-providers <provider_priority> --cache-policy <cache_policy> --manual-input <manual_input_policy> --portfolio-source <portfolio_source> --heartbeat <heartbeat_mode>
```

Use `--accept-defaults` only when the user explicitly confirms the default
initialization after hearing the capability/required/optional explanation.
Never use it as a convenience fallback.

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
`profile.onboarding` block. Explain what the package can do without APIs, what
Codex can cover with agent-native tools, which API groups are recommended for
the selected preset, and which specific tasks require APIs, cache, or
user-provided evidence. Do not ask the user to choose raw API names before
explaining the investment capabilities they unlock.

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
