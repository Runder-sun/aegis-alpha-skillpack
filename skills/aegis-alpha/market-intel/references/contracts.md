# market-intel Contracts

All public commands return:

```json
{
  "package": "market-intel",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {
    "status": "current",
    "as_of": "<utc-runtime>",
    "policy": "market-intel freshness is inherited from supplied evidence, latest prewarm artifact, or explicit provider timestamps"
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

- Market intelligence is evidence only.
- The skill never authorizes trading, allocation, or watchlist sync actions.
- Missing intelligence source data returns `ok=false`.
- Missing data must not be interpreted as no event risk, no policy risk, or no
  sentiment risk.

## Commands

| command | status | key inputs | output |
|---|---|---|---|
| `daily-news-scan` | implemented | prewarm news or optional providers | A-share/global/China macro news |
| `global-event-scan` | implemented | prewarm event/news or optional providers | global event list and category counts |
| `event-calendar-scan` | implemented | prewarm calendar/events | A-share and global event calendar |
| `policy-analysis` | implemented | prewarm policy feed | policy summaries |
| `research-reports` | implemented | prewarm reports/news | reports and focus/macro news |
| `market-sentiment-index` | implemented | snapshot market fields | sentiment/breadth indicators |
| `black-swan-monitor` | implemented | snapshot market fields/headlines | extreme risk signals |
| `forum-sentiment` | implemented | snapshot sectors | strong/weak sector sentiment proxy |
| `kol-tracker` | implemented | snapshot hotmoney | hot-money/seat context |
| `global-sentiment-scan` | implemented | optional xreach/QVeris items | keyword sentiment scan |

## Removed Commands

| command | reason |
|---|---|
| `event-driven-trading` | executable-trading semantics are unsafe; use event analysis plus paper-only planning |
| `xueqiu-kol-query` | connector not verified |
| `xueqiu-kol-sentiment` | connector not verified |
| `xueqiu-quotes` | connector not verified |
| `xueqiu-watchlist-sync` | connector not verified |

## Failure Example

```json
{
  "ok": false,
  "decision_allowed": false,
  "errors": ["market_news_missing"],
  "result": {
    "note": "Market intelligence evidence is incomplete; do not infer sentiment, event impact, or trading action.",
    "missing_critical_inputs": ["market_news_missing"]
  }
}
```
