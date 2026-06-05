---
name: akshare
description: "Open-source financial data access via AkShare (public data sources)."
metadata:
  openclaw:
    skillKey: akshare
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
  hermes:
    internal: true
    facade: market-data
---

# akshare

Open-source financial data access via AkShare. Suitable for research and non-SLA data.

## Commands

### a-stock-daily
Fetch A-share daily history using AkShare.

Payload:
- `symbol` (string, required) e.g. `000001`
- `start_date` (string, optional) e.g. `20260101`
- `end_date` (string, optional) e.g. `20260310`
- `adjust` (string, optional) `""|"qfq"|"hfq"`

### index-daily
Fetch index daily history (default: 上证指数) using AkShare.

Payload:
- `symbol` (string, optional) e.g. `sh000001`
- `start_date` (string, optional)
- `end_date` (string, optional)

### north-capital-flow
Fetch northbound capital (HKSC) daily net inflow data (北向资金日级净流入).

Payload:
- `market` (string, optional) — `sh`| `sz`|`total`, default `total`
- `start_date` (string, optional) — `YYYYMMDD`
- `end_date` (string, optional)
- `limit` (int, optional) — default `20`

Underlying API: `ak.stock_em_hsgt_north_net_flow_in`

### concept-board-hist
Fetch concept board historical price performance (概念板块日线).

Payload:
- `symbol` (string, required) — board name, e.g. `华为产业鈣`
- `start_date` (string, optional) — `YYYYMMDD`
- `end_date` (string, optional)

Underlying API: `ak.stock_board_concept_hist_em`

### concept-board-list
Fetch the current list of all concept boards with today's performance (概念板块列表).

Payload: `{}`

Underlying API: `ak.stock_board_concept_name_em`

### industry-board-list
Fetch the current list of all industry boards with today's performance (行业板块列表).

Payload: `{}`

Underlying API: `ak.stock_board_industry_name_em`

### industry-board-hist
Fetch industry board historical performance (行业板块日线).

Payload:
- `symbol` (string, required) — board name, e.g. `半导体`
- `start_date` (string, optional) — `YYYYMMDD`
- `end_date` (string, optional)

Underlying API: `ak.stock_board_industry_hist_em`

### stock-individual-flow
Fetch individual stock capital inflow/outflow data (个股资金流向).

Payload:
- `symbol` (string, required) — stock code, e.g. `000001`
- `market` (string, optional) — `沪深A股`|`沪市A股`|`深市A股`, default `沪深A股`
- `limit` (int, optional) — number of days, default `10`

Underlying API: `ak.stock_individual_fund_flow`

### stock-market-flow
Fetch overall market main-force capital flow trend (市场整体主力资金流向).

Payload:
- `limit` (int, optional) — number of records, default `20`

Underlying API: `ak.stock_market_fund_flow`

### stock-hot-rank
Fetch East-Money A-share popularity hot rank (东方财富人气榜).

Payload:
- `limit` (int, optional) — top N, default `50`

Underlying API: `ak.stock_hot_rank_em`

### stock-news
Fetch individual stock news from East-Money (个股新闻).

Payload:
- `symbol` (string, required) — stock code, e.g. `000001`
- `limit` (int, optional) — number of news items, default `20`

Underlying API: `ak.stock_news_em`

### stock-minute
Fetch A-share intraday minute-level K-line data (分钟级K线).

Payload:
- `symbol` (string, required) — e.g. `000001`
- `period` (string, optional) — `1`|`5`|`15`|`30`|`60`, default `5`
- `adjust` (string, optional) — `""|"qfq"|"hfq"`, default `""`

Underlying API: `ak.stock_zh_a_hist_min_em`

### fund-etf-daily
Fetch ETF daily K-line history (主要ETF日线).

Payload:
- `symbol` (string, required) — ETF code, e.g. `510300`
- `start_date` (string, optional) — `YYYYMMDD`
- `end_date` (string, optional)
- `adjust` (string, optional) — `""|"qfq"|"hfq"`, default `"qfq"`

Underlying API: `ak.fund_etf_hist_em`

### margin-detail
Fetch A-share margin financing balance and net buy-in details (融资融券明细).

Payload:
- `exchange` (string, optional) — `sh`|`sz`|`all`, default `all`
- `date` (string, optional) — `YYYYMMDD`, default latest

Underlying APIs: `ak.stock_margin_sse`, `ak.stock_margin_szse`

### limit-up-list
Fetch the daily limit-up stock pool (涨停板股票池).

Payload:
- `date` (string, optional) — `YYYYMMDD`, default today
- `pool` (string, optional) — `zt`(涨停板)|`dt`(跌停板)|`strong`(强势股), default `zt`

Underlying API: `ak.stock_zt_pool_em`

### macro-cn-forex
Fetch China foreign exchange and gold reserve data (外汇黄金储备).

Payload:
- `limit` (int, optional) — number of months, default `24`

Underlying API: `ak.macro_china_fx_gold`

### macro-us-cpi
Fetch monthly US CPI data (美国CPI月度数据).

Payload:
- `limit` (int, optional) — number of months, default `24`

Underlying API: `ak.macro_usa_cpi_monthly`

### global-bond-yield
Fetch China and US 10-year government bond yield data (中美国债收益率).

Payload:
- `start_date` (string, optional) — `YYYYMMDD`
- `end_date` (string, optional)
- `limit` (int, optional) — default `60`

Underlying API: `ak.bond_zh_us_rate`

### macro-pmi
Fetch China PMI time series.

Payload: `{}`

### macro-cpi
Fetch China CPI time series.

Payload: `{}`

### macro-ppi
Fetch China PPI time series.

Payload: `{}`

## Runtime Notes
### Data Sources
- AkShare public endpoints; no SLA, may lag.
- `north-capital-flow`, `limit-up-list`, `margin-detail` require market hours or post-close data.
- `stock-minute` only available for recent sessions (typically last 10 trading days).

### Failure & Fallback
- If AkShare is unavailable, upstream skills may switch to Jin10/Tushare.
- `concept-board-hist` falls back to `industry-board-hist` when concept board name not found.
