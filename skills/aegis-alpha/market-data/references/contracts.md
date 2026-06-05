# Contracts

## Common Envelope

All commands return a data-only envelope:

```json
{
  "package": "market-data",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "artifact_derived",
    "as_of": "<utc-runtime>",
    "policy": "latest prewarm artifact only; missing artifact or missing field fails closed"
  },
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "data_only",
  "source": ["<workspace>/memory/prewarm/nightly-prewarm-*.json"],
  "sources": ["<workspace>/memory/prewarm/nightly-prewarm-*.json"],
  "artifacts": ["<workspace>/memory/prewarm/nightly-prewarm-*.json"],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Data Source

Commands read from the latest nightly prewarm JSON under
`memory/prewarm/nightly-prewarm-*.json`. They do not call live providers at
dispatch time and do not substitute one provider for another silently.

## Commands

| command | status | key source field | failure behavior |
|---|---|---|---|
| `snapshot-full` | implemented | `market_data.hhxg_snapshot` or `hhxg_snapshot` | missing snapshot fails closed |
| `margin-full` | implemented | `market_data.hhxg_margin` or `hhxg_margin` | missing margin data fails closed |
| `calendar-week` | implemented | `market_data.hhxg_calendar` or `hhxg_calendar` | missing calendar fails closed |
| `macro-pmi` | implemented | `akshare_macro_pmi` variants | missing PMI series fails closed |
| `macro-cpi` | implemented | `akshare_macro_cpi` variants | missing CPI series fails closed |
| `macro-ppi` | implemented | `akshare_macro_ppi` variants | missing PPI series fails closed |
| `index-daily` | implemented | `baostock_index_daily` | missing index series fails closed |

## Data Quality Rules

- `result` is the exact artifact segment used by the command; no empty object or
  empty list is returned as success when the segment is missing.
- `source`, `sources`, and `artifacts` identify the artifact path used.
- `freshness.status=unavailable` plus `ok=false` means the caller must stop any
  downstream investment chain that depends on this market data.
- Units, trading calendar, adjustment basis, and frequency are inherited from
  the upstream artifact segment and must be preserved by callers. If an artifact
  omits those fields, downstream research must report the gap in
  `missing_critical_inputs` instead of normalizing by assumption.

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "freshness": {"status": "unavailable"},
  "errors": ["hhxg_snapshot_missing"],
  "missing_critical_inputs": ["hhxg_snapshot_missing"],
  "result": {
    "note": "Required market data artifact or field is missing; do not infer market data from an empty result."
  }
}
```
