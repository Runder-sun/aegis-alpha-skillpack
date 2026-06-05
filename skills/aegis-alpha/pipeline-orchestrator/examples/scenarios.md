# pipeline-orchestrator Scenarios

## pipeline-run
- Trigger: "run nightly pipeline"
- Invocation: `python scripts/dispatch.py --command pipeline-run --payload '{"pipeline_id":"nightly"}'`

## pipeline-dry-run
- Trigger: "show nightly steps"
- Invocation: `python scripts/dispatch.py --command pipeline-dry-run --payload '{"pipeline_id":"nightly"}'`
