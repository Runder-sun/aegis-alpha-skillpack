---
name: pipeline-runner
description: "Pipeline templates for scheduled investment workflows."
metadata:
  openclaw:
    skillKey: pipeline-runner
    packageProfile: invest-core-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: pipeline
---

# pipeline-runner

This package provides deterministic pipeline templates for scheduled investment workflows.
It does not execute the pipeline itself; it returns the ordered steps so an agent or
external orchestrator can run them.

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command and pipeline definitions.
- `assets/`: reusable output templates.

## Commands

### pipeline-list
Return all available pipeline templates.

### pipeline-run
Run a pipeline by id. Payload requires `pipeline_id`.

### pipeline-run-nightly
Shortcut for `pipeline-run` with `pipeline_id=nightly`.

### pipeline-run-morning
Shortcut for `pipeline-run` with `pipeline_id=morning`.

### pipeline-run-market-review
Shortcut for `pipeline-run` with `pipeline_id=market-review`.

### pipeline-run-weekly
Shortcut for `pipeline-run` with `pipeline_id=weekly`.

## Runtime Notes
### Data Sources
- Reads `data/pipelines.json` for step definitions.

### Inputs
- `pipeline-run` requires `payload.pipeline_id`.

### Outputs
- Returns ordered steps for the pipeline without executing them.

### Failure & Fallback
- Unknown `pipeline_id` results in `SystemExit` with explicit error.
