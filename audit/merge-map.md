# AI-Invest-OpenClaw Merge Map

Recommended consolidation map generated from the current audit and optimization requirements.

| Current skill | Target surface | Action | Present |
|---|---|---|---:|
| `search-layer` | `information-retrieval` | merge with extraction and research stubs | yes |
| `content-extract` | `information-retrieval` | merge URL markdown extraction | yes |
| `mineru-extract` | `information-retrieval` | merge high-fidelity parsing fallback | yes |
| `research-tools` | `information-retrieval` | replace echo-stub surface with real retrieval router | yes |
| `portfolio-management` | `portfolio-ops` | merge with position operations and implement state mutations | yes |
| `position-ops` | `portfolio-ops` | merge risk and sizing commands | yes |
| `pipeline-runner` | `pipeline` | merge pipeline definitions | yes |
| `pipeline-orchestrator` | `pipeline` | merge pipeline execution | yes |
| `theme-cycle` | `theme-cycle` | keep public theme layer | yes |
| `themesurfer-signal` | `theme-cycle` | move MA signal into theme-cycle | yes |
| `akshare` | `market-data/internal-adapter` | keep as source adapter | yes |
| `baostock` | `market-data/internal-adapter` | keep as source adapter | yes |
| `tushare` | `market-data/internal-adapter` | keep as source adapter | yes |
| `hhxg-market` | `market-data/internal-adapter` | keep as source adapter | yes |
| `jin10-feed` | `market-intel/internal-adapter` | keep as news adapter | yes |
| `qveris-official` | `external-connector` | move out of default investment surface unless implemented | yes |