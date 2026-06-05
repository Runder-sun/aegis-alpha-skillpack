---
name: market-data
description: Consolidated structured market data from nightly prewarm.
metadata: {"openclaw": {"skillKey": "market-data", "packageProfile": "invest-core-v1", "requires": {"bins": ["python3"]}}}
---

# market-data

Consolidated structured market data fed by nightly prewarm snapshots.

## Commands

### snapshot-full
Return the full HHXG market snapshot from prewarm.

Payload: `{}`

### margin-full
Return the HHXG margin data from prewarm.

Payload: `{}`

### calendar-week
Return the HHXG calendar week data from prewarm.

Payload: `{}`

### macro-pmi
Return the macro PMI series from prewarm.

Payload: `{}`

### macro-cpi
Return the macro CPI series from prewarm.

Payload: `{}`

### macro-ppi
Return the macro PPI series from prewarm.

Payload: `{}`

### index-daily
Return the index daily data from prewarm.

Payload: `{}`
