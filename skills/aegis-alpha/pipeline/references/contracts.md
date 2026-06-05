# pipeline Contracts

## Common Envelope

All commands return an orchestration envelope:

```json
{
  "package": "pipeline",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {"status": "delegated"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "pipeline_orchestration_only",
  "source": "<internal-skill>::<command>",
  "sources": ["<internal-skill>::<command>"],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {"delegated": {}}
}
```

| command | routes to | status |
|---|---|---|
| `pipeline-list` | `pipeline-runner::pipeline-list` | implemented |
| `pipeline-dry-run` | `pipeline-orchestrator::pipeline-dry-run` | implemented |
| `pipeline-run` | `pipeline-orchestrator::pipeline-run` | implemented |
| `pipeline-run-nightly` | `pipeline-orchestrator::pipeline-run` with `pipeline_id=nightly` | implemented |
| `pipeline-run-morning` | `pipeline-orchestrator::pipeline-run` with `pipeline_id=morning` | implemented |
| `pipeline-run-weekly` | `pipeline-orchestrator::pipeline-run` with `pipeline_id=weekly` | implemented |

## Safety Rules

- Pipeline artifacts are audit records, not trade authorization.
- Push steps remain disabled unless `allow_push=true`; push commands still
  require their own confirmation and credential gates.
- A missing pipeline definition, missing command reference, missing artifact, or
  failed required step returns `ok=false`.
- Optional steps may be skipped only when their optional status is represented
  in `warnings` or step-level results.
- `pipeline-run-nightly`, `pipeline-run-morning`, and `pipeline-run-weekly`
  must leave runtime artifacts under workspace `memory/` paths for audit.
