---
name: report-evolution
description: "Capture evidence and align outcomes for report evolution (Phase 1)."
metadata: {"openclaw": {"skillKey": "report-evolution", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# report-evolution

This package captures report evidence and aligns outcomes for report evolution.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### capture-report-evidence
Captures pipeline evidence for the target report window.

### align-report-outcome
Aligns report outputs with observed outcomes using the latest evidence snapshot or an explicit report ID.
