# pipeline-orchestrator Contracts

## Command surface
- `pipeline-run`
- `pipeline-dry-run`

## Inputs
- Pipeline definitions come from `../pipeline-runner/data/pipelines.json` in the active workspace.
- Each step is executed through a package `scripts/dispatch.py`, except HHXG direct script routing.

## Outputs
- Run records are written to `memory/pipeline_runs/`.
- Nightly context is written to `memory/pipeline_context/` before `advice-lifecycle::nightly-strategy`.
