# information-retrieval Contracts

## Common Envelope

All commands return a research-only envelope:

```json
{
  "package": "information-retrieval",
  "command": "<command>",
  "payload": {},
  "ok": true,
  "as_of": "<utc-runtime>",
  "freshness": {"status": "delegated"},
  "decision_allowed": false,
  "requires_human_confirmation": true,
  "max_action_level": "research_only",
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
| `research-search` | `search-layer::search` | implemented |
| `fetch-content` | `research-tools::web-content-fetch` | implemented |
| `parse-document` | `mineru-extract::parse-documents` | implemented |
| `research-history` | `research-tools::analysis-history` | implemented |
| `set-research-preference` | `research-tools::set-preference` | implemented |

## Failure Rules

- Missing query, URL, document path, or unreadable source fails closed.
- Failed retrieval is not evidence that no information exists.
- Web, forum, and document evidence must carry URL/path provenance in
  `source`/`sources` before downstream investment skills may use it.
- Optional parser/provider fallback is allowed only for retrieval mechanics; it
  must remain visible in `warnings` and must not convert unavailable evidence
  into a positive investment fact.
