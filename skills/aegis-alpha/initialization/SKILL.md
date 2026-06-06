---
name: initialization
description: "Public Aegis Alpha first-run and reconfiguration skill. Use before any other Aegis Alpha skill when runtime-profile.json is missing, when the user asks to initialize/configure/reconfigure the skillpack, or when the user needs to understand capabilities, required setup choices, optional API groups, prewarm/cache, heartbeat automation, portfolio source, or external push before writing runtime state."
metadata:
  openclaw:
    skillKey: initialization
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
---

# initialization

Use this skill as the default first-run entry for Aegis Alpha. If the runtime
profile is missing, do not route investment research, portfolio, automation, or
pipeline work directly to other Aegis Alpha public skills. Initialize or
reconfigure first.

Initialization is a skill-mediated conversation. The bootstrap script only
writes a confirmed runtime profile; it does not replace user education or
choice.

Initialization must behave like a guided wizard, not a one-shot script. Start
or resume by running `init-guide`. Handle only the current pending step, explain
the capability and tradeoffs, ask the user for the exact choice, then record
that choice with `record-choice` before moving to the next step. Continue until
`init-guide.result.initialized=true`. If the user chooses "defer", record it,
but do not call initialization complete; only an explicit configure/skip/manual
terminal choice can close a step.

On first use, or whenever the user asks "how do I use this skillpack?", present
the First-Run User Brief from `init-guide.result.user_onboarding` before asking
for credentials or writing state. The brief must tell the user what the
skillpack can do, which configuration is required, which configuration is
optional, where provider setup happens, and what is lost when a choice is
skipped. Do not compress this into "please provide keys"; users must understand
the product surface before choosing setup.

Do not tell the user "initialization is complete" merely because
`runtime-profile.json` exists. Full initialization is complete only after the
runtime profile exists, the global `market_data` baseline is ready, and every
operational choice required by the selected preset has either been explicitly
configured or explicitly declined by the user. For `prewarm-required`, an
initial prewarm/cache artifact must exist or the user must explicitly choose to
defer/skip initial cache seeding. Recurring prewarm schedules are not configured
in the prewarm step; they are configured in the heartbeat/automation step. For
`market-heartbeat`, `daily-prewarm`, or `full` heartbeat, the agent must
configure a real supported automation or the user must explicitly choose
manual/no heartbeat. Otherwise report the state as "runtime profile written,
initialization incomplete" and list the pending choices.

## Required Conversation

Before writing or completing runtime state, explain what the skillpack can do
and what each setup choice means. Then ask the user what to configure.

Use `init-guide.result.user_onboarding.configuration_matrix` as the canonical
user-facing setup table. It must be reflected in the conversation before the
first credential or automation request. Use
`init-guide.result.user_onboarding.step_prompt_templates` for the current step
so the agent asks one concrete question at a time with the required context.

1. Explain product experiences:

- `quick-research`: one-off research and evidence collection.
- `daily-desk`: morning/nightly market desk workflow.
- `portfolio-desk`: holdings, trade ledger, risk review, and advice tracking.
- `report-review`: evidence capture, report review, and outcome alignment.
- `full-institutional`: full research, market, portfolio, validation, and reporting loop.

2. Explain required initialization axes:

- `data-providers`: acquisition priority, usually `agent_native,skill_api` or
  `skill_api,agent_native`. Agent-native tools and configured APIs are
  compatible.
- `cache-policy`: `none`, `read-if-fresh`, `cache-first`,
  `refresh-if-stale`, or `prewarm-required`.
- `manual-input`: `ask-when-missing` or `disabled`.
- `portfolio-source`: `none`, `manual-ledger`, `imported-file`, or
  `read-only-api`.
- `heartbeat`: `none`, `manual`, `daily-prewarm`, `market-heartbeat`, or
  `full`.

3. Explain the global required API group before optional capability unlocks:

