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
| `theme-chain-screening` | implemented | `data/theme-chain-template.ai-infrastructure.json` or `payload.theme_map`, optional `theme_ids`/`node_ids`/`regions`/`max_forward_pe` | template/fixture candidate list, score layers, node summary |
| `plan-theme-coverage` | implemented | dynamic `theme-chain-map.json`, optional `theme_ids`/`required_markets` | node/market coverage plan and gap list |
| `record-theme-candidates` | implemented | payload `candidates` from agent research, user input, or provider verification | appended `theme-candidates.jsonl` ledger rows |
| `refresh-theme-stock-pool` | implemented | recorded theme candidates or explicit payload candidates | refreshed `theme-stock-pool.json` artifact |
| `theme-stock-pool-audit` | implemented | theme stock pool and evidence ledger | evidence/staleness audit |
| `batch-theme-research` | implemented | theme stock pool | equity-research prompt queue |
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

Theme-chain candidates may also include:

- `symbol`
- `region`
- `market`
- `forward_pe`
- `ai_infra_exposure`
- `bottleneck_score`
- `model_shift_score`
- `evidence_quality`
- `chain_node`
- `chain_role`
- `repricing_model`
- `valuation_models`
- `risk_flags`

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
