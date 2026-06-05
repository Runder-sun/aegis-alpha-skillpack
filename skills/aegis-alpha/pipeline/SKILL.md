---
name: pipeline
description: "Public investment workflow pipeline facade for listing templates, dry-runs, and auditable execution."
metadata:
  openclaw:
    skillKey: pipeline
    packageProfile: invest-core-v1
    requires:
      bins: ["python3"]
---

# pipeline

Use this as the default public entry for scheduled investment workflows. It
wraps `pipeline-runner` and `pipeline-orchestrator` so agents do not need to
choose between template discovery and execution internals.

## Commands

### pipeline-list
List available investment workflow templates.

### pipeline-dry-run
Validate a pipeline path without running steps.

### pipeline-run
Run a named pipeline and persist an auditable result artifact.

### pipeline-run-nightly
Run or dry-run the nightly workflow.

### pipeline-run-morning
Run or dry-run the morning workflow.

### pipeline-run-weekly
Run or dry-run the weekly workflow.

## Safety

- Push steps remain disabled unless `allow_push=true`.
- Pipeline outputs are auditable artifacts, not autonomous trading permission.
- Missing packages, commands, or artifacts fail closed through the orchestrator.
