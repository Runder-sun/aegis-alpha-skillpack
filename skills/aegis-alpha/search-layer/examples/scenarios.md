# search-layer Examples

## search
- Trigger: 需要联网搜索、对比资料、跟踪 issue/PR 线索
- Invocation: `python scripts/dispatch.py --command search --payload '{"query":"OpenClaw latest config bug","mode":"deep","intent":"status"}'`

## extract-refs
- Trigger: 已知若干 GitHub issue / PR URL，需要抽引用关系
- Invocation: `python scripts/dispatch.py --command extract-refs --payload '{"urls":["https://github.com/openclaw/openclaw/issues/123"]}'`

## fetch-thread
- Trigger: 需要深抓单个 issue / PR / 讨论串正文和评论
- Invocation: `python scripts/dispatch.py --command fetch-thread --payload '{"url":"https://github.com/openclaw/openclaw/issues/123","format":"json"}'`
