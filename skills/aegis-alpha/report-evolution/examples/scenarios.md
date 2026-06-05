# Scenarios

## capture-report-evidence
- Triggered after nightly report generation.
- Resolves the latest runtime artifacts for `nightly` and writes a deterministic evidence snapshot under `memory/report_evidence/nightly/<report_id>/`.
- Example latest-mode payload:
  - `{"pipeline_id":"nightly","snapshot_version":7}`
- Example success result:
  - `{"ok":true,"saved_to":"<workspace>/memory/report_evidence/nightly/nightly-20260322-220000-td2026-03-23-cn-a-share-sv7","report_id":"nightly-20260322-220000-td2026-03-23-cn-a-share-sv7","idempotent":false}`
- Re-running with the same runtime sources returns the same `saved_to` path with `idempotent:true`.
- If the artifact files are rewritten in place while the paths stay the same, the rerun is treated as source drift and returns `duplicate_runtime_report_id` instead of a false idempotent success.
- Explicit-mode payloads are allowed only for files that stay inside the active workspace and inside the correct runtime directories.
- Invalid explicit-path examples:
  - outside workspace → `artifact_path_outside_workspace`
  - wrong in-workspace subtree → `artifact_path_invalid_location`
  - missing file → `missing_explicit_artifact`
- Malformed payload and artifact examples:
  - malformed CLI JSON → `invalid_payload_json`
  - non-object payload → `invalid_payload_type`
  - malformed pipeline run JSON → `invalid_pipeline_payload`
  - invalid report filename date stamp → `invalid_report_stamp`
- Unsupported phase-1 pipelines return `unsupported_phase1_pipeline`.

## align-report-outcome
- Triggered after outcome window elapses.
- Compares report assertions with observed outcomes.
- Latest-mode payload: `{"pipeline_id":"nightly"}` resolves the newest captured evidence snapshot for that pipeline.
- Explicit-mode payload: `{"pipeline_id":"nightly","report_id":"nightly-20260322-220000-td2026-03-23-cn-a-share-sv7"}` aligns a specific evidence snapshot.
- Phase 1 currently returns a pending placeholder response.

## Router messages
- `scripts/agent_turn.py agent-turn --message "evolution-capture nightly"`
- `scripts/agent_turn.py agent-turn --message "evolution-align nightly"`
