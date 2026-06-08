# Aegis Alpha

Aegis Alpha is an AI investment research skillpack. It helps an agent collect
market evidence, understand market regime, review themes and portfolios, and
produce research reports. It is designed for research and paper planning only.
It does not place trades, authorize live orders, or replace your own investment
judgment.

This README has two versions:

- [中文](#中文)
- [English](#english)

---

# 中文

## 一句话介绍

Aegis Alpha 是给 Codex、Claude Code 等 AI agent 使用的投资研究技能包。你可以把它理解成一个“研究助理工作台”：它负责整理行情、新闻、宏观环境、主题轮动、个股线索、持仓风险和每日报告，但不会替你实盘下单。

## 适合谁

- 想让 AI 每天生成市场研究报告的人。
- 想系统跟踪 A 股、港股、美股、主题行情和持仓风险的人。
- 想把投资想法记录成纸面计划，并持续复盘的人。
- 想让 agent 在缺少关键数据时停止下结论，而不是硬编答案的人。

## 你可以用它做什么

### 1. 生成每日市场报告

你可以让 agent 生成早盘、盘后、晚间或周度报告。报告通常会覆盖：

- 今日市场状态和主要指数表现。
- A 股情绪、涨跌停、连板、炸板、成交和资金面。
- 港股、美股或海外市场的重要变化。
- 热点主题、行业轮动、政策和新闻催化。
- 宏观风险、流动性和市场风险偏好。
- 你的持仓观察和风险提醒。

如果数据不完整，报告会明确写出缺口，不会把“没有数据”说成“没有风险”。

### 2. 做宏观和市场环境判断

Aegis Alpha 可以帮助 agent 判断当前市场更偏进攻、防守还是观望，包括：

- 全球风险偏好。
- 中国宏观和流动性环境。
- A 股情绪温度。
- 行业和概念轮动。
- 当前更适合扩大研究、收缩风险，还是只做观察。

### 3. 跟踪主题和板块周期

它可以把市场热点拆成长期、中期、短期和超短期主题，帮助你观察：

- 哪些主题正在升温。
- 哪些主题可能已经过热。
- 哪些板块开始退潮。
- 短线交易环境是否适合继续进攻。

其中 ThemeSurfer 是一个风险闸门。简单说，当市场环境太差或主题退潮时，它会要求 agent 降低进攻性，甚至只允许观察。

### 4. 筛选和研究个股

你可以让 agent 围绕主题、行业、财务、估值、催化剂或新闻线索筛选股票。它也可以对单个公司做研究，输出：

- 公司业务和叙事。
- 近期催化剂。
- 基本面和估值线索。
- 技术和资金面观察。
- 主要风险和需要继续验证的问题。

### 5. 生成纸面交易计划

Aegis Alpha 只支持纸面计划，不支持实盘执行。它可以帮助你把想法写成清楚的研究计划：

- 为什么关注这个标的。
- 什么条件下才算验证成功。
- 什么条件下计划失效。
- 观察价位、风险点和复盘节点。

这些内容只用于研究和复盘，不是自动下单指令。

### 6. 复盘持仓和风险

如果你提供完整持仓数据，例如数量、成本、市值或权重，agent 可以做组合复盘：

- 持仓集中度。
- 行业和主题暴露。
- 单票风险。
- 组合和当前市场环境是否匹配。
- 哪些持仓需要更多证据支持。

如果你只提供股票名称或代码列表，Aegis Alpha 会把它当成观察清单，不能推断仓位、盈亏或真实风险。

### 7. 跟踪建议生命周期

你可以让 agent 记录某个纸面建议，并在之后持续检查：

- 建议是否还有效。
- 关键价格或事件是否变化。
- 原来的理由是否被证伪。
- 是否应该继续观察、复盘或归档。

### 8. 自动预热和每日任务

初始化时你可以选择是否启用每日自动任务。常见任务包括：

- 每天提前刷新行情和新闻数据。
- 盘中或盘后检查市场状态。
- 定时准备报告素材。
- 在你确认并配置凭证后，把报告推送到外部工具。

自动任务只负责研究数据和报告准备，不会执行交易。

## 开始前需要准备什么

### 必须配置：行情数据

Aegis Alpha 要正常工作，必须有基础行情数据来源。不同市场对应不同配置：

| 市场 | 推荐配置 | 获取地址 | 用途 |
|---|---|---|---|
| A 股/中国市场 | `TUSHARE_TOKEN` | <https://tushare.pro> | A 股行情、指数、日历、资金和基础市场数据 |
| 港股/美股/海外市场 | LongBridge / LongPort | <https://open.longbridge.com/skill/> | 海外行情、报价和历史数据 |
| 海外备用 | `FINNHUB_API_KEY` | <https://finnhub.io> | LongBridge 不可用时的备用行情来源 |

如果没有完成行情数据配置，Aegis Alpha 不能算完整初始化。

### 可选配置

这些配置不是必须的，但会增强对应能力：

| 配置项 | 需要的环境变量 | 获取地址 | 打开后能做什么 | 不配置会怎样 |
|---|---|---|---|---|
| 搜索增强 | `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://app.tavily.com>, <https://qveris.ai/docs> | 更系统地发现资料来源 | 使用 agent 自带搜索能力 |
| 研报/PDF 解析 | `MINERU_API_KEY` | <https://mineru.net/apiManage/docs> | 解析复杂研报和长 PDF | 只能读取普通文件或你提供的文本 |
| 市场新闻和事件 | `JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://www.jin10.com/> 等 | 更稳定地获取新闻、政策、宏观事件 | 依赖 agent 自带搜索，证据不足时停止下结论 |
| 外部推送 | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID` | <https://open.feishu.cn> | 把确认后的报告推送到飞书 | 报告只留在对话或本地工作区 |

## 初始化时会问你什么

第一次使用时，对 agent 说：

```text
使用 $aegis-alpha 初始化
```

agent 应该按步骤向你说明并确认：

1. 你想用哪种模式：一次性研究、每日市场桌面、持仓复盘、报告复盘，或完整研究流程。
2. 是否已经配置 A 股和海外行情数据。
3. 哪些可选 API 要配置，哪些要跳过。
4. 是否现在运行一次数据预热。
5. 是否创建每日自动任务。
6. 是否提供持仓来源。
7. 最后确认初始化结果和仍然缺少的能力。

初始化不是让 agent 偷偷写默认配置。它必须先解释能力和配置项，再让你确认。

## 常用说法

```text
使用 $aegis-alpha 生成今日报告
```

```text
使用 $aegis-alpha 分析我的持仓风险
```

```text
使用 $aegis-alpha 筛选今天 A 股值得研究的主题和个股
```

```text
使用 $aegis-alpha 跟踪这条纸面建议
```

如果你知道具体能力，也可以直接调用：

- `$aegis-alpha-initialization`：初始化和重新配置。
- `$aegis-alpha-market-data`：读取行情数据。
- `$aegis-alpha-market-intel`：整理新闻、政策和市场事件。
- `$aegis-alpha-macro-regime`：判断宏观和市场环境。
- `$aegis-alpha-theme-cycle`：分析主题轮动。
- `$aegis-alpha-equity-screening`：筛选候选股票。
- `$aegis-alpha-equity-research`：研究单个公司。
- `$aegis-alpha-trade-planning`：生成纸面交易计划。
- `$aegis-alpha-portfolio-ops`：持仓和风险复盘。
- `$aegis-alpha-advice-lifecycle`：跟踪纸面建议。
- `$aegis-alpha-pipeline`：运行标准研究流程。
- `$aegis-alpha-execution-automation`：预热、检查和自动任务。
- `$aegis-alpha-quality-gate`：质量检查。
- `$aegis-alpha-quant-validation`：离线回测和策略验证。
- `$aegis-alpha-report-evolution`：报告复盘和演化。
- `$aegis-alpha-information-retrieval`：资料检索和文档处理。

## 安装

Codex：

```bash
python3 adapters/codex/install.py
```

Hermes：

```bash
python3 adapters/hermes/install.py
```

OpenClaw：

```bash
python3 adapters/openclaw/install.py
```

Claude Code：

```bash
python3 adapters/claude-code/install.py
```

Codex 和 Claude Code 会安装一个总入口 `$aegis-alpha`，以及上面列出的细分能力入口。默认使用链接方式安装；如果你的环境不支持链接，可以使用 `--link-mode copy`。

## 安全边界

- Aegis Alpha 只做研究和纸面计划。
- 不会实盘下单。
- 不会授权外部交易系统。
- 不会把缺失数据当成正确信号。
- 不应把 API key、`.env`、持仓、账本、报告、运行缓存或个人账户数据提交到公开仓库。

## 开发者验证

如果你在维护这个仓库，可以运行：

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

## In One Sentence

Aegis Alpha is an investment research skillpack for AI agents such as Codex and
Claude Code. Think of it as a research desk assistant: it helps organize market
data, news, macro conditions, theme rotation, stock ideas, portfolio risk, and
daily reports, but it never places live trades.

## Who It Is For

- Users who want an AI agent to generate daily market research reports.
- Users who track A-shares, Hong Kong stocks, US stocks, themes, and portfolio risk.
- Users who want to record paper trade ideas and review them over time.
- Users who prefer the agent to stop when evidence is missing instead of inventing certainty.

## What You Can Do With It

### 1. Generate Daily Market Reports

You can ask the agent for morning, post-market, nightly, or weekly reports. A
typical report may cover:

- market state and major index moves;
- A-share sentiment, limit-up/down activity, turnover, and capital flow;
- important Hong Kong, US, or overseas market changes;
- hot themes, sector rotation, policy items, and news catalysts;
- macro risk, liquidity, and risk appetite;
- portfolio watch items and risk reminders.

When data is incomplete, the report should show the gap instead of treating
missing evidence as no risk.

### 2. Understand Macro And Market Regime

Aegis Alpha helps the agent judge whether the current environment is more
aggressive, defensive, or watch-only:

- global risk appetite;
- China macro and liquidity conditions;
- A-share market temperature;
- sector and concept rotation;
- whether to expand research, reduce risk, or stay observant.

### 3. Track Themes And Sector Cycles

It can organize market themes across long, medium, short, and ultra-short time
frames, helping you watch:

- which themes are heating up;
- which themes may be crowded or overheated;
- which sectors may be fading;
- whether short-term trading conditions are supportive.

ThemeSurfer is a risk gate. When the environment is weak or themes are fading,
it tells the agent to reduce aggressiveness or keep ideas on watch only.

### 4. Screen And Research Stocks

You can ask the agent to screen stocks by theme, industry, fundamentals,
valuation, catalyst, or news trail. It can also research a single company and
summarize:

- business and narrative;
- recent catalysts;
- fundamental and valuation clues;
- technical and flow observations;
- key risks and open questions.

### 5. Create Paper-Only Trade Plans

Aegis Alpha only creates paper plans. It can help turn an idea into a clear
research plan:

- why the name is being watched;
- what would confirm the thesis;
- what would invalidate it;
- watch levels, risk points, and review checkpoints.

These plans are for research and review only, not executable order instructions.

### 6. Review Portfolio Risk

If you provide complete holdings data, such as quantity, cost basis, market
value, or weight, the agent can review:

- concentration risk;
- industry and theme exposure;
- single-name risk;
- fit between the portfolio and current market conditions;
- holdings that need more evidence.

If you only provide symbols or company names, Aegis Alpha treats them as a
watchlist. It cannot infer position size, PnL, or real portfolio risk.

### 7. Track Advice Over Time

You can ask the agent to record a paper-only recommendation and later check:

- whether it is still valid;
- whether price or event conditions changed;
- whether the original thesis was invalidated;
- whether it should remain active, be reviewed, or be archived.

### 8. Prewarm Data And Run Daily Jobs

During initialization, you can decide whether to enable recurring jobs. Common
jobs include:

- refreshing market and news data before reports;
- checking market state during or after trading hours;
- preparing report inputs on a schedule;
- pushing confirmed reports to external tools after credentials are configured.

Automation is for research data and report preparation only. It does not trade.

## What You Need Before Starting

### Required: Market Data

Aegis Alpha needs a baseline market data source before it is fully initialized:

| Market | Recommended setup | Where to get it | Purpose |
|---|---|---|---|
| A-share / China | `TUSHARE_TOKEN` | <https://tushare.pro> | A-share quotes, indices, calendars, capital flow, and market data |
| Hong Kong / US / overseas | LongBridge / LongPort | <https://open.longbridge.com/skill/> | Overseas quotes and historical data |
| Overseas fallback | `FINNHUB_API_KEY` | <https://finnhub.io> | Backup source when LongBridge is unavailable |

Without market data, Aegis Alpha is not fully initialized.

### Optional Setup

These integrations are optional, but they unlock stronger workflows:

| Setup | Environment variables | Where to get it | What it unlocks | If skipped |
|---|---|---|---|---|
| Search expansion | `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://app.tavily.com>, <https://qveris.ai/docs> | broader source discovery | use the agent's native search tools |
| Report/PDF parsing | `MINERU_API_KEY` | <https://mineru.net/apiManage/docs> | complex research report and PDF parsing | use basic file reading or user-provided text |
| Market news and events | `JIN10_API_KEY`, `TAVILY_API_KEYS`, `QVERIS_API_KEY` | <https://www.jin10.com/> and related provider sites | news, policy, macro events, and catalysts | rely on native search; stop when fresh evidence cannot be proven |
| External push | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`, `FEISHU_CHAT_ID` | <https://open.feishu.cn> | confirmed Feishu report delivery | keep output in chat or local workspace |

## What Initialization Should Ask

After installation, say:

```text
Use $aegis-alpha to initialize
```

The agent should explain and confirm:

1. which mode you want: one-off research, daily market desk, portfolio review, report review, or full workflow;
2. whether A-share and overseas market data are configured;
3. which optional APIs to configure or skip;
4. whether to run one data prewarm now;
5. whether to create daily automation;
6. whether you want to provide a portfolio source;
7. the final initialization result and remaining gaps.

Initialization should not silently write defaults. The agent must explain the
capabilities and setup choices before asking you to confirm.

## Common Prompts

```text
Use $aegis-alpha to generate today's report
```

```text
Use $aegis-alpha to review my portfolio risk
```

```text
Use $aegis-alpha to screen today's A-share themes and stocks worth researching
```

```text
Use $aegis-alpha to track this paper recommendation
```

You can also call a specific capability directly:

- `$aegis-alpha-initialization`: initialization and reconfiguration.
- `$aegis-alpha-market-data`: market data reading.
- `$aegis-alpha-market-intel`: news, policy, and market events.
- `$aegis-alpha-macro-regime`: macro and market regime.
- `$aegis-alpha-theme-cycle`: theme rotation.
- `$aegis-alpha-equity-screening`: candidate stock screening.
- `$aegis-alpha-equity-research`: single-company research.
- `$aegis-alpha-trade-planning`: paper-only trade planning.
- `$aegis-alpha-portfolio-ops`: holdings and risk review.
- `$aegis-alpha-advice-lifecycle`: paper advice tracking.
- `$aegis-alpha-pipeline`: standard research workflows.
- `$aegis-alpha-execution-automation`: prewarm, checks, and automation.
- `$aegis-alpha-quality-gate`: quality checks.
- `$aegis-alpha-quant-validation`: offline backtesting and validation.
- `$aegis-alpha-report-evolution`: report review and improvement.
- `$aegis-alpha-information-retrieval`: source retrieval and document handling.

## Installation

Codex:

```bash
python3 adapters/codex/install.py
```

Hermes:

```bash
python3 adapters/hermes/install.py
```

OpenClaw:

```bash
python3 adapters/openclaw/install.py
```

Claude Code:

```bash
python3 adapters/claude-code/install.py
```

Codex and Claude Code install the main `$aegis-alpha` entry plus the specific
capability entries listed above. Symlinks are used by default. Use
`--link-mode copy` if your environment does not support symlinks.

## Safety Boundaries

- Aegis Alpha is for research and paper planning only.
- It does not place live trades.
- It does not authorize external trading systems.
- It should not treat missing data as a positive signal.
- Do not commit API keys, `.env` files, holdings, ledgers, reports, runtime
  cache, or personal account data to a public repository.

## Developer Validation

Maintainers can run:

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
