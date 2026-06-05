---
name: content-extract
description: "信息搜集内容抽取层：把网页 URL 转成可读 Markdown，并在普通抓取不稳时走 MinerU 兜底。"
metadata:
  openclaw:
    skillKey: content-extract
    packageProfile: info-gathering-v1
    requires:
      bins: []
  hermes:
    internal: true
    facade: information-retrieval
---

# content-extract

`content-extract` 属于信息搜集 skill 栈，负责把网页 URL 归一化为可复查的 Markdown 产物。
它默认调用本地的 MinerU 封装脚本，适合与 `search-layer` 联用。

## Commands

### extract-url
提取单个网页 URL，返回统一的 JSON 合同：正文 markdown、产物路径、来源列表与失败备注。
