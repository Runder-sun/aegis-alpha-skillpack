---
name: equity-research
description: "Fundamental and narrative deep-dive research."
metadata: {"openclaw": {"skillKey": "equity-research", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# equity-research

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

When a company comes from a theme-chain, re-rating screen, or theme stock pool,
read `references/valuation-model-router.md` before valuation. The agent must
state the old valuation model, proposed model, evidence for the shift, missing
inputs, sensitivity, and invalidation conditions. Scripts validate metrics and
compose research sections; the LLM chooses the model and explains why.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### financial-diagnosis
Legacy mapping: `financial_diagnosis`
Diagnose profitability, growth, leverage, and cash-flow quality from supplied
financial metrics.

### fundamental-analysis
Legacy mapping: `fundamental_analysis`
Build a fundamental research section from financial metrics and optional
business context.

### narrative-analysis
Legacy mapping: `narrative_analysis`
Summarize company or market narrative from payload context and latest prewarm
snapshot.

### stock-analysis
Legacy mapping: `stock_analysis`
Compose news, narrative, fundamentals, valuation, and score into one research
package.

### stock-news
Legacy mapping: `stock_news`
Filter supplied or prewarm news for a stock code, name, or query.

### stock-score
Legacy mapping: `stock_score`
Score a stock from financial quality, valuation, and optional narrative score.

### valuation-check
Legacy mapping: `valuation_check`
Check valuation from PE/PB/dividend/FCF metrics and optional industry
comparison.

## Runtime Notes
### Data Sources
- Uses payload metrics first.
- Uses latest `memory/prewarm/nightly-prewarm-*.json` for news and narrative
  context when available.

### Outputs
- Common JSON envelope with `ok`, `decision_allowed`, `warnings`, `errors`,
  `sources`, and `result`.
- `decision_allowed` is always false. This package produces research evidence,
  not trade instructions.

### Failure & Fallback
- Missing critical metrics return `ok=false`; the caller must not infer an
  investment conclusion from absent evidence.
- If prewarm is missing, payload-driven commands can still run, but news and
  narrative commands require explicit payload context.
