---
name: market-intel
description: "Collect market intelligence from news, events, policy, research reports, sentiment, hot-money context, and black-swan risk with fail-closed investment safety."
metadata: {"openclaw": {"skillKey": "market-intel", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# market-intel

Use this package when the task needs market intelligence or event context before
macro, theme, equity, or paper-only trade planning.

## Runtime

Run commands through `scripts/dispatch.py` with `--command <name>` and optional
JSON `--payload`. The dispatcher reads `AEGIS_ALPHA_WORKSPACE` when set;
otherwise it uses `~/.aegis-alpha/workspace`.

## Public Commands

- `daily-news-scan`: A-share, China macro, and global market news.
- `global-event-scan`: global macro/event items.
- `event-calendar-scan`: A-share calendar and economic calendar.
- `policy-analysis`: policy feed summary.
- `research-reports`: focus news, macro news, and research report summary.
- `market-sentiment-index`: sentiment and market breadth indicators.
- `black-swan-monitor`: extreme risk monitor.
- `forum-sentiment`: sector-level sentiment proxy from strong/weak sectors.
- `kol-tracker`: hot-money and seat context from snapshot data.
- `global-sentiment-scan`: optional global macro sentiment scan.

## Removed From Public Surface

- `event-driven-trading`: name implies executable trading. Use
  `theme-cycle::event-analysis` plus paper-only `trade-planning` instead.
- `xueqiu-kol-query`, `xueqiu-kol-sentiment`, `xueqiu-quotes`,
  `xueqiu-watchlist-sync`: no verified connector in this package.

## Data Sources

Primary local source is the latest
`memory/prewarm/nightly-prewarm-*.json`. Optional providers such as Tavily,
QVeris, and xreach may enrich results when configured.

## Outputs

All commands return `ok`, `decision_allowed`, `max_action_level`, `sources`,
`warnings`, `errors`, and `result`. `decision_allowed` is always false and
`max_action_level` is `research_only`.

## Failure Rules

- Missing news, event, policy, report, sentiment, hot-money, or sector evidence
  returns `ok=false` for the relevant command.
- Optional provider failure is not silently converted into neutral evidence.
- Never treat missing intelligence as no risk, no event impact, or permission to
  trade.
