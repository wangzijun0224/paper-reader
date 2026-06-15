---
name: boiler-reader
description: 单篇论文深度阅读，支持精读/粗读/综述三种模式。输入arXiv链接、DOI、本地PDF路径、或论文标题。用户说"精读""详细分析""读一下这篇"时触发完整模式；"粗读""快速看""摘要"触发速读模式。
context: fork
allowed-tools: Bash, Read, Write, Edit, WebFetch, WebSearch, Glob, Grep
---

# 论文阅读助手

## Step 0: 读配置
读项目 `config/user-config.json`，提取项目、Vault 和输出目录变量。

## Step 1: 识别论文 & 获取内容
| 输入 | 处理 |
|------|------|
| arXiv链接/ID | WebFetch HTML版（优先）+ PDF fallback |
| DOI | 先判断是否有arXiv版，再尝试DOI页面 |
| 本地PDF路径 | 直接Read |
| 标题 | WebSearch → arXiv |

## Step 2: 判断阅读模式
| 模式 | 触发词 | 输出 |
|------|--------|------|
| **精读** | 默认/"精读"/"详细"/"深度" | 完整结构化笔记（见精读模板） |
| **粗读** | "粗读"/"快速"/"quick"/"摘要" | 粗读卡（150字以内） |
| **综述素材** | "综述"/"加入综述"/"survey" | 提取方法+结论，追加到对应综述文件 |

## Step 3A: 精读笔记生成
严格按 `{项目目录}/templates/精读笔记模板.md`。

**保存路径：** `{Vault}/{paper_notes_folder}/{主domain}/{论文方法名}.md`

**多 domain 处理：** 在 Frontmatter 写 `domain: [D1, D2]`，在主 domain 目录建笔记，其他领域通过索引和双链引用。

**质量要求：**
- 文件 ≥ 80行
- 包含方法核心思想、与已有方法对比、对锅炉/CFD/LLM场景的迁移价值
- 论文中有公式则必须提取（LaTeX格式）
- 论文中有图则尝试从arXiv HTML获取图片URL

**写入后：** 调用 `python {项目目录}/scripts/update_graph.py --note "{笔记路径}"`

## Step 3B: 粗读卡生成
按 `{项目目录}/templates/粗读卡模板.md`，保存到 `{quick_notes_folder}/YYYY-MM/` 下。

## Step 3C: 综述素材追加
定位 `{surveys_folder}/{domain}/{subfield}-综述.md`，在 `## 文献池` 区域追加：
```
### 论文标题 [doi/arxiv]
- 方法：...
- 结论：...
- 迁移到{场景}的价值：...
```

## 错误处理
- PDF获取失败 → fallback到摘要级分析，注明"仅摘要，未读全文"
- 公式OCR失败 → 占位符，不捏造
- 图片获取失败 → 记录URL，不强制嵌入
