---
name: equity-screening
description: "Build equity universes, harvest leaders, screen candidate stocks, rate candidates, and maintain the local screening pool with fail-closed investment safety."
metadata: {"openclaw": {"skillKey": "equity-screening", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# equity-screening

Use this package when the task is about candidate stock discovery, universe
construction, leader harvesting, preliminary screening, or maintaining the
local screening pool before deeper `equity-research`.

For theme-driven discovery, read
`references/theme-driven-candidate-discovery.md`. The LLM should discover and
classify candidates from theme nodes, suppliers, customers, peers, constituents,
filings, news, and market co-movement. Scripts normalize, score, persist, and
audit the candidate set; they do not replace evidence reasoning.
Use coverage-aware judgment before refreshing a theme stock pool: determine
which nodes and markets the user needs, inspect current candidate coverage, and
then choose suitable tools. Do not treat bundled templates as complete market
coverage.

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
- `theme-chain-screening`: score the bundled AI infrastructure chain
  template/fixture or `payload.theme_map`; use it for ontology/schema examples,
  not as a full market scan.
- `plan-theme-coverage`: write a node/market coverage plan before candidate
  expansion.
- `record-theme-candidates`: persist agent-discovered, user-supplied, or
  provider-verified candidates to the theme candidate ledger.
- `refresh-theme-stock-pool`: refresh
  `memory/stock_pool/theme-stock-pool.json` from recorded candidates or
  explicit `payload.candidates`.
- `batch-theme-research`: prepare `equity-research` deep-dive prompts from the
  theme stock pool.
- `theme-stock-pool-audit`: fail-closed audit for evidence coverage and stale
  theme candidates.
- `theme-maintenance-review`: generate coverage-gap search tasks,
  stale/downgrade suggestions, layered rankings, and verification tasks for the
  dynamic theme stock pool. Use it as an agent work queue; it does not mutate
  candidate state by itself.
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

For theme-chain template scoring, use the bundled
`data/theme-chain-template.ai-infrastructure.json` or provide
`payload.theme_map`:

```json
{
  "theme_ids": ["ai-infrastructure"],
  "node_ids": ["nand-ssd-storage", "ai-server-odm"],
  "max_forward_pe": 20,
  "min_score": 55
}
```

## Outputs

All commands return a common JSON envelope with `ok`, `decision_allowed`,
`max_action_level`, `sources`, `artifacts`, `warnings`, `errors`, and `result`.
`decision_allowed` is always false and `max_action_level` is `research_only`.

Screening scores use these factors:

- capital flow: 35%
- theme match: 20%
- information support: 25%
- market sentiment: 20%

Theme-chain screening scores use:

- valuation/forward-PE cheapness: 30%
- AI infrastructure exposure: 20%
- bottleneck strength: 20%
- valuation model shift potential: 20%
- evidence quality: 10%

It returns candidates with `chain_node`, `repricing_model`,
`valuation_models`, score breakdowns, and `core`/`watchlist`/`expensive_or_risk`
layers. Treat this output as a template/fixture unless candidates were supplied
from live research or a verified candidate ledger.

Dynamic theme maintenance should be agent-led: use `plan-theme-coverage` to
expose missing nodes/markets, discover candidates with research tools, record
and refresh the pool, audit it, then run `theme-maintenance-review` to decide
what needs discovery, verification, downgrade review, or deeper
`equity-research`. Do not silently apply status changes from the maintenance
review; bind evidence or ask for confirmation first.

The output is a research shortlist, not a trading recommendation. Send selected
candidates to `equity-research` for fundamentals/valuation and then to
`trade-planning` only for paper-only plans.

## Failure Rules

- Missing candidates and missing prewarm snapshot return `ok=false`.
- Missing evidence source for company evidence collection returns `ok=false`.
- Corrupt local stock pool state returns `ok=false`; do not overwrite it.
- Do not promote theme candidates based only on a label; require evidence before
  `validated`, `watchlist`, or `core`.
- Do not infer market coverage from a bundled template. If A-share, Hong Kong,
  US, Japan, Korea, Taiwan, or any requested market is not covered, report a
  coverage gap and choose tools only if the user/task requires expansion.
- Never treat missing data as an empty opportunity set.
