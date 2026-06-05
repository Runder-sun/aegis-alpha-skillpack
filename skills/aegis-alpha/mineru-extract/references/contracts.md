# mineru-extract Contracts

| command | input highlights | output highlights |
|---|---|---|
| `parse-documents` | `file_sources`, OCR/table/formula flags, `model_version`, `emit_markdown` | MCP-aligned `{ ok, items, errors }` JSON |
| `extract-url` | single `url`, optional parsing flags and output controls | low-level MinerU extraction JSON / printed markdown |

`mineru-extract` is the high-fidelity parsing fallback inside the information-gathering stack.
