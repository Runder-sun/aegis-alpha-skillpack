# pipeline-runner Examples

## pipeline-list
- Trigger: `/ pipeline-list`
- Invocation: `python scripts/dispatch.py --command pipeline-list --payload '{}'`

## pipeline-run (nightly)
- Trigger: `/ pipeline-run nightly`
- Invocation: `python scripts/dispatch.py --command pipeline-run --payload '{"pipeline_id":"nightly"}'`

## pipeline-run-morning
- Trigger: `/ pipeline-run-morning`
- Invocation: `python scripts/dispatch.py --command pipeline-run-morning --payload '{}'`
