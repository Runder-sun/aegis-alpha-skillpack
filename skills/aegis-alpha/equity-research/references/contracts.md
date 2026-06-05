# equity-research Contracts

All commands return:

```json
{
  "package": "equity-research",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "research freshness is inherited from supplied metrics, source artifacts, news, or explicit timestamps"
  },
  "decision_allowed": false,
  "max_action_level": "research_only",
  "source": [],
  "sources": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

## Safety Rules

- This skill produces research evidence only.
- It never authorizes buy/sell actions.
- Missing financial or valuation metrics return `ok=false`.
- Missing evidence must not be interpreted as a negative conclusion.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `financial-diagnosis` | implemented | at least 3 core financial metrics | quality score, strengths, risks |
| `fundamental-analysis` | implemented | financial metrics, optional business context | fundamental research section |
| `narrative-analysis` | implemented | payload context or prewarm snapshot | thesis/narrative context |
| `stock-analysis` | implemented | metrics, optional news/context | combined research package |
| `stock-news` | implemented | `code`, `name`, `query`, or payload `news` | matching news evidence |
| `stock-score` | implemented | financial and/or valuation metrics | weighted research score |
| `valuation-check` | implemented | PE/PB/dividend/FCF or price+EPS | valuation grade and flags |

## Core Metric Names

Common accepted metric keys:

- `roe`
- `net_margin`
- `revenue_growth`
- `net_profit_growth`
- `debt_to_asset`
- `operating_cashflow`
- `net_profit`
- `price`
- `eps`
- `pe`
- `pb`
- `industry_pe`
- `earnings_growth`
- `dividend_yield`
- `fcf_yield`

Metrics may be supplied either in `metrics`, in `financials`, or as top-level
payload fields.

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["valuation_metrics_missing"],
  "result": {
    "note": "Equity research evidence is incomplete; do not infer an investment conclusion.",
    "missing_critical_inputs": ["valuation_metrics_missing"]
  }
}
```
