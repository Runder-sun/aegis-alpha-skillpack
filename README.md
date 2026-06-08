# Aegis Alpha

Research-only multi-agent investment skillpack for market data provenance,
macro regime analysis, theme rotation, equity screening, equity research,
paper-only trade planning, portfolio/risk review, advice lifecycle tracking,
pipeline orchestration, quality gates, quant validation, report evolution, and
fail-closed financial safety.

This repository is public. Do not commit `.env`, API keys, local workspace
state, prewarm artifacts, positions, ledgers, reports, runtime memory, or any
other personal/account data.

## Language

- [中文](#中文)
- [English](#english)

---

# 中文

## 这是什么

Aegis Alpha 是一个面向 AI agent 的投资研究技能包。它不是交易机器人，也不会授权实盘下单。它的目标是把投资研究工作流拆成可审计的能力模块：数据采集、宏观判断、主题轮动、个股筛选、深度研究、纸面交易计划、组合复盘、建议生命周期、自动化预热和报告生成。

核心原则：

- **研究用途**：所有输出都是研究、复盘、纸面计划或工作流结果。
- **禁止实盘授权**：不允许 live trading、外部下单、资产配置授权。
- **证据可追溯**：输出必须保留 `source`、`as_of`、`freshness`、`warnings`、`errors`、`missing_critical_inputs`。
- **缺证据就 fail-closed**：缺市场数据、缺持仓、缺价格、数据过期时，不把空结果解释为“无风险”或“无机会”。

## 能做什么

### 1. 初始化与配置引导

初始化是一个独立 public skill：`aegis-alpha-initialization`。第一次使用时，它会先向用户说明：

- 技能包能做哪些投资研究工作流。
- 哪些配置是必须项，哪些是可选项。
- 每个 API 或运行配置解锁什么能力。
- 跳过配置后会失去什么能力。
- 每个 provider 的配置网址。
- prewarm、heartbeat、portfolio source、external push 分别是什么。

初始化不是简单脚本。agent 必须一步步询问、记录用户确认，并且只有在必选项配置完成、可选项被明确配置/跳过/禁用后，才可以说初始化完成。

### 2. 市场数据与数据溯源

`aegis-alpha-market-data` 从最新 prewarm artifact 读取结构化市场数据，包含：

- A 股市场快照、情绪、涨停/跌停、炸板、连板梯队。
- 板块强弱、行业资金、题材热度、游资/机构席位。
- 指数日线、宏观指标、交易日历、两融数据。
- 数据来源、更新时间、freshness 状态和缺口。

市场数据不允许静默 fallback。缺关键字段时必须失败，而不是返回空数组假装成功。

### 3. 市场情报与新闻事件

`aegis-alpha-market-intel` 用于收集和整理：

- 市场新闻、宏观事件、政策、研报摘要。
- 黑天鹅监控、风险新闻、全球事件日历。
- KOL/席位/论坛情绪代理。
- provider-backed market intelligence 和 agent-native 搜索结果。

当 `market_intel` API 未配置时，agent 可以使用自身 web/search 工具补充证据；若无法证明新鲜事实，必须显式说明缺口。

### 4. 宏观 regime 与资金环境

`aegis-alpha-macro-regime` 用于判断：

- 全球 risk-on/risk-off 状态。
- 中国宏观环境、PMI/CPI/PPI、流动性、社融、GDP、利率。
- A 股情绪温度、风险预算、资金面。
- 板块轮动和概念热度。

输出会给出风险等级、风险预算参考、主要理由和数据来源。

### 5. 主题周期与 ThemeSurfer 门控

`aegis-alpha-theme-cycle` 用于：

- 发现当前活跃主题。
- 跟踪长期/中期/短期/超短期主线。
- 判断板块周期位置、过热风险和退潮风险。
- 执行 ThemeSurfer 风险门控，例如 `FULL` 或 `LOCKOUT`。

当 ThemeSurfer 为 `LOCKOUT` 时，短线 A 股新开仓应被禁止或降级为观察，不应输出可执行买入计划。

### 6. 个股筛选与深度研究

`aegis-alpha-equity-screening` 和 `aegis-alpha-equity-research` 用于：

- 建立候选池、筛选股票、维护本地股票池。
- 收集证据、识别题材/叙事/基本面匹配度。
- 做公司叙事、基本面、估值、催化剂和风险研究。
- 输出可审计的候选评分和研究摘要。

缺候选、缺价格、缺估值指标或缺证据时，相关命令必须 fail-closed。

### 7. 纸面交易计划

`aegis-alpha-trade-planning` 只生成 paper-only 交易计划：

- 短线策略分析。
- 候选入场条件、目标、止损和失效条件。
- T+1、风险收益比、主题门控约束。

它不会下单，也不会授权任何外部交易系统。

### 8. 组合与持仓复盘

`aegis-alpha-portfolio-ops` 用于：

- 读取或维护持仓来源。
- 风险检查、持仓分析、头寸规模建议。
- 结合市场数据做组合风险复盘。

组合分析需要真实持仓字段：数量、成本、市值或权重。只有标的清单时，只能作为观察清单，不能推断空仓、盈亏、仓位或风险暴露。

### 9. 建议生命周期

`aegis-alpha-advice-lifecycle` 用于 paper-only 建议管理：

- 记录显式建议对象。
- 跟踪建议状态、有效期、价格更新和结果。
- 生成早盘/晚间报告 prompt bundle。
- 做建议过期检查和报告证据绑定。

它不自行发明建议。所有建议必须有明确身份、 thesis、失效条件和证据。

### 10. Pipeline 与自动化

`aegis-alpha-pipeline` 和 `aegis-alpha-execution-automation` 用于：

- 运行 morning / market-review / nightly / weekly 工作流。
- 执行 prewarm，生成可审计数据缓存。
- 检查 prewarm 状态和关键缺口。
- 创建 heartbeat/日常预热自动化。
- 在用户明确确认且配置凭证后执行外部推送。

prewarm 不是用户直接配置的 public skill。它是安装和运行时健康检查/缓存填充步骤。Recurring prewarm 属于 heartbeat 自动化配置。

### 11. 质量门禁、量化验证、报告演化

其他 public skills 覆盖：

- `aegis-alpha-quality-gate`：夜间质量检查和回测循环。
- `aegis-alpha-quant-validation`：离线回测、策略比较、参数搜索。
- `aegis-alpha-report-evolution`：证据捕获、结果对齐、报告演化。
- `aegis-alpha-information-retrieval`：搜索、URL 抽取、文档解析和本地研究历史。

## Public Surface

默认暴露 16 个 public skills：

- `aegis-alpha-initialization`
- `aegis-alpha-information-retrieval`
- `aegis-alpha-market-data`
- `aegis-alpha-market-intel`
- `aegis-alpha-macro-regime`
- `aegis-alpha-theme-cycle`
- `aegis-alpha-equity-screening`
- `aegis-alpha-equity-research`
- `aegis-alpha-trade-planning`
- `aegis-alpha-portfolio-ops`
- `aegis-alpha-advice-lifecycle`
- `aegis-alpha-pipeline`
- `aegis-alpha-quality-gate`
- `aegis-alpha-quant-validation`
- `aegis-alpha-report-evolution`
- `aegis-alpha-execution-automation`

`aegis-alpha` 是聚合 conductor skill，适合跨模块任务或不知道该调用哪个 public skill 时使用。低层 provider、parser、兼容层默认是 internal。

## 必选与可选配置

### 全局必选：market_data

Aegis Alpha 完整初始化必须配置 `market_data` baseline。

| 市场 | 推荐配置 | 说明 |
|---|---|---|
| A 股/中国市场 | `TUSHARE_TOKEN` | 参考 Tushare：<https://tushare.pro> |
| 海外市场 | LongBridge / LongPort | 推荐：<https://open.longbridge.com/skill/> |
| 海外 fallback | `FINNHUB_API_KEY` | 仅当 LongBridge 不可用时使用：<https://finnhub.io> |

LongBridge 可以通过两种方式满足海外 market_data：

- 配置 `LONGPORT_APP_KEY`、`LONGPORT_APP_SECRET`、`LONGPORT_ACCESS_TOKEN`。
- 或安装并登录 LongBridge CLI，使 `longbridge auth status` 返回有效会话。

### 可选 API 组

| API 组 | 环境变量 | 配置网址 | 解锁能力 | 跳过后影响 |
|---|---|---|---|---|
| `research_search` | `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://app.tavily.com>, <https://qveris.ai/docs> | 搜索扩展、来源发现 | 使用 agent-native 搜索；无法证明新鲜事实时 fail-closed |
| `document_parse` | `MINERU_API_KEY` | <https://mineru.net/apiManage/docs> | 大 PDF/研报解析 | 只能用 agent-native 文件读取或用户提供文本 |
| `market_intel` | `JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://www.jin10.com/> 等 | 新闻、宏观事件、主题催化 | provider-backed 情报能力下降 |
| `external_push` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID` | <https://open.feishu.cn> | 飞书确认推送 | 只能在 agent 对话或 workspace 输出 |

## 初始化预设

| Preset | 适用场景 |
|---|---|
| `quick-research` | 一次性研究和证据收集 |
| `daily-desk` | 早盘/晚间市场桌面工作流 |
| `portfolio-desk` | 持仓、交易日志、风险复盘、建议跟踪 |
| `report-review` | 报告证据捕获、复盘和结果对齐 |
| `full-institutional` | 完整研究、市场、组合、验证和报告闭环 |

Preset 是默认运行配置，不是功能门禁。选择任意 preset 后，16 个 public skills 仍然可用。

## 安装

Codex 安装：

```bash
python3 adapters/codex/install.py
```

Hermes 安装：

```bash
python3 adapters/hermes/install.py
```

OpenClaw 安装：

```bash
python3 adapters/openclaw/install.py
```

Claude Code 安装：

```bash
python3 adapters/claude-code/install.py
```

Codex 和 Claude Code 会安装 native public skillset：

- `.aegis-alpha-core`：共享 canonical source。
- `aegis-alpha`：聚合 conductor skill。
- `aegis-alpha-<public-skill>`：每个 public skill 的原生技能目录。

默认使用 symlink。若运行环境不支持 symlink，可使用 `--link-mode copy`。

## 初始化

安装后，在 agent 里说：

```text
使用 $aegis-alpha 初始化
```

或：

```text
使用 $aegis-alpha-initialization 继续初始化
```

初始化过程会逐步确认：

1. 选择 preset。
2. 配置全局必选 `market_data`。
3. 配置、跳过或禁用可选 API 组。
4. 是否立即运行一次 prewarm，或延后到日常任务。
5. 是否创建 heartbeat/每日自动化任务。
6. 选择 portfolio source，并确认是否已有持仓。
7. 最终 review。

## 生成报告

初始化完成后，可以在 Codex 中请求：

```text
使用 $aegis-alpha 生成今日报告
```

典型流程：

1. `aegis-alpha-initialization` 检查初始化状态。
2. `aegis-alpha-execution-automation` 运行 prewarm 或检查 prewarm freshness。
3. `aegis-alpha-market-data` 读取市场快照。
4. `aegis-alpha-market-intel` 收集新闻、政策、研报和风险事件。
5. `aegis-alpha-macro-regime` 输出宏观 regime 和风险预算。
6. `aegis-alpha-theme-cycle` 输出主题轮动和 ThemeSurfer 门控。
7. `aegis-alpha-portfolio-ops` 在持仓信息完整时做组合复盘。
8. agent 汇总生成研究报告。

如果组合只有标的清单，没有数量、成本、市值或权重，报告必须降级为“持仓观察清单”，不能生成仓位风险或盈亏结论。

## 验证

运行完整本地验收：

```bash
python3 skills/aegis-alpha/scripts/bootstrap_runtime.py --dry-run
python3 skills/aegis-alpha/scripts/provider_resolver.py --capability research_search --profile /dev/null
python3 tools/audit_capabilities.py --output-dir audit
python3 tools/check_public_skill_visibility.py --output-dir audit
python3 tools/check_public_contracts.py --output-dir audit
python3 tools/check_pipeline_integrity.py --output-dir audit
python3 tools/smoke_portfolio_position_research.py --output-dir audit
python3 tools/smoke_investment_closed_loop.py --output-dir audit
python3 tools/check_final_acceptance.py --audit-dir audit
```

---

# English

## What This Is

Aegis Alpha is an investment research skillpack for AI agents. It is not a
trading bot and does not authorize live orders. Its purpose is to turn
investment research into auditable modules: data intake, macro regime analysis,
theme rotation, equity screening, deep research, paper-only trade planning,
portfolio review, advice lifecycle tracking, automation, and report generation.

Core rules:

- **Research-only**: outputs are research, reviews, paper plans, or workflow artifacts.
- **No live authorization**: no live trading, external order execution, or allocation authorization.
- **Provenance first**: outputs preserve `source`, `as_of`, `freshness`,
  `warnings`, `errors`, and `missing_critical_inputs`.
- **Fail closed**: missing market data, stale evidence, missing holdings, or
  missing prices must not be interpreted as no risk or no opportunity.

## Capabilities

### 1. Initialization And Guided Setup

First-run setup is handled by `aegis-alpha-initialization`. It explains:

- what the skillpack can do;
- which setup items are required or optional;
- what each API group unlocks;
- what happens if a setup item is skipped;
- where to get provider credentials;
- what prewarm, heartbeat, portfolio source, and external push mean.

Initialization is not a one-shot script. The agent must guide the user step by
step, record explicit choices, and only report completion after required setup
is configured and optional setup is explicitly configured, skipped, or disabled.

### 2. Market Data And Provenance

`aegis-alpha-market-data` reads structured data from the latest prewarm
artifact:

- A-share market snapshot, sentiment, limit-up/down, fried boards, and ladder data;
- sector strength, capital flow, hot themes, hot-money and institution context;
- index daily bars, macro indicators, calendars, margin data;
- data source, update time, freshness status, and critical gaps.

Missing critical fields must fail closed instead of returning empty success.

### 3. Market Intelligence

`aegis-alpha-market-intel` collects and summarizes:

- market news, macro events, policy items, and research reports;
- black-swan monitoring and global event calendars;
- sentiment proxies, forum/KOL context, and seat activity;
- provider-backed feeds and agent-native search evidence.

When provider APIs are not configured, the current agent may use native web or
search tools. If fresh evidence cannot be proven, the output must surface the gap.

### 4. Macro Regime

`aegis-alpha-macro-regime` evaluates:

- global risk-on/risk-off mode;
- China macro indicators, liquidity, social financing, GDP, and rates;
- A-share risk temperature and risk-budget references;
- sector rotation and concept heat.

Outputs include risk level, risk budget, reasons, and sources.

### 5. Theme Cycle And ThemeSurfer

`aegis-alpha-theme-cycle` supports:

- current theme discovery;
- long, mid, short, and ultra-short theme tracking;
- cycle-stage and overheating risk analysis;
- ThemeSurfer gates such as `FULL` and `LOCKOUT`.

When ThemeSurfer returns `LOCKOUT`, new A-share short-term entries should be
blocked or downgraded to watchlist-only.

### 6. Equity Screening And Research

`aegis-alpha-equity-screening` and `aegis-alpha-equity-research` support:

- candidate universe construction and maintenance;
- evidence collection and narrative/fundamental matching;
- company research, valuation context, catalysts, and risks;
- auditable scores and research summaries.

Missing candidates, prices, valuation metrics, or evidence must fail closed.

### 7. Paper-Only Trade Planning

`aegis-alpha-trade-planning` produces paper-only plans:

- short-term strategy analysis;
- entry conditions, targets, stops, and invalidation;
- T+1, risk/reward, and theme-gate constraints.

It does not place orders and does not authorize external trading systems.

### 8. Portfolio And Risk Review

`aegis-alpha-portfolio-ops` supports:

- reading or maintaining a portfolio source;
- risk checks, position analysis, and position sizing;
- market-aware portfolio reviews.

Real portfolio review requires quantity, cost basis, market value, or portfolio
weight. A symbols-only list is a watchlist, not a portfolio state.

### 9. Advice Lifecycle

`aegis-alpha-advice-lifecycle` supports:

- recording explicit paper-only recommendation objects;
- tracking status, expiry, prices, and outcomes;
- generating morning and nightly report prompt bundles;
- binding advice to evidence and report outcomes.

It does not invent recommendations on its own. Advice must include identity,
thesis, invalidation, and evidence.

### 10. Pipelines And Automation

`aegis-alpha-pipeline` and `aegis-alpha-execution-automation` support:

- morning, market-review, nightly, and weekly workflows;
- prewarm generation and freshness checks;
- heartbeat and daily prewarm automation;
- explicit-confirmation external push when configured.

Prewarm is not a user-facing public skill. It is a runtime health and cache
seeding step. Recurring prewarm belongs to heartbeat automation.

### 11. Quality Gate, Quant Validation, Report Evolution

Additional public skills cover:

- `aegis-alpha-quality-gate`: nightly quality checks and backtest loops.
- `aegis-alpha-quant-validation`: offline backtesting and strategy comparison.
- `aegis-alpha-report-evolution`: evidence capture and outcome alignment.
- `aegis-alpha-information-retrieval`: search, URL extraction, document parsing, and local research history.

## Public Surface

Aegis Alpha exposes 16 public skills:

- `aegis-alpha-initialization`
- `aegis-alpha-information-retrieval`
- `aegis-alpha-market-data`
- `aegis-alpha-market-intel`
- `aegis-alpha-macro-regime`
- `aegis-alpha-theme-cycle`
- `aegis-alpha-equity-screening`
- `aegis-alpha-equity-research`
- `aegis-alpha-trade-planning`
- `aegis-alpha-portfolio-ops`
- `aegis-alpha-advice-lifecycle`
- `aegis-alpha-pipeline`
- `aegis-alpha-quality-gate`
- `aegis-alpha-quant-validation`
- `aegis-alpha-report-evolution`
- `aegis-alpha-execution-automation`

`aegis-alpha` is the aggregate conductor skill for cross-skill workflows or
ambiguous requests. Low-level providers, parsers, and compatibility shims are internal.

## Required And Optional Setup

### Globally Required: market_data

Aegis Alpha is not fully initialized until the global `market_data` baseline is configured.

| Market | Recommended setup | Notes |
|---|---|---|
| A-share / China | `TUSHARE_TOKEN` | Tushare: <https://tushare.pro> |
| Overseas | LongBridge / LongPort | Preferred: <https://open.longbridge.com/skill/> |
| Overseas fallback | `FINNHUB_API_KEY` | Fallback only: <https://finnhub.io> |

LongBridge can satisfy overseas market data through either:

- `LONGPORT_APP_KEY`, `LONGPORT_APP_SECRET`, and `LONGPORT_ACCESS_TOKEN`;
- or an installed and authenticated LongBridge CLI session where
  `longbridge auth status` is valid.

### Optional API Groups

| API group | Environment variables | Setup URL | Unlocks | If skipped |
|---|---|---|---|---|
| `research_search` | `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://app.tavily.com>, <https://qveris.ai/docs> | search expansion and source discovery | use agent-native search; fail closed if freshness cannot be proven |
| `document_parse` | `MINERU_API_KEY` | <https://mineru.net/apiManage/docs> | complex PDF/report parsing | use native file reading or user-provided text |
| `market_intel` | `JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://www.jin10.com/> and search provider URLs | news, macro events, theme catalysts | weaker provider-backed intelligence |
| `external_push` | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID` | <https://open.feishu.cn> | confirmed Feishu delivery | output stays in chat or workspace |

## Presets

| Preset | Use case |
|---|---|
| `quick-research` | one-off research and evidence collection |
| `daily-desk` | morning/nightly market desk workflow |
| `portfolio-desk` | holdings, trade ledger, risk review, and advice tracking |
| `report-review` | report evidence capture and outcome alignment |
| `full-institutional` | full research, market, portfolio, validation, and reporting loop |

Presets are default operating profiles, not feature gates. All public skills
remain available after any preset is selected.

## Installation

Install Codex native skills:

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

Install Claude Code native skills:

```bash
python3 adapters/claude-code/install.py
```

Codex and Claude Code install:

- `.aegis-alpha-core`: shared canonical source;
- `aegis-alpha`: aggregate conductor skill;
- `aegis-alpha-<public-skill>`: native directories for each public skill.

Symlinks are used by default. Use `--link-mode copy` when symlinks are unavailable.

## Initialization

After installation, ask your agent:

```text
Use $aegis-alpha to initialize
```

or:

```text
Use $aegis-alpha-initialization to continue initialization
```

The wizard will confirm:

1. preset;
2. required `market_data`;
3. optional API groups to configure, skip, or disable;
4. whether to run an initial prewarm now or defer it to daily jobs;
5. heartbeat / daily automation;
6. portfolio source and holdings state;
7. final review.

## Generating Reports

After initialization, ask:

```text
Use $aegis-alpha to generate today's report
```

Typical flow:

1. check initialization state;
2. run or validate prewarm freshness;
3. read market data;
4. collect market intelligence;
5. analyze macro regime and risk budget;
6. analyze theme rotation and ThemeSurfer gate;
7. review portfolio if holdings are complete;
8. generate a research-only report.

If the portfolio only contains symbols without quantity, cost basis, market
value, or weight, the report must treat it as a watchlist rather than a known
portfolio.

## Validation

Run local acceptance:

```bash
python3 skills/aegis-alpha/scripts/bootstrap_runtime.py --dry-run
python3 skills/aegis-alpha/scripts/provider_resolver.py --capability research_search --profile /dev/null
python3 tools/audit_capabilities.py --output-dir audit
python3 tools/check_public_skill_visibility.py --output-dir audit
python3 tools/check_public_contracts.py --output-dir audit
python3 tools/check_pipeline_integrity.py --output-dir audit
python3 tools/smoke_portfolio_position_research.py --output-dir audit
python3 tools/smoke_investment_closed_loop.py --output-dir audit
python3 tools/check_final_acceptance.py --audit-dir audit
```
