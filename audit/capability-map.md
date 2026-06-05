# AI-Invest-OpenClaw Capability Audit

Generated from static inspection.

- Source: `/root/hermes-agent/aegis-alpha-skillpack/skills/aegis-alpha`
- Skills: 31
- Commands: 217
- Visibility: {'public': 15, 'internal': 16}
- Skill status: {'implemented': 30, 'no_commands': 1}
- Command status: {'implemented': 217}

## Skill Summary

| Skill | Visibility | Facade | Status | Commands | Dispatch LOC | Main risks |
|---|---:|---|---:|---:|---:|---|
| `advice-lifecycle` | `public` | `` | `implemented` | 12 | 1613 |  |
| `akshare` | `internal` | `market-data` | `implemented` | 21 | 272 | manifest_missing_payload_schema, manifest_missing_result_schema, thin_contract |
| `baostock` | `internal` | `market-data` | `implemented` | 8 | 216 | manifest_missing_payload_schema, manifest_missing_result_schema, thin_contract |
| `content-extract` | `internal` | `information-retrieval` | `implemented` | 1 | 84 | manifest_missing_payload_schema, manifest_missing_result_schema |
| `equity-research` | `public` | `` | `implemented` | 7 | 423 |  |
| `equity-screening` | `public` | `` | `implemented` | 10 | 457 |  |
| `execution-automation` | `public` | `` | `implemented` | 14 | 587 |  |
| `hhxg-market` | `internal` | `market-data` | `implemented` | 16 | 135 | manifest_missing_payload_schema, manifest_missing_result_schema |
| `information-retrieval` | `public` | `` | `implemented` | 5 | 126 |  |
| `jin10-feed` | `internal` | `market-intel` | `implemented` | 4 | 150 | has_not_implemented_return, manifest_missing_payload_schema, manifest_missing_result_schema, thin_contract |
| `macro-regime` | `public` | `` | `implemented` | 8 | 1706 | empty_dict_return |
| `market-data` | `public` | `` | `implemented` | 7 | 171 |  |
| `market-intel` | `public` | `` | `implemented` | 10 | 809 | empty_dict_return |
| `mineru-extract` | `internal` | `information-retrieval` | `implemented` | 2 | 154 | manifest_missing_payload_schema, manifest_missing_result_schema |
| `pipeline` | `public` | `` | `implemented` | 6 | 154 |  |
| `pipeline-orchestrator` | `internal` | `pipeline` | `implemented` | 2 | 425 | manifest_missing_payload_schema, manifest_missing_result_schema |
| `pipeline-runner` | `internal` | `pipeline` | `implemented` | 6 | 74 | manifest_missing_payload_schema, manifest_missing_result_schema |
| `portfolio-management` | `internal` | `portfolio-ops` | `implemented` | 6 | 455 |  |
| `portfolio-ops` | `public` | `` | `implemented` | 8 | 122 |  |
| `position-ops` | `internal` | `portfolio-ops` | `implemented` | 3 | 322 |  |
| `quality-gate` | `public` | `` | `implemented` | 2 | 369 |  |
| `quant-validation` | `public` | `` | `implemented` | 7 | 683 |  |
| `qveris-official` | `internal` | `information-retrieval` | `no_commands` | 0 | 1 | placeholder_dispatch, thin_contract |
| `report-evolution` | `public` | `` | `implemented` | 2 | 134 |  |
| `research-tools` | `internal` | `information-retrieval` | `implemented` | 5 | 225 |  |
| `search-layer` | `internal` | `information-retrieval` | `implemented` | 3 | 217 |  |
| `theme-cycle` | `public` | `` | `implemented` | 11 | 1241 | empty_dict_return, empty_positions_possible |
| `themesurfer-signal` | `internal` | `theme-cycle` | `implemented` | 1 | 150 | manifest_missing_payload_schema, manifest_missing_result_schema, thin_contract |
| `trade-planning` | `public` | `` | `implemented` | 7 | 455 |  |
| `tushare` | `internal` | `market-data` | `implemented` | 22 | 359 | manifest_missing_payload_schema, manifest_missing_result_schema, thin_contract |
| `weekly-stock-pool` | `internal` | `equity-screening` | `implemented` | 1 | 296 |  |