- `market_data` is globally required before Aegis Alpha is considered fully
  initialized. For A-share and China market data, follow the existing
  `$tushare` convention and configure `TUSHARE_TOKEN`. For overseas market
  data, prefer the existing `$longbridge` / LongPort convention and configure
  `LONGPORT_APP_KEY`, `LONGPORT_APP_SECRET`, and `LONGPORT_ACCESS_TOKEN`, or
  install and authenticate the LongBridge CLI so `longbridge auth status`
  reports a valid session. `FINNHUB_API_KEY` is only a fallback when
  LongBridge/LongPort is unavailable.
  Without this baseline, stay in setup guidance or fail closed.

When asking the user to configure `market_data`, include provider setup URLs:
Tushare `https://tushare.pro`, LongBridge `https://open.longbridge.com/skill/`,
and Finnhub fallback `https://finnhub.io`.

4. Explain optional capability unlocks before asking for other API keys:

- `research_search` (`TAVILY_API_KEYS`, `QVERIS_API_KEY`): source discovery
  and search expansion. Optional when the agent has native web/search tools.
- `document_parse` (`MINERU_API_KEY`): large PDF/report parsing. Optional
  unless native file reading is insufficient.
- `market_intel` (`JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY`):
  provider-backed market news, macro events, and theme catalysts. Recommended
  for desk workflows.
