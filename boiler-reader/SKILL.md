---
name: boiler-reader
description: 单篇论文深度阅读（非Zotero来源）。输入arXiv链接/ID、DOI、本地PDF路径或论文标题。用户说"精读""详细分析""读一下这篇"时触发完整模式；"粗读""快速看""摘要"触发速读模式；Zotero来源的论文请用 boiler-zotero 技能。
context: fork
allowed-tools: Bash, Read, Write, Edit, WebFetch, WebSearch, Glob, Grep
---

# 论文阅读助手

## 配置路径
- 项目目录: `D:\lunwen\boiler-research-system`
- Vault: `D:/lunwen/论文阅读`
- 精读模板: `D:\lunwen\boiler-research-system\templates\精读笔记模板.md`
- 综述模板: `D:\lunwen\boiler-research-system\templates\综述模板.md`
- 粗读模板: `D:\lunwen\boiler-research-system\templates\粗读卡模板.md`
- 输出根目录: `D:/lunwen/论文阅读/60_Zotero导入/`

## 领域短名（frontmatter domain 字段必须用这些短名）
| 短名 | 含义 |
|------|------|
| `Boiler` | 燃煤锅炉 · 燃烧 · NOx |
| `LLM-Agent` | 大模型智能体 · 自主科研 |
| `CFD` | CFD · 燃烧仿真 · 湍流 |
| `DigitalTwin` | 数字孪生 · 软测量 · 故障诊断 |
| `ROM` | 降阶模型 · 代理模型 · PINN |
| `CS-Foundations` | ML/DL · 时序 · RL · MPC |
| `KnowledgeInfra` | 知识图谱 · RAG · 文献工作流 |

## 知识图谱规范（写笔记时必须遵守）
1. **frontmatter `domain`** 用短名数组，如 `domain: ["LLM-Agent", "KnowledgeInfra"]`
2. **核心信息表"所属领域"行**：保留实际所属的 `[[短名]]` wikilink，删除其余
   → 这是 Obsidian 图谱中 Paper→Domain 连接的来源
3. **section 10 相关工作**（精读）/ **section 3/4 代表性工作/关键文献**（综述）/ **section 9 文献池**：
   用 `[[论文文件名]]` 格式填写，不要用纯文本
   → 这是 Obsidian 图谱中 Paper→Paper 连接的来源
4. 写完后运行更新图谱脚本（Step 5），同步 `graph_data.json`

---

## Step 0: 读配置
读项目 `D:\lunwen\boiler-research-system\config\user-config.json`，获取 `paper_notes_folder`、`quick_notes_folder`。

## Step 1: 识别论文 & 获取内容
| 输入 | 处理 |
|------|------|
| arXiv链接/ID | WebFetch HTML版（优先）+ PDF fallback |
| DOI | 先判断是否有arXiv版，再尝试DOI页面 |
| 本地PDF路径 | 直接 Read |
| 标题 | WebSearch → arXiv |

## Step 2: 两层判断：论文类型 × 阅读深度

**第一层：判断论文类型**

| 信号 | 判定为综述 |
|------|-----------|
| 标题含 review / survey / overview / perspective / 综述 / 进展 | ✅ |
| abstract 首句含 "we review" / "this paper reviews" / "systematic review" | ✅ |
| 正文结构以"分类+代表性工作列举"为主，无自有实验数据 | ✅ |
| 否则 | 研究论文 |

**第二层：判断阅读深度**
- 用户明确说"精读" → 精读
- 用户明确说"粗读"/"快速看" → 粗读
- 未指定 → 默认精读

**组合结果 → 4种模式**：

| 类型 | 深度 | 模式 |
|------|------|------|
| 研究论文 | 精读 | **研究精读** |
| 研究论文 | 粗读 | **研究粗读** |
| 综述论文 | 精读 | **综述精读** |
| 综述论文 | 粗读 | **综述粗读** |

## Step 3: 获取语料（优先级）
1. arXiv HTML 全文（WebFetch，质量最高）
2. 本地 PDF（Read 工具直接视觉读取）
3. 摘要 + 关键词（WebFetch DOI/arXiv 摘要页）

## Step 3.5: 架构图识别（仅研究论文精读时执行）

**目标**：找到论文的方法架构图，用视觉读取后填入 section 5.1。

**若输入为本地PDF**：
1. 从全文文字中搜索 "Fig. 1" / "Figure 1" 附近含 "architecture" / "framework" / "overview" / "pipeline" / "proposed" 等词，推断架构图页码（通常第 2–5 页）
2. 用 Read 工具视觉读取对应页：`Read(file_path="{pdf_path}", pages="{推断页码，如 '2-4'}")`
3. 用自然语言描述架构图的核心流程和模块，填入 section 5.1

**若输入为arXiv**：
1. 从 HTML 版找 Fig. 1 的 `<img>` 标签，获取图片 URL
2. 在 section 5.1 插入 `![]({图片URL})` 并描述架构
3. 如果 HTML 无图，用 arXiv PDF（`https://arxiv.org/pdf/{arxiv_id}`）的 Read 读取第 2–5 页

综述论文的分类 taxonomy 图（通常也是 Fig. 1）同样适用此步骤。

**跳过条件**：粗读模式、或无法获取PDF/图片 → 跳过，section 5.1 留空。

## Step 4: 生成笔记

**研究精读** → 严格按 `精读笔记模板.md`
- 重点：方法架构（含架构图）、关键公式、实验结果对比、可迁移点
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{主domain}/{标题缩写}.md`
- 文件 ≥ 80 行

**研究粗读** → 按 `粗读卡模板.md`
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{主domain}/{标题缩写}-粗读.md`

**综述精读** → 按 `综述模板.md`
- 重点：文献分类框架、关键引用（section 3/4 用 `[[]]` 格式）、文献池（section 9 用 `[[]]` 格式）
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{主domain}/{标题缩写}-综述精读.md`

**综述粗读** → 按 `综述模板.md` 的简化版（只填核心信息表 + section 1/2/9）
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{主domain}/{标题缩写}-综述粗读.md`

## Step 5: 更新知识图谱
```powershell
python D:\lunwen\boiler-research-system\scripts\update_graph.py --vault "D:/lunwen/论文阅读" --note "{笔记完整路径}"
```

## 错误处理
- PDF 获取失败 → fallback 到摘要级分析，注明"仅摘要，未读全文"
- 公式无法确认 → 写"公式待人工确认"，不捏造
- 架构图无法获取 → section 5.1 留空，不强制