## Command Classification

### advice-lifecycle

- `investment-advice`: `implemented` - command has explicit dispatch branch
- `advice-history`: `implemented` - command has explicit dispatch branch
- `advice-update-prices`: `implemented` - command has explicit dispatch branch
- `update-daily-advice`: `implemented` - command has explicit dispatch branch
- `advice-expire-check`: `implemented` - command has explicit dispatch branch
- `advice-track-report`: `implemented` - command has explicit dispatch branch
- `advice-track-stats`: `implemented` - command has explicit dispatch branch
- `nightly-strategy`: `implemented` - command has explicit dispatch branch
- `nightly-section`: `implemented` - command has explicit dispatch branch
- `morning-briefing`: `implemented` - command has explicit dispatch branch
- `weekly-asset-report`: `implemented` - command has explicit dispatch branch
- `market-review`: `implemented` - command has explicit dispatch branch

### akshare

- `a-stock-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `index-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `north-capital-flow`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `concept-board-hist`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `concept-board-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `industry-board-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `industry-board-hist`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-individual-flow`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-market-flow`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-hot-rank`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-news`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-minute`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `fund-etf-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `margin-detail`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `limit-up-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-forex`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-us-cpi`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `global-bond-yield`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-pmi`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cpi`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-ppi`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### baostock