- `external_push` (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`,
  `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID`): confirmed Feishu delivery. Required
  only if the user explicitly wants external push.

For every optional API group, include the setup URL or provider portal before
asking for a key. Use `capability-guide.json` `setup_urls` when present.

5. Explain operational choices separately from the preset:

- The prewarm step seeds an initial auditable cache artifact for
  `prewarm-required`; choosing a preset does not mean this artifact exists.
  Prewarm is not a separate public skill that the user configures directly; it
  is an execution-automation command invoked by the initialization wizard or by
  later scheduled workflows after installation and provider setup.
- Heartbeat/recurring workflows schedule future prewarm and heartbeat jobs, and
  require native automation support or an OS scheduler fallback; choosing
  `market-heartbeat` does not configure wakeups.
- Portfolio setup requires a source before portfolio review can rely on
  holdings.
- External push is disabled unless the user explicitly enables it and provides
  credentials.

6. Ask for explicit choices. If the user chooses `full-institutional`, do not
assume they approved APIs, prewarm execution, recurring wakeups, portfolio
ledger creation, or external push. Ask those items separately.

7. Continue the wizard until all steps are closed:

- Required `market_data` must be configured.
- Optional API groups (`market_intel`, `research_search`, `document_parse`,
  `external_push`) must be configured, explicitly skipped, or explicitly
  disabled. If deferred, initialization remains incomplete.
- Initial prewarm/cache seeding must be run, or explicitly skipped/deferred. If
  deferred, initialization remains incomplete. Recurring prewarm belongs to the
  heartbeat/automation step.
- Heartbeat must be configured as a real supported automation, or explicitly
  set to `manual`/`none`/`skip`. If deferred, initialization remains incomplete.
- Portfolio source must be confirmed as `none`, `manual-ledger`,
  `imported-file`, or `read-only-api`.
- Only say initialization is complete when `init-guide` or `init-status`
  returns `initialized=true`.

## Mandatory Step Confirmation

The `heartbeat` and `portfolio` steps are high-risk because they can create
recurring work or cause portfolio analysis to rely on missing state. Do not
record either step as complete unless the user has explicitly confirmed the
specific choice after hearing the options and consequences.

## First-Run UX Rules

- First show capabilities and setup impact, then ask for the preset and setup
  choices.
- Do not ask for every credential in one message. Ask only for the current
  pending step from `init-guide`.
- For every API group, say whether it is required or optional, what it unlocks,
  setup URL, completion condition, and what happens if skipped.
- `market_data` is globally required. It is not an optional enhancement.
- `prewarm` is an installation/runtime health step that seeds an auditable
  cache artifact. It is not a public user skill and does not create recurring
  automation.
- `heartbeat` is the recurring automation choice. It must name the exact jobs
  that will be created before asking for approval.
- `portfolio` must ask whether the user has current holdings. Do not infer an
  empty portfolio.
- The final review must summarize configured, skipped, deferred, and fail-closed
  items before saying initialization is complete.

For `heartbeat`, explain before asking:

- `none`: no recurring work.
- `manual`: user asks the agent to run workflows on demand.
- `daily-prewarm`: create recurring prewarm/cache jobs only.
- `market-heartbeat`: create recurring prewarm plus market heartbeat/review jobs.
- `full`: create morning, midday, heartbeat, nightly, and weekly review jobs.

Before creating any automation, tell the user exactly which jobs would be
created, what each job does, its schedule/frequency, where it will run, and that
all outputs remain research-only with no live trading or external sends. Then
ask whether to create those automations. If the current runtime cannot create
the exact requested schedule, explain the supported approximation and ask again.

When recording `heartbeat`, include `user_confirmed=true` and metadata:

- `capability_explained=true`
- `options_explained=true`
- `selected_mode`
- for active automation modes, `automation_plan` and
  `user_approved_automation_create=true`
- for manual/none/skip, `automation_plan=[]`

For `portfolio`, explain before asking:

- `none`: no portfolio source; portfolio analysis is unavailable.
- `manual-ledger`: user will maintain a local ledger or provide positions in chat.
- `imported-file`: user provides a CSV/JSON/XLSX holdings file.
- `read-only-api`: user configures a read-only portfolio source.

Always ask whether the user has current holdings. If holdings are not provided,
do not infer an empty portfolio. The user may explicitly choose to continue with
`manual-ledger` and no holdings yet, but metadata must mark
`holdings_state=not_provided_fail_closed`; future portfolio analysis must fail
closed until holdings are recorded or imported.

When recording `portfolio`, include `user_confirmed=true` and metadata:

- `options_explained=true`
- `holdings_question_asked=true`
- `holdings_state` as one of `provided`, `imported`, `read_only_api`,
  `none_confirmed`, or `not_provided_fail_closed`
- `fail_closed_without_holdings=true` unless holdings were actually provided,
  imported, or connected through read-only API.

## Commands

### init-status
Inspect whether a runtime profile exists and summarize current state.
Treat `result.initialized` as full initialization status. Use
`result.runtime_profile_exists` when you only mean that the runtime profile has
been written.

### init-guide
Return the step-by-step initialization wizard state. Use this at the start of
every initialization or reconfiguration turn. Ask the user only about
`result.current_step`, not every remaining step at once.

### init-plan
Return a setup explanation bundle for a preset without writing state. Use this
before asking for API keys or automation choices.

### record-choice
Record a user-confirmed initialization choice. Use it for optional API groups,
prewarm, heartbeat, portfolio source, and external push decisions. Do not
invent a choice on behalf of the user.

For `heartbeat` and `portfolio`, `record-choice` must include
`user_confirmed=true` and the mandatory metadata described above. The dispatcher
must reject missing confirmation metadata rather than trusting agent intent.

### bootstrap-profile
Write the confirmed runtime profile. Use only after the user has chosen the
preset and required axes, or explicitly accepted defaults after hearing the
capability and dependency explanation.

Example:

```bash
python3 scripts/dispatch.py --command bootstrap-profile --payload '{"user_confirmed":true,"agent":"codex","preset":"quick-research","data_providers":"agent_native,skill_api","cache_policy":"read-if-fresh","manual_input":"ask-when-missing","portfolio_source":"none","heartbeat":"none"}'
```

## Safety

- Initialization never enables live trading or executable advice.
- `decision_allowed` remains `false`.
- Do not treat a preset as authorization for optional API setup, prewarm runs,
  wakeups, portfolio ledger creation, or external push.
- Do not write a full runtime profile until the global `market_data` baseline
  is configured.
- Missing critical setup choices must fail closed by asking the user.
