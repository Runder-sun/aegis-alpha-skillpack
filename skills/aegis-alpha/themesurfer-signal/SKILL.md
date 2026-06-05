---
name: themesurfer-signal
description: "Market filter signal (MA20) for A-share short-term trading gate."
metadata:
  openclaw:
    skillKey: themesurfer-signal
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
  hermes:
    internal: true
    facade: theme-cycle
---

# themesurfer-signal

Computes a simple MA20-based market filter for A-share short-term trading.

## Commands

### signal
Compute MA20 filter using AkShare or BaoStock (fallback).

Payload:
- `symbol` (string, optional) default: `sh000001` or `sh.000001`
- `lookback` (int, optional) default: 60
- `ma_window` (int, optional) default: 20

Output:
- `status`: `FULL` (close >= MA20) or `LOCKOUT`
- `close`, `ma20`, `source`, `symbol`

## Runtime Notes
### Data Sources
- Uses AkShare as primary, BaoStock as fallback if available.

### Failure & Fallback
- If both sources fail, returns `success=false` with error details and non-zero exit.
