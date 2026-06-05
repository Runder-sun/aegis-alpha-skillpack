---
name: portfolio-ops
description: "Public portfolio operations facade for holdings, trade records, risk checks, and position sizing."
metadata:
  openclaw:
    skillKey: portfolio-ops
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
---

# portfolio-ops

Use this as the default public entry for portfolio state and risk operations.
It wraps `portfolio-management` and `position-ops` so agents do not need to
choose between overlapping holdings, trade-record, and sizing skills.

## Commands

### portfolio-add
Record a position in local portfolio state.

### portfolio-remove
Remove or reduce a position.

### portfolio-view
Read known portfolio state.

### portfolio-report
Summarize holdings.

### record-trade
Append an explicit trade record and update known state.

### portfolio-risk-check
Run research-only portfolio risk checks.

### position-sizing-advisor
Produce paper-only sizing guidance from explicit risk inputs.

### position-management
Read position state through the hardened position-management view.

## Safety

- Missing portfolio state fails closed and is never treated as empty holdings.
- Sizing and risk output is paper-only; `decision_allowed` is always false.
- Trade execution still requires human confirmation outside this skill.
