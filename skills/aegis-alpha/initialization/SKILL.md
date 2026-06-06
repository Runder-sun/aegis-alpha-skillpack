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

## Required Conversation

Before writing runtime state, explain what the skillpack can do and what each
setup choice means. Then ask the user what to configure.

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

3. Explain optional capability unlocks before asking for API keys:

- `research_search` (`TAVILY_API_KEYS`, `QVERIS_API_KEY`): source discovery
  and search expansion. Optional when the agent has native web/search tools.
- `document_parse` (`MINERU_API_KEY`): large PDF/report parsing. Optional
  unless native file reading is insufficient.
- `market_data` (`TUSHARE_TOKEN`, `FINNHUB_API_KEY`): quotes, bars,
  fundamentals, screening data, and quant inputs. Required for structured
  screening or quant validation unless the user provides a dataset/cache.
- `market_intel` (`JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY`):
  provider-backed market news, macro events, and theme catalysts. Recommended
  for desk workflows.
- `external_push` (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`,
  `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID`): confirmed Feishu delivery. Required
  only if the user explicitly wants external push.

4. Explain operational choices separately from the preset:

- Prewarm/cache jobs prepare auditable evidence artifacts; choosing a preset
  does not mean prewarm has run.
- Heartbeat/recurring workflows require native automation support or an OS
  scheduler fallback; choosing `market-heartbeat` does not configure wakeups.
- Portfolio setup requires a source before portfolio review can rely on
  holdings.
- External push is disabled unless the user explicitly enables it and provides
  credentials.

5. Ask for explicit choices. If the user chooses `full-institutional`, do not
assume they approved APIs, prewarm execution, recurring wakeups, portfolio
ledger creation, or external push. Ask those items separately.

## Commands

### init-status
Inspect whether a runtime profile exists and summarize current state.

### init-plan
Return a setup explanation bundle for a preset without writing state. Use this
before asking for API keys or automation choices.

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
- Missing critical setup choices must fail closed by asking the user.
