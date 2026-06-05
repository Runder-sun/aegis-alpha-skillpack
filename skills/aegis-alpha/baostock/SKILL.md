---
name: baostock
description: "BaoStock data access (A-share and index history)."
metadata:
  openclaw:
    skillKey: baostock
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
  hermes:
    internal: true
    facade: market-data
---

# baostock

BaoStock data access for A-share and index historical K-line data.

## Commands

### a-stock-daily
Query A-share daily history.

Payload:
- `symbol` (string, required) e.g. `sh.600000` / `sz.000001`
- `start_date` (string, optional) `YYYY-MM-DD`
- `end_date` (string, optional) `YYYY-MM-DD`
- `fields` (string, optional) default: `date,code,open,high,low,close,volume,amount,turn`
- `adjustflag` (string, optional) default: `3` (no-adjust)

### index-daily
Query index daily history.

Payload:
- `symbol` (string, required) e.g. `sh.000001`
- `start_date` (string, optional)
- `end_date` (string, optional)
- `fields` (string, optional)
- `adjustflag` (string, optional)

### stock-weekly
A 股/指数周线行情数据。

Payload:
- `symbol` (string, required) — e.g. `sh.600000` / `sz.000001`
- `start_date` (string, optional) — `YYYY-MM-DD`
- `end_date` (string, optional) — `YYYY-MM-DD`
- `fields` (string, optional) — default `date,code,open,high,low,close,volume,amount,turn,pctChg`
- `adjustflag` (string, optional) — `1`(后复权)|`2`(前复权)|`3`(不复权)，default `3`

Underlying API: `bs.query_history_k_data_plus` with `frequency="w"`

### fundamental-data
盈利能力 + 成长能力季度指标（ROE/净利润率/营收增长率等）。

Payload:
- `symbol` (string, required) — e.g. `sh.600000`
- `year` (int, optional) — 财报年份，如 `2023`；空则取最新
- `quarter` (int, optional) — 季度 `1`~`4`；空则返回全年最新

Underlying API: `bs.query_profit_data` + `bs.query_growth_data`

### balance-sheet
资产负债表关键指标（总资产/总负债/股东权益/资产负债率）。

Payload:
- `symbol` (string, required) — e.g. `sh.600000`
- `year` (int, optional) — 财报年份
- `quarter` (int, optional) — 季度 `1`~`4`

Underlying API: `bs.query_balance_data`

### cash-flow
现金流量表数据（经营/投资/筹资现金净额）。

Payload:
- `symbol` (string, required) — e.g. `sh.600000`
- `year` (int, optional) — 财报年份
- `quarter` (int, optional) — 季度 `1`~`4`

Underlying API: `bs.query_cash_flow_data`

### dupont-data
杜邦分析分解指标（净资产收益率 = 净利率 × 资产周转率 × 权益乘数）。

Payload:
- `symbol` (string, required) — e.g. `sh.600000`
- `year` (int, optional) — 财报年份
- `quarter` (int, optional) — 季度 `1`~`4`

Underlying API: `bs.query_dupont_data`

### dividend-data
历史分红派息数据（每股股息/分红率/派发日期）。

Payload:
- `symbol` (string, required) — e.g. `sh.600000`
- `year` (string, optional) — 年份 `YYYY`；空则返回全部历史

Underlying API: `bs.query_dividend_data`

## Runtime Notes
### Failure & Fallback
- Requires BaoStock login; failure returns error payload.
- Upstream skills may fall back to AkShare for index data.
