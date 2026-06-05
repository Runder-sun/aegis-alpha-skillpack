---
name: execution-automation
description: "Fail-closed investment workflow automation for data prewarm, market heartbeat/alerts, monitor state markers, and explicit-confirmation report pushes."
metadata: {"openclaw": {"skillKey": "execution-automation", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# execution-automation

Use this skill when the agent needs to prepare evidence artifacts for pipelines,
inspect whether prewarm data is usable, summarize market heartbeat alerts from
existing evidence, record a monitor desired-state marker, or push generated
reports after explicit human confirmation.

This skill does not execute trades and does not approve investment decisions.
All commands return `decision_allowed=false`, `requires_human_confirmation=true`,
and `max_action_level=automation_only`.

## Safety Rules

- Missing or invalid prewarm artifacts fail closed.
- Missing report text/path fails closed for push commands.
- External sends require `confirm_send=true`; use `dry_run=true` for checks.
- Realtime monitor control records a state marker only. It does not start an
  autonomous trading loop or order executor.
- Heartbeat and realtime scan read the latest prewarm artifact only; stale data
  fails closed rather than becoming a neutral signal.

## Prewarm Commands

`nightly-prewarm`, `morning-prewarm`, `midday-prewarm`, `evening-prewarm`, and
`weekly-prewarm` all call the shared deterministic collector:

`scripts/nightly_prewarm.py`

The command writes `memory/prewarm/nightly-prewarm-*.json` and records a marker
under `memory/automation/<command>-last.json`.

Payload:

- `dry_run`: when true, returns the planned script without running collectors.
- `timeout_sec`: optional collector timeout.

Critical gaps such as missing market snapshot, index data, macro PMI, or market
news are returned in `missing_critical_inputs`.

## Status And Monitoring

### `prewarm-status`

Reads the latest prewarm artifact and checks:

- artifact path
- age
- staleness against `max_age_minutes`
- critical gaps
- top-level keys

Missing, stale, or corrupt artifacts fail closed.

### `market-heartbeat` / `realtime-market-scan`

Reads the latest validated prewarm snapshot and returns:

- `heartbeat_status`
- `alerts`
- market metrics
- top themes

It does not fetch new data and does not produce executable trading actions.

### `realtime-alerts-summary`

Returns a compact summary of current heartbeat alerts.

### `realtime-monitor-control`

Payload `action` is one of `start`, `stop`, or `status`. The command only writes
or reads `memory/automation/realtime-monitor-state.json`.

## Push Commands

`nightly-push`, `morning-push`, `intraday-push`, and `weekly-push` accept:

- `report_path`: must resolve under `memory/reports`
- `text`: inline report text
- `report_title`
- `dry_run`
- `confirm_send`

External Feishu sending requires configured environment variables and
`confirm_send=true`. Missing credentials, missing text, invalid paths, or absent
confirmation fail closed.

## Output Contract

See `references/contracts.md`. All commands return the common automation
envelope with `as_of`, `freshness`, `source`, `artifacts`, `warnings`, `errors`,
`missing_critical_inputs`, and `result`.
