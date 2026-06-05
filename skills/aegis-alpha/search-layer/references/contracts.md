# search-layer Contracts

`search-layer` belongs to the information-gathering stack. Prefer
`research-tools::search-and-extract` for the agent-facing research flow; call
this skill directly only for low-level retrieval and thread/reference work.

## Common Envelope

Every command returns:

```json
{
  "package": "search-layer",
  "command": "search",
  "ok": false,
  "as_of": "2026-06-04T00:00:00Z",
  "freshness": {"status": "unavailable"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "research_only",
  "source": [],
  "sources": [],
  "artifacts": [],
  "warnings": [],
  "errors": ["search requires query or queries"],
  "missing_critical_inputs": ["search requires query or queries"],
  "result": {
    "note": "Search evidence is unavailable; do not infer facts from missing retrieval results."
  }
}
```

## Command Table

| command | input highlights | output highlights | failure behavior |
|---|---|---|---|
| `search` | `query` or `queries`, `mode`, `intent`, `freshness`, `domain_boost`, `source`, `extract_refs` | upstream `search.py` JSON result in common envelope | missing query or empty provider output fails closed |
| `extract-refs` | `urls`, optional `intent` | reference extraction JSON | missing URLs fails closed |
| `fetch-thread` | `url`, optional `max_comments`, `format`, `extract_refs_only` | structured thread JSON or markdown | missing URL or fetch failure is explicit |

## Allowed Fallbacks

Allowed:

- Providers may be tried according to the configured search mode.
- Thread fetching may use a generic web fallback after a specialized API fails,
  but the result must preserve errors/metadata.

Not allowed:

- Empty search output becomes a successful fact.
- Search results are treated as financial decision evidence without downstream
  provenance and freshness checks.
- Any output sets `decision_allowed=true`.
