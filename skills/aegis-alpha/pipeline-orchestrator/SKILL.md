---
name: pipeline-orchestrator
description: "Execute pipeline-runner templates with optional step skipping and result persistence."
metadata:
  openclaw:
    skillKey: pipeline-orchestrator
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
  hermes:
    internal: true
    facade: pipeline
---

# pipeline-orchestrator

Execute pipeline definitions (from pipeline-runner) and persist results.

## Commands

### pipeline-run
Run a pipeline by id.

Payload:
- `pipeline_id` (string, required)
- `allow_push` (bool, optional, default false)
- `dry_run` (bool, optional, default false)
- `max_fail` (int, optional, default 0)

### pipeline-dry-run
List steps without executing.

Payload:
- `pipeline_id` (string, required)

## Runtime Notes
### Data Sources
- Loads pipeline templates from `pipeline-runner`.
- Executes skill dispatchers in `workspace/skills/*/scripts/dispatch.py`.

### Outputs
- Persists run records to `memory/pipeline_runs/*.json`.
- Each step result includes `package`, `command`, `ok`, and `output/raw`.

### Failure & Fallback
- Optional steps can fail without aborting the pipeline.
- `max_fail` controls hard failure threshold.
