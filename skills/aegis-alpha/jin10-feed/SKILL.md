---
name: jin10-feed
description: "Jin10 important news snapshot + daemon monitor (Playwright-based)."
metadata:
  openclaw:
    skillKey: jin10-feed
    packageProfile: invest-core-v1
    requires:
      bins: ["node"]
  hermes:
    internal: true
    facade: market-intel
---

# jin10-feed

Fetches Jin10 important (red-flag) news via a headless browser.
Supports one-shot snapshot for nightly reports and optional daemon mode for realtime monitoring.

## Commands

### jin10-snapshot
One-shot snapshot of important news (returns JSON list).

### jin10-daemon-start
Start daemon monitor (writes JSONL to memory/jin10/news.jsonl).

### jin10-daemon-stop
Stop daemon monitor using PID file.

### jin10-daemon-status
Check daemon status.

## Runtime Notes

### Data Sources
- Jin10 homepage `https://www.jin10.com/` (red-flag important news).

### Outputs
- Snapshot returns `items` and `new_items`.
- Daemon writes JSONL to `memory/jin10/news.jsonl` and keeps `memory/jin10/dedup.json`.

### Env
- `AEGIS_ALPHA_WORKSPACE` (optional).
- `JIN10_URL` (optional; default https://www.jin10.com/).
- `JIN10_INTERVAL_MS` (optional; default 60000).

### Dependencies
- Requires `node` + `playwright`. If Playwright is missing, snapshot returns error.
