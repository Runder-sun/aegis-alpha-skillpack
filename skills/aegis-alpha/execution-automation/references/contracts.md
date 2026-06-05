# execution-automation Contracts

Cross-package calls are only allowed through command-level data contracts. Do
not import internal implementation files from another package directly.

## Common Envelope

Every command returns:

```json
{
  "package": "execution-automation",
  "command": "prewarm-status",
  "ok": false,
  "as_of": "2026-06-04T00:00:00Z",
  "freshness": {"status": "unavailable"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "automation_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": ["prewarm_artifact_missing"],
  "missing_critical_inputs": ["prewarm_artifact_missing"],
  "result": {
    "note": "Execution automation could not prove required evidence or explicit send authorization."
  }
}
```

`ok=true` means the automation check or operation completed. It never means an
investment action is approved.

## Command Table

| Command | Purpose | Critical inputs | Failure behavior |
|---|---|---|---|
| `nightly-prewarm` | Run shared prewarm collector | `scripts/nightly_prewarm.py` and workspace skills | Fails closed if collector fails or no artifact is written |
| `morning-prewarm` | Morning pipeline prewarm wrapper | same as nightly prewarm | Fails closed if artifact missing or invalid |
| `midday-prewarm` | Market-review prewarm wrapper | same as nightly prewarm | Fails closed if artifact missing or invalid |
| `evening-prewarm` | Evening workflow prewarm wrapper | same as nightly prewarm | Critical gaps are explicit |
| `weekly-prewarm` | Weekly workflow prewarm wrapper | same as nightly prewarm | Critical gaps are explicit |
| `prewarm-status` | Validate latest prewarm artifact | `memory/prewarm/nightly-prewarm-*.json` | Missing, corrupt, or stale artifact fails closed |
| `market-heartbeat` | Heartbeat alerts from latest prewarm | non-stale prewarm snapshot | Missing/stale snapshot fails closed |
| `realtime-market-scan` | Structured market alert scan | non-stale prewarm snapshot | Missing/stale snapshot fails closed |
| `realtime-alerts-summary` | Compact alert summary | non-stale prewarm snapshot | Same gate as realtime scan |
| `realtime-monitor-control` | Desired monitor state marker | `action=start|stop|status` | Invalid action or corrupt state fails closed |
| `nightly-push` | External push for nightly report | report text/path plus `confirm_send=true` | Missing text/path, missing confirmation, missing credentials fail closed |
| `morning-push` | External push for morning report | same as nightly push | Same |
| `intraday-push` | External push for intraday/review report | same as nightly push | Same |
| `weekly-push` | External push for weekly report | same as nightly push | Same |

## Allowed Fallbacks

Allowed:

- `dry_run=true` may return a planned action without running collectors or
  sending a message.
- Prewarm commands may succeed with non-critical gaps, but must list them in
  `missing_critical_inputs`.

Not allowed:

- Missing market data becomes `HEARTBEAT_OK`.
- Missing report path becomes a successful external push.
- Missing Feishu config becomes silent success.
- Monitor control starts an autonomous order executor.
- Any command sets `decision_allowed=true`.

## Minimal Examples

Dry-run prewarm:

```json
{"dry_run": true}
```

Check prewarm freshness:

```json
{"max_age_minutes": 720}
```

Dry-run report push:

```json
{"text": "report body", "report_title": "nightly", "dry_run": true}
```

Confirmed external send:

```json
{"report_path": "memory/reports/nightly-report.md", "confirm_send": true}
```
