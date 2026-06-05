---
name: research-tools
description: "Shared research and utility tooling."
metadata:
  openclaw:
    skillKey: research-tools
    packageProfile: invest-core-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: information-retrieval
---

# research-tools

This package follows the OpenClaw-compatible skill protocol and keeps all runnable
components inside this workspace folder for agent-side editing and optimization.

## 信息搜集 Skill Stack
- `search-layer`: 信息搜集主搜索层，负责多源搜索、去重排序与 thread pulling。
- `content-extract`: 信息搜集内容抽取层，负责 URL → Markdown 归一化。
- `mineru-extract`: 信息搜集解析兜底层，负责 MinerU 高保真解析。

上述三个 package 与 `research-tools` 一起构成项目的 information-gathering / 信息搜集能力层。

## Package Layout
- `scripts/`: deterministic dispatch scripts for command execution and validation.
- `references/`: command contracts and cross-package boundaries.
- `examples/`: trigger phrases and invocation examples.
- `data/`: machine-readable command manifest.
- `assets/`: reusable output templates.

## Commands

### analysis-history
Legacy mapping: `analysis_history`
List recent report, pipeline, and evidence artifacts from workspace memory.

### help
Legacy mapping: `help`
Show the current public research-tools commands and rehomed legacy commands.

### search-and-extract
Legacy mapping: `search_and_extract`
Route a query to `search-layer::search`, or route a URL to
`content-extract::extract-url`.

### set-preference
Legacy mapping: `set_preference`
Persist a research preference under `memory/research/preferences.json`.

### web-content-fetch
Legacy mapping: `web_content_fetch`
Fetch and normalize a URL through `content-extract`.

## Retired / Rehomed Commands

These commands are no longer part of the default public surface because they are
investment-analysis responsibilities rather than research utility functions:

- `asset-allocation` -> use `macro-regime`, `theme-cycle`, or `trade-planning`.
- `asset-bull-bear` -> use `macro-regime`.
- `global-asset-scan` -> use `macro-regime::global-macro-analysis`.
- `grok-search` -> no configured Grok API; use `search-layer`.

## Runtime Notes

### Safety
- `decision_allowed` is always false.
- This skill gathers or locates evidence; it does not produce investment advice.
- Missing evidence returns `ok=false`; do not infer that evidence does not exist.
