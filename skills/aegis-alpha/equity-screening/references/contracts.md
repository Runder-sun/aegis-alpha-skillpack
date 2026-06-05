# equity-screening Contracts

All commands return:

```json
{
  "package": "equity-screening",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "screening freshness is inherited from supplied candidates or latest prewarm artifact"
  },
  "decision_allowed": false,
  "max_action_level": "research_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Safety Rules

- This skill only creates research shortlists and evidence bundles.
- It never authorizes buy/sell actions or executable allocation.
- Missing candidates, missing prewarm data, missing evidence sources, or corrupt
  local pool state return `ok=false`.
- Missing data must not be interpreted as no opportunity, no risk, or negative
  evidence.
- Downstream investment use requires `equity-research` and paper-only
  `trade-planning`.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `board-universe-sync` | implemented | payload `boards` or prewarm `hot_themes` | board universe artifact and count |
| `company-evidence-collect` | implemented | `code`/`name`/`query` plus payload evidence or prewarm | matching reports/news evidence |
| `stock-screening` | implemented | `candidates` or valid prewarm snapshot | scored candidate list |
| `stock-screening-v2` | implemented | same as `stock-screening` | scored candidate list |
| `layered-stock-screening` | implemented | candidates or prewarm snapshot | `core`, `watchlist`, `reject` layers |
| `leader-source-harvest` | implemented | candidates or prewarm snapshot, optional `min_score` | high-scoring leaders |
| `stock-rating` | implemented | one candidate object or top-level candidate fields | score and grade |
| `stock-pool-incremental-am` | implemented | candidates or prewarm snapshot | new pool additions and artifact path |
| `stock-pool-incremental-pm` | implemented | candidates or prewarm snapshot | new pool additions and artifact path |
| `stock-pool-maintenance` | implemented | candidates or prewarm snapshot | refreshed pool additions and artifact path |

## Candidate Fields

Common accepted fields:

- `code`
- `name`
- `theme`
- `net_yi`
- `limitup`
- `news_hits`
- `research_hits`
- `reason`
- `source`

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["candidates_missing"],
  "result": {
    "note": "Screening evidence is incomplete; do not infer an empty opportunity set.",
    "missing_critical_inputs": ["candidates_missing"]
  }
}
```
