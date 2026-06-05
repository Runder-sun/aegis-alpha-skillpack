---
name: mineru-extract
description: "信息搜集解析兜底层：用 MinerU 官方 API 解析 URL、PDF、Office 或图片为 Markdown。"
metadata:
  openclaw:
    skillKey: mineru-extract
    packageProfile: info-gathering-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: information-retrieval
---

# mineru-extract

`mineru-extract` 是信息搜集 skill 栈的高保真解析兜底层，负责调用 MinerU 官方 API。
它通常由 `content-extract` 间接使用，也可以直接执行文档解析。

## Commands

### parse-documents
批量解析 URL 列表，返回 MCP-aligned JSON 合同，适合流水线或二次总结。

### extract-url
低层单 URL 解析入口，直接调用 MinerU 官方任务接口并下载结果产物。
