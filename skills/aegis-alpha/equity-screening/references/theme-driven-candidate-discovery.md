# Theme-Driven Candidate Discovery

Use this reference when the agent has a theme, theme node, or theme-chain map
and needs a candidate stock universe. Candidate discovery is LLM-led; scripts
normalize, rank, persist, and audit the result.

## Candidate Sources

Build candidates from multiple sources rather than one static list:

- known leaders and pure plays
- suppliers, customers, competitors, substitutes, and equipment/material
  providers
- ETF, index, industry, and concept-board constituents
- company filings, earnings-call transcripts, presentations, and backlog/order
  commentary
- news and research report co-mentions
- price/volume sympathy moves and relative strength
- user-supplied seeds

## Coverage-Aware Flow

Before refreshing a theme stock pool, decide the coverage target. Do not force a
single tool path.

1. Identify required markets and nodes from the user's request.
2. Inspect current candidates by node and market.
3. Mark coverage gaps explicitly.
4. Choose expansion tools based on the gap:
   agent-native research for open discovery, user leads for known names,
   Tushare for A-share verification and structured data, LongBridge/LongPort for
   Hong Kong and overseas quote/identity verification, and public filings or
   company pages for business exposure.
5. Record discovered candidates with `record-theme-candidates`.
6. Refresh the stock pool only after candidates exist.

The bundled AI infrastructure chain template is an ontology/schema example and
test fixture. It can guide node names and scoring fields, but it is not a
complete global universe and must not be used to imply that uncovered markets
have no candidates.

## Candidate Relationship Types

Classify the relationship to the theme:

- `pure_play`: revenue and valuation are mostly tied to the theme
- `core_beneficiary`: material direct exposure
- `bottleneck_supplier`: scarce component, material, capacity, or qualification
- `platform`: broad infrastructure platform exposed across nodes
- `derivative_beneficiary`: second-order exposure
- `adjacent`: related but evidence is weak
- `tourist`: market narrative only; usually reject

## Candidate State

- `discovered`: newly found, not validated
- `candidate`: has at least one relevant evidence item
- `validated`: direct theme-node relationship confirmed
- `watchlist`: useful research candidate but not yet core
- `core`: high score, strong evidence, acceptable valuation context
- `rejected`: weak evidence, wrong exposure, excessive risk, or valuation too
  stretched for the theme objective
- `stale`: evidence expired or no longer confirms the thesis

## Required Evidence

Before a candidate enters `validated`, `watchlist`, or `core`, bind evidence
for at least two of:

- revenue exposure or segment disclosure
- product, customer, order, backlog, capex, pricing, or capacity evidence
- earnings revision or guidance change
- supply-chain relationship
- market share or bottleneck position
- valuation model change

## Scoring

Theme candidate scoring should include:

- directness of exposure
- bottleneck or scarcity strength
- evidence quality and freshness
- valuation headroom
- earnings revision potential
- stock breadth and relative strength
- crowding and risk penalties

Use `theme-chain-screening` for canonical chain-map candidates. Use regular
`stock-screening` when candidates are supplied from another source.

## Failure Rules

- Do not infer an empty opportunity set from missing sources.
- Do not promote candidates based only on a theme label.
- Do not treat low PE as sufficient; require evidence that the valuation model
  can change.
- Do not treat a template or fixture candidate list as a completed market scan.
- If requested markets are missing, report coverage gaps instead of filling them
  with unrelated candidates.
- Keep all outputs research-only and route selected candidates to
  `equity-research` before any paper plan.
