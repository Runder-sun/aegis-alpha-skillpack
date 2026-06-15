---
name: information-retrieval
description: "Public research intake facade for search, URL extraction, document parsing, and local research history."
metadata:
  openclaw:
    skillKey: information-retrieval
    packageProfile: info-gathering-v1
    requires:
      bins: ["python3"]
---

# information-retrieval

Use this as the default public entry for information gathering. It wraps the
lower-level `search-layer`, `content-extract`, `mineru-extract`, and
`research-tools` packages so agents do not need to choose between overlapping
retrieval skills.

For theme research, retrieve evidence for claims, not just links. Extract the
claim, source type, affected theme/company, timestamp, and confidence, then pass
the evidence to `market-intel`, `theme-cycle`, `equity-screening`, or
`equity-research` as needed.

## Commands

### research-search
Search for one or more queries and optionally extract references.

### fetch-content
Fetch and normalize an explicit URL.

### parse-document
Parse explicit documents or URLs through the high-fidelity document parser.

### research-history
List local research artifacts and prior pipeline/report context.

### set-research-preference
Persist a local research preference.

## Safety

- This skill is research-only; `decision_allowed` is always false.
- Missing query, URL, document path, or source evidence fails closed.
- Retrieval output is evidence, not investment advice.
- Use downstream investment skills for regime, screening, research, trade plans,
  portfolio risk, and advice lifecycle records.
