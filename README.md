# Aegis Alpha

Aegis Alpha is a private, multi-agent investment skillpack. It keeps one
canonical skill source under `skills/aegis-alpha` and uses lightweight adapters
to install that source into Codex, Hermes, OpenClaw, Claude Code, or another
agent runtime.

The skillpack is research-only. It must not authorize live trading, allocation,
external sending, or execution without explicit human confirmation outside the
skill output.

## Public Surface

The default agent-facing surface is limited to 15 public skills:

- `information-retrieval`
- `market-data`
- `market-intel`
- `macro-regime`
- `theme-cycle`
- `equity-screening`
- `equity-research`
- `trade-planning`
- `portfolio-ops`
- `advice-lifecycle`
- `pipeline`
- `quality-gate`
- `quant-validation`
- `report-evolution`
- `execution-automation`

Low-level providers and compatibility shims remain internal.

## Install

Install Codex wrapper:

```bash
python3 adapters/codex/install.py
```

Install Hermes package:

```bash
python3 adapters/hermes/install.py
```

Install OpenClaw package:

```bash
python3 adapters/openclaw/install.py
```

Install Claude Code wrapper into the current project:

```bash
python3 adapters/claude-code/install.py
```

Use `--target <path>` to install into a specific directory. Existing targets are
not overwritten unless `--force` is provided.

## Validate

Run the full local acceptance set:

```bash
python3 tools/audit_capabilities.py --output-dir audit
python3 tools/check_public_contracts.py --output-dir audit
python3 tools/check_pipeline_integrity.py --output-dir audit
python3 tools/smoke_portfolio_position_research.py --output-dir audit
python3 tools/smoke_investment_closed_loop.py --output-dir audit
python3 tools/check_final_acceptance.py --audit-dir audit
```

## GitHub

This repository is intended to be pushed as a private GitHub repository. Do not
commit `.env`, local workspace state, prewarm artifacts, positions, ledgers, or
runtime memory.
