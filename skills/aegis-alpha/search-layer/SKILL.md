---
name: search-layer
description: "Research-only information retrieval layer: multi-source web search, result ranking, explicit URL reference extraction, and thread fetching."
metadata:
  openclaw:
    skillKey: search-layer
    packageProfile: info-gathering-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: information-retrieval
---

# search-layer

`search-layer` is the lower-level retrieval adapter behind research workflows.
Use `research-tools::search-and-extract` for the consolidated agent-facing
research entry, and use this skill when direct search, reference extraction, or
thread fetching is needed.

All commands are research-only. They return `decision_allowed=false`,
`requires_human_confirmation=true`, and `max_action_level=research_only`.

## Safety Rules

- Missing `query`/`queries`, `urls`, or `url` fails closed.
- Empty provider output is not a successful search result.
- Network/provider failures remain explicit in `errors` or the raw result.
- Search results are evidence candidates, not verified financial facts.
- For financial decisions, downstream skills must preserve source, date, and
  freshness before using any retrieved item.

## Commands

### search
Runs configured multi-source search. Payload supports `query` or `queries`,
`mode`, `intent`, `freshness`, `domain_boost`, `source`, and optional reference
extraction.

### extract-refs
Extracts structured references from explicit URLs. This is useful for following
issue/PR/article citation chains.

### fetch-thread
Fetches GitHub issue/PR/discussion or web discussion threads and returns
structured content, comments, and references.

## Output Contract

See `references/contracts.md`. All commands return the common envelope with
`as_of`, `freshness`, `source`, `warnings`, `errors`,
`missing_critical_inputs`, and `result`.
