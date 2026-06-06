# initialization Contracts

## Common Envelope

All commands return an initialization envelope:

```json
{
  "package": "initialization",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "configuration_only",
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

| command | purpose | writes state |
|---|---|---|
| `init-status` | Inspect current runtime profile state | no |
| `init-plan` | Explain preset, required axes, optional API groups, and operational dependencies | no |
| `bootstrap-profile` | Write the confirmed runtime profile | yes |

## Safety Rules

- `bootstrap-profile` must require `user_confirmed=true`.
- `bootstrap-profile` must fail closed when the global `market_data` baseline
  is missing: `TUSHARE_TOKEN` for A-share/China data plus LongBridge/LongPort
  credentials (`LONGPORT_APP_KEY`, `LONGPORT_APP_SECRET`,
  `LONGPORT_ACCESS_TOKEN`) for overseas data, or `FINNHUB_API_KEY` as fallback.
- A preset choice does not imply approval for API credentials, prewarm
  execution, recurring wakeups, portfolio ledger creation, or external push.
- Missing required axis values must return `ok=false`.
- Runtime configuration is research-only and never authorizes live trading.