- `a-stock-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `index-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-weekly`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `fundamental-data`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `balance-sheet`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `cash-flow`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `dupont-data`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `dividend-data`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### content-extract

- `extract-url`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### equity-research

- `financial-diagnosis`: `implemented` - command has explicit dispatch branch
- `fundamental-analysis`: `implemented` - command has explicit dispatch branch
- `narrative-analysis`: `implemented` - command has explicit dispatch branch
- `stock-analysis`: `implemented` - command has explicit dispatch branch
- `stock-news`: `implemented` - command has explicit dispatch branch
- `stock-score`: `implemented` - command has explicit dispatch branch
- `valuation-check`: `implemented` - command has explicit dispatch branch

### equity-screening

- `board-universe-sync`: `implemented` - command has explicit dispatch branch
- `company-evidence-collect`: `implemented` - command has explicit dispatch branch
- `layered-stock-screening`: `implemented` - command has explicit dispatch branch
- `leader-source-harvest`: `implemented` - command has explicit dispatch branch
- `stock-pool-incremental-am`: `implemented` - command has explicit dispatch branch
- `stock-pool-incremental-pm`: `implemented` - command has explicit dispatch branch
- `stock-pool-maintenance`: `implemented` - command has explicit dispatch branch
- `stock-rating`: `implemented` - command has explicit dispatch branch
- `stock-screening`: `implemented` - command has explicit dispatch branch
- `stock-screening-v2`: `implemented` - command has explicit dispatch branch

### execution-automation

- `nightly-prewarm`: `implemented` - command has explicit dispatch branch
- `morning-prewarm`: `implemented` - command has explicit dispatch branch
- `midday-prewarm`: `implemented` - command has explicit dispatch branch
- `evening-prewarm`: `implemented` - command has explicit dispatch branch
- `weekly-prewarm`: `implemented` - command has explicit dispatch branch
- `prewarm-status`: `implemented` - command has explicit dispatch branch
- `market-heartbeat`: `implemented` - command has explicit dispatch branch
- `realtime-market-scan`: `implemented` - command has explicit dispatch branch
- `realtime-alerts-summary`: `implemented` - command has explicit dispatch branch
- `realtime-monitor-control`: `implemented` - command has explicit dispatch branch
- `nightly-push`: `implemented` - command has explicit dispatch branch
- `morning-push`: `implemented` - command has explicit dispatch branch
- `intraday-push`: `implemented` - command has explicit dispatch branch
- `weekly-push`: `implemented` - command has explicit dispatch branch

### hhxg-market

- `snapshot-full`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-market`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-themes`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-ladder`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-hotmoney`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-sectors`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-news`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `snapshot-summary`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `calendar-week`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `calendar-trading`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `calendar-unlock`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `calendar-earnings`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `calendar-delivery`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `margin-full`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `margin-overview`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema
- `margin-top`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema

### information-retrieval

- `research-search`: `implemented` - command has explicit dispatch branch
- `fetch-content`: `implemented` - command has explicit dispatch branch
- `parse-document`: `implemented` - command has explicit dispatch branch
- `research-history`: `implemented` - command has explicit dispatch branch
- `set-research-preference`: `implemented` - command has explicit dispatch branch

### jin10-feed

- `jin10-snapshot`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `jin10-daemon-start`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `jin10-daemon-stop`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `jin10-daemon-status`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### macro-regime

- `capital-flow-analysis`: `implemented` - command has explicit dispatch branch
- `concept-heat`: `implemented` - command has explicit dispatch branch
- `domestic-macro`: `implemented` - command has explicit dispatch branch
- `global-macro-analysis`: `implemented` - command has explicit dispatch branch
- `macro-alert-check`: `implemented` - command has explicit dispatch branch
- `macro-regime-query`: `implemented` - command has explicit dispatch branch
- `market-review`: `implemented` - command has explicit dispatch branch
- `sector-rotation`: `implemented` - command has explicit dispatch branch

### market-data

- `snapshot-full`: `implemented` - command has explicit dispatch branch
- `margin-full`: `implemented` - command has explicit dispatch branch
- `calendar-week`: `implemented` - command has explicit dispatch branch
- `macro-pmi`: `implemented` - command has explicit dispatch branch
- `macro-cpi`: `implemented` - command has explicit dispatch branch
- `macro-ppi`: `implemented` - command has explicit dispatch branch
- `index-daily`: `implemented` - command has explicit dispatch branch

### market-intel

- `black-swan-monitor`: `implemented` - command has explicit dispatch branch
- `daily-news-scan`: `implemented` - command has explicit dispatch branch
- `event-calendar-scan`: `implemented` - command has explicit dispatch branch
- `forum-sentiment`: `implemented` - command has explicit dispatch branch
- `kol-tracker`: `implemented` - command has explicit dispatch branch
- `market-sentiment-index`: `implemented` - command has explicit dispatch branch
- `global-sentiment-scan`: `implemented` - command has explicit dispatch branch
- `global-event-scan`: `implemented` - command has explicit dispatch branch
- `policy-analysis`: `implemented` - command has explicit dispatch branch
- `research-reports`: `implemented` - command has explicit dispatch branch

### mineru-extract

- `parse-documents`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `extract-url`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### pipeline

- `pipeline-list`: `implemented` - command has explicit dispatch branch
- `pipeline-dry-run`: `implemented` - command has explicit dispatch branch
- `pipeline-run`: `implemented` - command has explicit dispatch branch
- `pipeline-run-nightly`: `implemented` - command has explicit dispatch branch
- `pipeline-run-morning`: `implemented` - command has explicit dispatch branch
- `pipeline-run-weekly`: `implemented` - command has explicit dispatch branch

### pipeline-orchestrator

- `pipeline-run`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-dry-run`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### pipeline-runner

