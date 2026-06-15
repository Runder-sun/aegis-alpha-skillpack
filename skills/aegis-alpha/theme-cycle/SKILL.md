---
name: theme-cycle
description: "Discover themes, track lifecycle state, analyze event impact, gate Themesurfer risk, and produce paper-only rotation reviews with fail-closed investment safety."
metadata: {"openclaw": {"skillKey": "theme-cycle", "packageProfile": "invest-core-v1", "requires": {"bins": []}}}
---

# theme-cycle

Use this package after `macro-regime` and before `equity-screening` when the
task needs theme discovery, lifecycle tracking, event impact analysis, or a
Themesurfer market gate.

For dynamic theme discovery or emerging sub-track work, use the LLM-led workflow
in `references/dynamic-theme-discovery.md`. The agent should collect and
cluster evidence, name candidate themes, decompose chain nodes, assign lifecycle
state, and only then persist or route candidates. Scripts are for state,
scoring, persistence, and audit; they do not replace semantic theme judgment.
Use `record-theme-signals` to bind evidence, then `write-theme-registry` to
persist `memory/dynamic_themes/theme-registry.json`,
`theme-chain-map.json`, and `evidence-ledger.jsonl`.
When routing to screening, describe the desired node/market coverage and any
known gaps. Do not imply that missing candidates mean no opportunity.

## Runtime

Run commands through `scripts/dispatch.py` with `--command <name>` and optional
JSON `--payload`. The dispatcher reads `AEGIS_ALPHA_WORKSPACE` when set;
otherwise it uses `~/.aegis-alpha/workspace`.

## Public Commands

- `discover-themes`: active/weak theme discovery from prewarm sectors.
- `record-theme-signals`: append structured theme evidence to the dynamic theme
  evidence ledger.
- `write-theme-registry`: persist the dynamic theme registry and theme-chain map
  from bound evidence or LLM-supplied themes.
- `sector-cycle-panorama`: strong/weak sector cycle snapshot.
- `event-analysis`: map events/news to active themes and risk flags.
- `theme-tracker`: read local `memory/themes.json` with optional filters.
- `mainline-update`: persist global and A-share mainlines with lifecycle history.
- `themesurfer-check`: return `FULL` or `LOCKOUT` market gate from risk inputs.
- `themesurfer-signal`: versioned Themesurfer signal with risk reasons.
- `themesurfer-weekly-stats`: lifecycle/status summary from the theme store.
- `rebalance-check`: paper-only theme rotation review actions.
- `macro-analysis`: combined macro snapshots through `macro-regime`.
- `global-medium-long-strategy`: global medium/long mainlines and allocation
  references.

## Data Sources

Primary local source is the latest
`memory/prewarm/nightly-prewarm-*.json`, especially `hhxg_snapshot.sectors`,
`hhxg_snapshot.hot_themes`, and `hhxg_snapshot.market`. The local theme store is
`memory/themes.json`. Macro context is read through the sibling `macro-regime`
command contract.

## Outputs

All commands return `ok`, `decision_allowed`, `max_action_level`, `sources`,
`artifacts`, `warnings`, `errors`, and `result`. `decision_allowed` is always
false and `max_action_level` is `research_only`.

Rotation/rebalance outputs are research reviews only. They may block or flag
new ideas, but they do not authorize portfolio changes.

## Failure Rules

- Missing sector/theme snapshot returns `ok=false` for discovery and panorama.
- Missing market risk inputs returns `ok=false` for Themesurfer checks.
- Missing theme store returns `ok=false` for tracker and weekly stats.
- Missing event/news inputs returns `ok=false` for event analysis.
- Do not upgrade a theme beyond `seed` without bound evidence.
- Never treat missing theme data as no active themes or permission to rotate.
