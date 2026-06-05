# Contracts

## Common Envelope

All commands return a report-review envelope:

```json
{
  "package": "report-evolution",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {"status": "runtime_artifact_check"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "report_review_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": [],
  "missing_critical_inputs": [],
  "result": {}
}
```

The legacy top-level `error` field may appear for explicit artifact validation
failures, but public callers must also treat that as `ok=false` and stop any
downstream investment chain that depends on the missing evidence.

## capture-report-evidence
- Inputs:
  - latest mode: `{"pipeline_id":"nightly","snapshot_version":7}`
  - explicit mode: `{"pipeline_id":"nightly","pipeline_run_path":"/workspace/memory/pipeline_runs/nightly-20260322-215955.json","report_path":"/workspace/memory/reports/nightly-report-20260322-220000.md","market_context_path":"/workspace/memory/pipeline_context/nightly-context-20260322-215950.json","snapshot_version":7}`
- Explicit artifact paths must resolve inside the active workspace and under their expected runtime directories:
  - `pipeline_run_path` → `memory/pipeline_runs/`
  - `report_path` → `memory/reports/`
  - `market_context_path` → `memory/pipeline_context/`
- Success output:
  - `{"ok":true,"saved_to":"<workspace>/memory/report_evidence/nightly/<report_id>","report_id":"nightly-20260322-220000-td2026-03-23-cn-a-share-sv7","idempotent":false}`
- Idempotent rerun output:
  - `{"ok":true,"saved_to":"<workspace>/memory/report_evidence/nightly/<report_id>","report_id":"nightly-20260322-220000-td2026-03-23-cn-a-share-sv7","idempotent":true}`
  - Idempotency requires both the same artifact paths and unchanged artifact contents; if content drifts in place, capture returns `duplicate_runtime_report_id`.
- Error outputs:
  - invalid payload JSON: `{"ok":false,"error":"invalid_payload_json"}`
  - invalid payload type: `{"ok":false,"error":"invalid_payload_type"}`
  - unsupported pipeline: `{"ok":false,"error":"unsupported_phase1_pipeline","pipeline_id":"morning"}`
  - latest-mode artifact discovery failed: `{"ok":false,"error":"missing_runtime_artifacts","pipeline_id":"nightly"}`
  - malformed pipeline run JSON: `{"ok":false,"error":"invalid_pipeline_payload","path":"<workspace>/memory/pipeline_runs/nightly-20260322-215955.json","pipeline_id":"nightly"}`
  - invalid report filename stamp: `{"ok":false,"error":"invalid_report_stamp","path":"<workspace>/memory/reports/nightly-report-20261340-220000.md","pipeline_id":"nightly"}`
  - explicit path escapes workspace: `{"ok":false,"error":"artifact_path_outside_workspace","field":"pipeline_run_path","path":"/tmp/outside.json","pipeline_id":"nightly"}`
  - explicit path is in the wrong workspace subtree: `{"ok":false,"error":"artifact_path_invalid_location","field":"pipeline_run_path","path":"<workspace>/skills/report-evolution/SKILL.md","pipeline_id":"nightly"}`
  - explicit path is missing: `{"ok":false,"error":"missing_explicit_artifact","field":"report_path","path":"<workspace>/memory/reports/nightly-report-20260323-000000.md","pipeline_id":"nightly"}`
  - duplicate `report_id` with different runtime sources: `{"ok":false,"error":"duplicate_runtime_report_id","report_id":"..."}`
- Saved evidence directory contents:
  - `pipeline.json`
  - `prompt-bundle.json`
  - `final-report.md`
  - `market-context.json`
  - `metadata.json`
  - `outcome.json`
  - `subagent-manifest.json`
  - `subagents/*.md`

## align-report-outcome
- Inputs:
  - latest mode: `{"pipeline_id":"nightly"}`
  - explicit mode: `{"pipeline_id":"nightly","report_id":"nightly-20260322-220000-td2026-03-23-cn-a-share-sv7"}`
- Latest mode resolves the newest captured evidence snapshot under `memory/report_evidence/<pipeline_id>/`.
- Outputs: alignment summary (Phase 1 placeholder).

## Safety Rules

- Report evolution is post-hoc evidence alignment, not a trading signal.
- Missing runtime artifacts, path escape attempts, duplicate report IDs with
  changed sources, and invalid evidence metadata fail closed.
- Saved evidence must preserve pipeline, prompt bundle, final report,
  market-context, metadata, outcome, and subagent artifacts when available.
- Alignment output must identify evidence gaps rather than filling them with
  narrative assumptions.
