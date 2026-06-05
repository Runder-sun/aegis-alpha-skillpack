# content-extract Contracts

| command | input highlights | output highlights |
|---|---|---|
| `extract-url` | `url`, optional `model`, `language`, `max_chars`, `force` | `{ ok, source_url, engine, markdown, artifacts, sources, notes }` |

`content-extract` is the information-gathering content normalization layer.
It is typically called after `search-layer` identifies a relevant URL.
