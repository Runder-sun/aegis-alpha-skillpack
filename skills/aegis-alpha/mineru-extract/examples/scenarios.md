# mineru-extract Examples

## parse-documents
- Trigger: 批量解析 URL / PDF / Office 链接为 Markdown 产物
- Invocation: `python scripts/dispatch.py --command parse-documents --payload '{"file_sources":["https://example.com/doc.pdf"],"emit_markdown":true}'`

## extract-url
- Trigger: 需要直接调用 MinerU 官方 API 解析单个 URL
- Invocation: `python scripts/dispatch.py --command extract-url --payload '{"url":"https://example.com/report.pdf","model":"pipeline"}'`
