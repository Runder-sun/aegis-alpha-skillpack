# Aegis Alpha Automation Playbook

Use this file only when the user asks to initialize, configure, enable, disable,
or inspect Aegis Alpha automation or heartbeat behavior.

## Goal

Let the current agent configure Aegis Alpha recurring work with its own native
automation ability when available. Do not assume a script can control every
agent runtime.

## User Choices

Ask for a heartbeat mode before enabling automation:

- `none`: no recurring work.
- `manual`: user asks the agent to run workflows on demand.
- `daily-prewarm`: schedule morning/nightly prewarm jobs only.
- `market-heartbeat`: schedule prewarm plus market heartbeat jobs.
- `full`: schedule morning, midday, heartbeat, nightly, and weekly review jobs.

External sends remain disabled unless the user explicitly chooses
`external-push=confirm-only`. Live trading is never enabled.

## Profile Context

Automation is independent from the product preset and data provider priority.
For example, `full-institutional` can still run in `manual` heartbeat mode, and
`quick-research` can be paired with `daily-prewarm` if the user wants scheduled
data preparation only. Do not make `agent_native`, `skill_api`, or
`full-institutional` mutually exclusive choices.

## Job Definitions

Read `data/automation-jobs.json` for job names, default schedules, prompts, and
workflow steps. Configure only jobs whose `heartbeat_mode` is compatible with
the user's selected mode.

## Agent-Native Configuration

The current agent should configure automation through its own tools when those
tools exist.

- Codex: if automation tools are available, use them to create recurring tasks
  whose prompts invoke the Aegis Alpha conductor. If unavailable, offer OS
  scheduler or manual mode.
- Claude Code: if the environment exposes native scheduling, use it. Otherwise
  create project-local commands and tell the user that recurring agent wakeups
  are not available in this runtime.
- Hermes: if Hermes cron/scheduler is available, register scheduled agent turns
  that call the conductor. Otherwise use OS scheduler or manual mode.
- OpenClaw: if OpenClaw gateway/scheduler is available, register the configured
  jobs there. Otherwise use OS scheduler or manual mode.

## Fallback

OS scheduler fallback may run deterministic commands such as prewarm and
heartbeat scripts, but it must not claim to wake Codex or Claude Code unless the
agent has a native recurring task mechanism.

## Required Profile Update

After configuration, update `config/runtime-profile.json` under
`AEGIS_ALPHA_WORKSPACE` with:

- `automation.heartbeat_mode`
- `automation.configured_by_agent`
- selected scheduler/provider name
- enabled job names

If automation cannot be configured, record manual mode and explain why.
