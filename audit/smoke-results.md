# Portfolio / Position / Research / Equity / Screening / Macro / Theme / Intel / Trade / Advice / Automation / Quant / Search / Weekly Pool Smoke Results

- OK: True
- Workspace: `/tmp/aegis-alpha-smoke`

| Check | OK |
|---|---:|
| portfolio-view fails closed when state is missing | True |
| portfolio-add creates state artifact | True |
| record-trade sell updates remaining quantity | True |
| record-trade oversell fails closed | True |
| position-management-v2 reads known state | True |
| portfolio-risk-check flags concentration | True |
| position-sizing-advisor fails closed on missing inputs | True |
| information-retrieval research-history returns local artifact envelope | True |
| information-retrieval set-research-preference writes artifact | True |
| equity financial-diagnosis scores supplied metrics | True |
| equity valuation-check fails closed without valuation metrics | True |
| equity stock-analysis composes complete research package | True |
| equity-screening stock-screening scores payload candidates | True |
| equity-screening stock-screening fails closed without candidates or prewarm | True |
| equity-screening layered-stock-screening returns candidate layers | True |
| equity-screening stock-rating rates one candidate | True |
| equity-screening evidence collection fails closed without evidence source | True |
| equity-screening evidence collection uses payload evidence | True |
| equity-screening stock-pool update writes artifact | True |
| equity-screening stock-pool maintenance fails closed on corrupt pool | True |
| trade short-term-analysis fails closed without candidates or prewarm | True |
| theme-cycle themesurfer-check fails closed without market risk inputs | True |
| market-intel sentiment index fails closed without snapshot inputs | True |
| macro-regime query fails closed without snapshot inputs | True |
| macro-regime query returns risk-off bundle from snapshot | True |
| macro-regime concept-heat ranks hot themes | True |
| macro-regime alert check emits high risk alerts | True |
| market-intel sentiment index reads snapshot inputs | True |
| market-intel daily news scan reads prewarm news | True |
| market-intel policy-analysis reads policy feed | True |
| market-intel research-reports reads report feed | True |
| theme-cycle themesurfer-check returns lockout under red risk | True |
| theme-cycle event-analysis maps event to active theme | True |
| theme-cycle rebalance-check returns paper-only lockout actions | True |
| theme-cycle theme-tracker reads local theme store | True |
| theme-cycle weekly stats summarizes local theme store | True |
| trade short-term-analysis returns paper-only candidates | True |
| trade full-investment-plan composes complete paper plan | True |
| advice-lifecycle history fails closed without ledger | True |
| advice-lifecycle investment-advice records explicit paper advice | True |
| advice-lifecycle advice-update-prices updates explicit price | True |
| advice-lifecycle advice-track-stats computes paper return | True |
| advice-lifecycle expire check is review-only by default | True |
| execution-automation nightly-prewarm supports dry-run without network | True |
| execution-automation prewarm-status fails closed without artifact | True |
| execution-automation prewarm-status validates latest artifact | True |
| execution-automation market-heartbeat reads prewarm evidence | True |
| execution-automation push dry-run does not send externally | True |
| execution-automation push fails closed without explicit confirmation | True |
| quant-validation strategy-backtest fails closed without history | True |
| quant-validation strategy-backtest computes metrics from explicit series | True |
| quant-validation batch-backtest ranks valid strategies | True |
| quant-validation grid-search-advisor evaluates bounded grid | True |
| information-retrieval research-search fails closed without query | True |
| information-retrieval research-search returns structured delegated envelope | True |
| weekly-stock-pool fails closed without weekly artifacts | True |
| weekly-stock-pool consolidates verified weekly artifacts | True |