# pipeline-runner Contracts

## Pipeline schema

Each pipeline entry in `data/pipelines.json` uses:

- `id` (string, kebab-case)
- `label` (string)
- `description` (string)
- `steps` (list)

Each step uses:

- `package` (string): skill package name
- `command` (string): command name in that package
- `optional` (boolean): whether the step can be skipped
- `note` (string): short intent/description

## Commands

- `pipeline-list` returns all pipelines.
- `pipeline-run` requires payload: `{ "pipeline_id": "nightly" }`.
- `pipeline-run-*` are shortcuts to `pipeline-run`.
