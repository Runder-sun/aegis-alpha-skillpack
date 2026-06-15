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
   supported Hong Kong/US/China quote or identity checks, and public filings,
   exchange pages, company IR, or public quote pages for markets outside the
   configured API coverage.
5. Record discovered candidates with `record-theme-candidates`.
6. Refresh the stock pool only after candidates exist.

The bundled AI infrastructure chain template is an ontology/schema example and
test fixture. It can guide node names and scoring fields, but it is not a
complete global universe and must not be used to imply that uncovered markets
have no candidates.

## Maintenance Loop

Use the maintenance loop when the user asks whether the dynamic theme system can
keep discovering, refreshing, downgrading, and validating theme candidates over
time.

1. Run `plan-theme-coverage` to expose node/market gaps.
2. Use agent-native research and available APIs to discover candidates and bind
   evidence; do not rely on a static seed list.
3. Record candidates with `record-theme-candidates`.
4. Run `refresh-theme-stock-pool` to normalize symbols, deduplicate listings,
   and score the current pool.
5. Run `theme-stock-pool-audit` to fail closed on missing evidence or stale
   state.
6. Run `theme-maintenance-review` to generate the next work queue:
   coverage-gap search tasks, stale/downgrade suggestions, layered rankings,
   and verification tasks.
7. Send selected names or verification tasks to `equity-research` for deep
   validation before changing state to `watchlist` or `core`.

Do not automatically mutate candidate state from maintenance output alone. Treat
`theme-maintenance-review` as a decision-support queue for the agent and user:
apply changes only after evidence review or explicit confirmation.

## Provider Applicability

Do not interpret an empty quote result from an inapplicable provider as evidence
that a security does not exist. LongBridge coverage depends on the account and
market permissions. If the configured LongBridge session does not support Japan,
Korea, or Taiwan, route those markets to official exchange/company IR identity
checks and public delayed quote pages, then record the verification scope.

Suggested verification routes:

- `CN`: Tushare, LongBridge when available, exchange/company filings.
- `HK`: LongBridge, HKEX, company IR.
- `US`: LongBridge, SEC/company IR, public quote pages.
- `JP`: JPX listed-company search, company IR, public delayed quote pages.
- `KR`: KRX/Seoul quote pages, company IR, public delayed quote pages.
- `TW`: TWSE, company IR, public delayed quote pages.

Record provider metadata explicitly:

- `verified_by`: e.g. `longbridge_quote`,
  `public_web_identity_delayed_quote`, `company_ir_identity`.
- `verification_scope`: e.g. `identity`, `delayed_quote`,
  `realtime_quote`, `financials`, `segment_exposure`.
- `unsupported_verifiers`: providers that were not applicable, such as
  `longbridge_quote` for markets the current account cannot cover.

## Demand Driver Nodes

Some theme nodes are not stock-universe nodes. Hyperscaler capex, policy budget,
cloud customer demand, and macro liquidity are demand-driver evidence nodes.
For these nodes, bind customer capex guidance, order/backlog commentary, and
budget evidence. Do not force market-by-market candidate coverage or call an
empty candidate list a coverage failure. Route beneficiary discovery to the
downstream component, equipment, infrastructure, or supplier nodes.

In a theme-chain map, mark these nodes with either:

- `role: demand_driver`, or
- `coverage_mode: evidence_only`.

## Symbol Normalization

Before refreshing a theme stock pool, normalize and deduplicate candidates by
market-aware symbol key. Examples:

- `MU` and `MU.US` are the same US equity candidate.
- `992` and `992.HK` are the same Hong Kong equity candidate.
- `6981` and `6981.T` are the same Japan equity candidate when `region=JP`.

Preserve aliases and multiple node memberships, but keep one ranked candidate
row per canonical security. If two records conflict, keep the stronger evidence
and latest provider verification, and retain the weaker symbol/name in
`aliases`.

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
