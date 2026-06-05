---
name: equity-screening
description: "Build equity universes, harvest leaders, screen candidate stocks, rate candidates, and maintain the local screening pool with fail-closed investment safety."
metadata: {"openclaw": {"skillKey": "equity-screening", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# equity-screening

Use this package when the task is about candidate stock discovery, universe
construction, leader harvesting, preliminary screening, or maintaining the
local screening pool before deeper `equity-research`.

## Runtime

Run commands through `scripts/dispatch.py` with `--command <name>` and optional
JSON `--payload`. The dispatcher reads `AEGIS_ALPHA_WORKSPACE` when set;
otherwise it uses `~/.aegis-alpha/workspace`.

## Public Commands

- `board-universe-sync`: create a board/theme universe from `payload.boards` or
  latest prewarm hot themes.
- `company-evidence-collect`: collect matching company news/research evidence
  from payload `news`/`reports` or prewarm data.
- `stock-screening`, `stock-screening-v2`: score and filter candidates.
- `layered-stock-screening`: split screened candidates into `core`,
  `watchlist`, and `reject`.
- `leader-source-harvest`: return high-scoring leaders for source tracking.
- `stock-rating`: rate one candidate.
- `stock-pool-incremental-am`, `stock-pool-incremental-pm`,
  `stock-pool-maintenance`: screen candidates and update
  `memory/stock_pool/screening-pool.json`.

## Inputs

Prefer explicit payload candidates when available:

```json
{
  "candidates": [
    {"name": "贵州茅台", "theme": "消费", "net_yi": 5, "news_hits": 2, "research_hits": 1}
  ],
  "min_score": 55
}
```

Without payload candidates, screening commands require a valid latest
`memory/prewarm/nightly-prewarm-*.json` containing `hhxg_snapshot` market data.

## Outputs

All commands return a common JSON envelope with `ok`, `decision_allowed`,
`max_action_level`, `sources`, `artifacts`, `warnings`, `errors`, and `result`.
`decision_allowed` is always false and `max_action_level` is `research_only`.

Screening scores use these factors:

- capital flow: 35%
- theme match: 20%
- information support: 25%
- market sentiment: 20%

The output is a research shortlist, not a trading recommendation. Send selected
candidates to `equity-research` for fundamentals/valuation and then to
`trade-planning` only for paper-only plans.

## Failure Rules

- Missing candidates and missing prewarm snapshot return `ok=false`.
- Missing evidence source for company evidence collection returns `ok=false`.
- Corrupt local stock pool state returns `ok=false`; do not overwrite it.
- Never treat missing data as an empty opportunity set.
