# Valuation Model Router

Use this reference when a candidate comes from a theme, theme node, or
re-rating screen. The agent chooses the valuation model; scripts can validate
inputs and compute scores.

## Routing Rules

Choose the model that matches the business economics:

- HBM / DRAM / commodity storage:
  `pb`, `cycle_normalized_earnings`, `forward_pe`, `ev_ebit`
- NAND / SSD / HDD storage infrastructure:
  `cycle_normalized_earnings`, `forward_pe`, `ev_ebit`, pricing-cycle checks
- AI server ODM / rack integration:
  `forward_pe`, `ev_ebit`, margin-upgrade bridge, backlog conversion
- Optical interconnect:
  `forward_pe`, `ev_sales`, gross-margin bridge, customer concentration
- Power, cooling, electrical infrastructure:
  `ev_ebitda`, `forward_pe`, backlog conversion, service mix
- MLCC / passive components:
  `sotp`, `forward_pe`, normalized margin, cycle-adjusted demand
- Advanced packaging materials / substrates:
  `sotp`, `forward_pe`, capacity utilization, pricing and qualification cycle
- Semiconductor equipment:
  `forward_pe`, `ev_ebit`, order cycle, backlog, shipment timing
- Broad platforms:
  `sotp`, segment revenue bridge, blended multiple

## Model Shift Test

A valuation model shift is plausible only when at least two are true:

- product mix moves toward structurally higher margin demand
- customer commitments, backlog, or qualification barriers increase visibility
- earnings revisions are starting or likely
- the company controls a bottleneck node
- old-cycle valuation metrics understate forward profit pool
- peer group used by the market is changing

## Required Output

For every theme candidate research card, state:

- old valuation model
- proposed valuation model
- why the model should or should not change
- key inputs required
- current missing inputs
- valuation sensitivity
- invalidation conditions

## Failure Rules

- If model inputs are missing, return research gaps rather than a target price.
- Do not use peak-cycle earnings as normal earnings without labeling it.
- Do not apply high-growth PE to a low-margin pass-through business unless
  margin or mix evidence supports it.
- All valuation output is research-only.
