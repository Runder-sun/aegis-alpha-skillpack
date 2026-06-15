# Dynamic Theme Discovery

Use this reference when a user asks for emerging themes, new sub-tracks,
sector trends, theme rotation, or thematic stock discovery. This workflow is
LLM-led: the agent performs semantic clustering, chain decomposition, and
evidence judgment; scripts should only normalize, persist, score, and audit.

## Workflow

1. Collect signals from market-intel, information-retrieval, market-data,
   filings, company reports, earnings calls, price/volume moves, and user
   supplied leads.
2. Extract structured theme signals:
   `theme_hint`, `node_hint`, `companies`, `catalyst_type`, `claim`,
   `source_url`, `as_of`, `confidence`.
3. Cluster related signals into candidate themes. Merge synonyms, separate
   adjacent but different chains, and keep weak one-off news as signals rather
   than themes.
4. Name the theme in plain market language and define the investment question.
5. Decompose the theme into chain nodes: demand driver, upstream bottleneck,
   core enabler, manufacturing/integration, distribution/customer, and
   substitutes/risks.
6. Assign lifecycle state and trend score.
7. Bind evidence. A theme without evidence can be `seed` only.
8. Route validated nodes to `equity-screening` for candidate discovery.
9. Send top candidates to `equity-research`; keep paper-only safety.
10. Revisit outcomes through `quality-gate`, `report-evolution`, and
    `advice-lifecycle`.

## Lifecycle States

- `seed`: weak but plausible signal cluster; no investable conclusion.
- `emerging`: multiple independent signals, early company mentions, limited
  price diffusion, evidence still incomplete.
- `accelerating`: signal velocity, order/capex/pricing evidence, and stock
  participation are all rising.
- `mainline`: broad market recognition, multi-stock participation, recurring
  earnings/news validation.
- `crowded`: theme is valid but valuation, positioning, or news saturation is
  high; downgrade new candidate aggressiveness.
- `fading`: signal velocity or price breadth weakens.
- `invalidated`: core thesis is contradicted by evidence.

## Theme Trend Score

Use a transparent score instead of intuition:

- signal velocity: frequency and acceleration of fresh evidence
- evidence quality: company filings, orders, prices, capex, earnings calls
- chain bottleneck strength: scarcity, qualification barriers, supply limits
- stock breadth: number and quality of beneficiaries participating
- earnings revision: revenue, EPS, margin, backlog, or guidance revisions
- valuation headroom: whether beneficiaries are not already fully re-rated
- crowding penalty: valuation, momentum saturation, consensus overconfidence
- contradiction penalty: evidence that weakens the thesis

## Mainline Candidate Test

A theme is a mainline candidate only when at least three are true:

- evidence arrives from more than one source type
- the theme maps to a concrete chain node and beneficiary type
- multiple related stocks move or revise earnings in the same direction
- the theme changes valuation model or profit pool allocation
- demand is tied to budget/capex/order behavior, not only narrative
- invalidation conditions are clear and monitorable

## Failure Rules

- Do not turn a single headline into a theme.
- Do not treat price action alone as industry evidence.
- Do not call a theme `emerging` or higher without evidence links or supplied
  source artifacts.
- If evidence is stale or contradictory, keep the theme as `seed`, `fading`, or
  `invalidated`.
- All outputs are research-only.