- `pipeline-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-run`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-run-nightly`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-run-morning`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-run-market-review`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `pipeline-run-weekly`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### portfolio-management

- `portfolio-add`: `implemented` - command has explicit dispatch branch
- `portfolio-advice`: `implemented` - command has explicit dispatch branch
- `portfolio-remove`: `implemented` - command has explicit dispatch branch
- `portfolio-report`: `implemented` - command has explicit dispatch branch
- `portfolio-view`: `implemented` - command has explicit dispatch branch
- `record-trade`: `implemented` - command has explicit dispatch branch

### portfolio-ops

- `portfolio-add`: `implemented` - command has explicit dispatch branch
- `portfolio-remove`: `implemented` - command has explicit dispatch branch
- `portfolio-view`: `implemented` - command has explicit dispatch branch
- `portfolio-report`: `implemented` - command has explicit dispatch branch
- `record-trade`: `implemented` - command has explicit dispatch branch
- `portfolio-risk-check`: `implemented` - command has explicit dispatch branch
- `position-sizing-advisor`: `implemented` - command has explicit dispatch branch
- `position-management`: `implemented` - command has explicit dispatch branch

### position-ops

- `portfolio-risk-check`: `implemented` - command has explicit dispatch branch
- `position-management-v2`: `implemented` - command has explicit dispatch branch
- `position-sizing-advisor`: `implemented` - command has explicit dispatch branch

### quality-gate

- `nightly-quality-gate`: `implemented` - command has explicit dispatch branch
- `backtest-loop`: `implemented` - command has explicit dispatch branch

### quant-validation

- `agent-validation-backtest`: `implemented` - command has explicit dispatch branch
- `strategy-backtest`: `implemented` - command has explicit dispatch branch
- `batch-backtest`: `implemented` - command has explicit dispatch branch
- `strategy-compare`: `implemented` - command has explicit dispatch branch
- `grid-search-advisor`: `implemented` - command has explicit dispatch branch
- `parameter-optimization-biweekly`: `implemented` - command has explicit dispatch branch
- `nightly-eval-12m`: `implemented` - command has explicit dispatch branch

### qveris-official

- No manifest commands found.

### report-evolution

- `capture-report-evidence`: `implemented` - command has explicit dispatch branch
- `align-report-outcome`: `implemented` - command has explicit dispatch branch

### research-tools

- `analysis-history`: `implemented` - command has explicit dispatch branch
- `help`: `implemented` - command has explicit dispatch branch
- `search-and-extract`: `implemented` - command has explicit dispatch branch
- `set-preference`: `implemented` - command has explicit dispatch branch
- `web-content-fetch`: `implemented` - command has explicit dispatch branch

### search-layer

- `search`: `implemented` - command has explicit dispatch branch
- `extract-refs`: `implemented` - command has explicit dispatch branch
- `fetch-thread`: `implemented` - command has explicit dispatch branch

### theme-cycle

- `discover-themes`: `implemented` - command has explicit dispatch branch
- `event-analysis`: `implemented` - command has explicit dispatch branch
- `global-medium-long-strategy`: `implemented` - command has explicit dispatch branch
- `macro-analysis`: `implemented` - command has explicit dispatch branch
- `rebalance-check`: `implemented` - command has explicit dispatch branch
- `sector-cycle-panorama`: `implemented` - command has explicit dispatch branch
- `theme-tracker`: `implemented` - command has explicit dispatch branch
- `mainline-update`: `implemented` - command has explicit dispatch branch
- `themesurfer-check`: `implemented` - command has explicit dispatch branch
- `themesurfer-signal`: `implemented` - command has explicit dispatch branch
- `themesurfer-weekly-stats`: `implemented` - command has explicit dispatch branch

### themesurfer-signal

- `signal`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### trade-planning

- `full-investment-plan`: `implemented` - command has explicit dispatch branch
- `short-term-analysis`: `implemented` - command has explicit dispatch branch
- `stock-technical-scan`: `implemented` - command has explicit dispatch branch
- `strategy-advisor`: `implemented` - command has explicit dispatch branch
- `theme-identification`: `implemented` - command has explicit dispatch branch
- `theme-targets`: `implemented` - command has explicit dispatch branch
- `trading-strategy-v2`: `implemented` - command has explicit dispatch branch

### tushare

- `news`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `major-news`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `policy`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `research-report`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `eco-cal`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-m2`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-sf`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-gdp`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-shibor`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `macro-cn-lpr`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `daily-basic`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stock-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `stk-limit`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `top-list`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `top-inst`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `margin`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `share-float`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `income`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `balancesheet`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `cashflow`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `fina-indicator`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description
- `sw-daily`: `implemented` - command has explicit dispatch branch; manifest missing payload schema; manifest missing result schema; manifest missing description

### weekly-stock-pool

- `weekly-stock-pool`: `implemented` - command has explicit dispatch branch
