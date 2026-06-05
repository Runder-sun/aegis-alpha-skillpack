---
name: advice-lifecycle
description: "Paper-only investment advice recording, tracking, expiry review, and evidence-bound report prompt generation."
metadata: {"openclaw": {"skillKey": "advice-lifecycle", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# advice-lifecycle

Use this skill when the agent needs to record, track, update, expire, or review investment advice as a research artifact, or when it needs to build evidence-bound morning, nightly, weekly, or post-market report prompts.

This skill is not an execution layer. It must not place orders, recommend autonomous execution, or convert missing evidence into a tradable conclusion.

## Safety Rules

- `decision_allowed` is always `false`.
- `requires_human_confirmation` is always `true`.
- `max_action_level` is always `research_only`.
- Missing ledger, invalid ledger, missing explicit recommendation payload, missing explicit prices, or missing update ids must fail closed.
- Do not silently fetch substitute prices or infer recommendation fields from narrative text.
- Do not treat a missing ledger as "no advice" unless the command is explicitly creating a new ledger from `investment-advice` payload.
- Report prompt commands may return prompt bundles with data gaps, but those gaps must remain visible through `warnings` and `missing_critical_inputs`.

## Runtime State

Advice rows are stored in:

- `memory/advice/advice-ledger.json` under `AEGIS_ALPHA_WORKSPACE`

Each advice row is paper-only and should preserve:

- identity: `id`, `code`/`symbol`, `name`
- thesis and theme
- entry/current price when explicitly supplied
- validity window and invalidation condition
- evidence list
- status and history

## Public Commands

### investment-advice

Records explicit recommendation objects into the advice ledger. This command only persists supplied research suggestions; it does not generate new advice.

Required input:

- `recommendations`, `advices`, `advice`, or `recommendation`
- each item needs an identity field or a thesis/reason/summary

Failure cases:

- `recommendations_required`
- `recommendation_identity_or_thesis_required`
- invalid ledger JSON/schema

### advice-history

Reads the advice ledger with optional `status` and `limit` filters.

Failure cases:

- `advice_ledger_missing`
- invalid ledger JSON/schema

### advice-update-prices

Updates existing advice rows with explicit `prices` supplied by `id`, `code`, or `name`.

Failure cases:

- `prices_required`
- `no_matching_advice_for_prices`
- missing or invalid ledger

### update-daily-advice

Applies explicit status and note updates to existing advice rows.

Failure cases:

- `updates_required`
- `no_matching_advice_for_updates`
- missing or invalid ledger

### advice-expire-check

Detects expired active advice rows. It only mutates status when payload contains `apply=true`; otherwise it returns the expired set for review.

### advice-track-report

Returns per-advice rows with status, entry price, current price, return percentage, and expiry.

### advice-track-stats

Summarizes advice count, status counts, priced count, average return percentage, and positive/negative counts.

### nightly-strategy

Builds the 7-section nightly strategy prompt bundle from pipeline/prewarm/theme artifacts. Default behavior is prompt-only; LLM generation requires `enable_llm=true`.

### nightly-section

Builds a single nightly section prompt. Requires integer `section_id` from 1 to 7.

### morning-briefing

Builds a morning briefing prompt bundle from current artifacts.

### weekly-asset-report

Builds a weekly macro and asset allocation report prompt bundle from current artifacts.

### market-review

Builds a post-market review prompt bundle from current market, intelligence, and pipeline artifacts.

## Output Envelope

Every command returns a JSON object with:

- `ok`
- `decision_allowed`
- `requires_human_confirmation`
- `max_action_level`
- `source` / `sources`
- `as_of`
- `freshness`
- `artifacts`
- `warnings`
- `errors`
- `missing_critical_inputs`
- `result`

For command schemas and examples, read `data/command-manifest.json` and `references/contracts.md`.
