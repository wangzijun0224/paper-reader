---
name: boiler-research-system
description: 锅炉科研文献工作流，覆盖多来源论文检索与约30篇每日推荐、最多5篇精读、固定日期范围检索、单篇粗读/精读、Zotero只读处理、Obsidian Vault检索、综述生成、索引和知识图谱维护。用户提到今日论文推荐、指定日期论文、锅炉/CFD/数字孪生/ROM/LLM-Agent论文阅读、Zotero文献、已有笔记问答、生成综述或更新索引时使用。
---

# 锅炉科研文献系统

将当前目录视为项目根目录。默认使用中文。

## 开始前

1. 读取 `config/user-config.json`，获取路径、推荐数量、评分和来源参数。
2. 不输出或转述 `api_keys` 字段。
3. 只读取当前任务需要的子工作流：
   - 每日推荐或日期范围检索：`skills/boiler-daily/SKILL.md`
   - 单篇粗读、精读或综述摘录：`skills/boiler-reader/SKILL.md`
   - Zotero 单篇或 Collection：`skills/boiler-zotero/SKILL.md`
   - 基于已有笔记生成综述：`skills/boiler-survey/SKILL.md`
   - Vault 检索问答：`skills/boiler-vault/SKILL.md`

## 路由

### 论文发现与每日推荐

- 用户说“今日论文推荐”“最近 N 天论文”时，运行相对日期流程。
- 用户指定开始和结束日期时，使用 `--start-date` 和 `--end-date`。
- 推荐总数、最低分和精读上限只从配置读取；默认约 30 篇，最多 5 篇精读。
- 用户明确要求查找论文或生成推荐时，视为允许访问配置启用的外部文献来源。
- 只要求配置、说明、代码修改或 Vault 问答时，不访问外部来源。

### 单篇论文阅读

- 未指定阅读深度时先粗读，不自动升级精读。
- 粗读主要依据元数据和摘要。
- 精读时读取方法、实验、结论、局限及必要公式，并使用 `templates/精读笔记模板.md`。
- 摘要证据不得写成全文结论；公式无法确认时写“公式待人工确认”。
- 写笔记时默认新建草稿，不覆盖已有笔记。

### Zotero

- 只读访问 SQLite，使用 `scripts/zotero_helper.py`。
- 证据优先级：批注和高亮、全文缓存、本地 PDF。
- 不直接写 Zotero 数据库。

### Vault 与综述

- Vault 问答只使用 Vault 已有内容。
- 证据不足时明确写“Vault 中未找到足够依据”。
- 综述中的确定性结论必须能追溯到已有笔记。
- 写入笔记后使用 `scripts/update_graph.py --note` 更新图谱；需要时运行 `--refresh-index`。

## 字段

文献笔记遵循工作区 `config/field_schema.yaml`：

- 多领域字段使用 `domain`。
- 方法字段使用 `algorithm`。
- 必须标明 `evidence_level`、`status`、`created` 和 `updated`。
- 区分原文事实、分析推断和待确认内容。

## 边界

- 不自动执行论文代码。
- 不运行 OCR，除非用户明确要求。
- 不连接 CFD/Fluent、工业控制系统或在线生产环境。
- 不实施模型自更新或上线。

