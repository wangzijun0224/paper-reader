---
name: boiler-reader
description: 单篇论文深度阅读（非Zotero来源）。输入arXiv链接/ID、DOI、本地PDF路径或论文标题。用户说"精读""详细分析""读一下这篇"时触发完整模式；"粗读""快速看""摘要"触发速读模式；Zotero来源的论文请用 boiler-zotero 技能。
context: fork
allowed-tools: Bash, Read, Write, Edit, WebFetch, WebSearch, Glob, Grep
---

# 论文阅读助手

## Step 0: 读配置

唯一硬编码路径（迁移时只需改这一行）：
```
CONFIG = D:\lunwen\boiler-research-system\config\user-config.json
```

读取后派生所有变量：
```
vault          = config.paths.obsidian_vault
notes_dir      = {vault}/{config.paths.paper_notes_folder}   # 10_精读笔记
quick_dir      = {vault}/{config.paths.quick_notes_folder}   # 20_粗读卡
survey_dir     = {vault}/{config.paths.surveys_folder}       # 30_综述
templates_dir  = {CONFIG所在目录的上级}\templates
template_深读  = {templates_dir}\精读笔记模板.md
template_综述  = {templates_dir}\综述模板.md
template_粗读  = {templates_dir}\粗读卡模板.md
graph_script   = {CONFIG所在目录的上级}\scripts\update_graph.py
```

后续步骤统一使用上述变量，不再出现任何硬编码路径。

## 四个核心域（frontmatter domain 字段必须用以下全名）

| 域全名 | 核心范围 |
|--------|---------|
| `Agentic AI and Multi-Agent Systems` | LLM 自主智能体、多智能体、MARL、工具调用、自动科研、代码生成、仿真智能体 |
| `Intelligent Boiler Operation, Monitoring and Combustion Optimization` | 锅炉燃烧优化、配风、NOx、磨煤机、结焦、故障诊断、早期预警；以及为解决锅炉问题所用的 RL/MPC/贝叶斯/时序/异常检测等方法 |
| `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling` | CFD 仿真与自动化、降阶模型（POD/DMD）、代理模型、PINN/FNO/DeepONet、实时流场预测、数字孪生架构 |
| `Knowledge-Centric AI Infrastructure` | 知识图谱、本体、RAG、GraphRAG、文献知识库、CFD 案例库、智能体记忆基础设施、知识组织 |

## 知识图谱规范（写笔记时必须遵守）

### 域分类规则（严格执行）

**`{{domain_wikilinks}}` 填写规则**：
- 只填论文**实质内容**涉及的域，不填"沾边"或"可能相关"
- 通常 1 个域，跨领域才填 2 个，极少数填 3 个
- 格式：`[[Agentic AI and Multi-Agent Systems]]`（单域）
- 这些 wikilink 在 Obsidian 图谱中创建 Paper → 域 连线

**判断标准（按主贡献分类，不按方法分类）**：
| 信号 | 归属 |
|------|------|
| 主贡献是 LLM/Agent/多智能体系统本身 | Agentic AI and Multi-Agent Systems |
| 主贡献是解决锅炉燃烧/运行/监控问题（无论用什么算法） | Intelligent Boiler Operation, Monitoring and Combustion Optimization |
| 主贡献是 CFD、降阶模型、代理模型、神经算子、数字孪生构建 | CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling |
| 主贡献是 RAG/知识图谱/知识组织/记忆基础设施 | Knowledge-Centric AI Infrastructure |

**跨域举例**：
- "用 PINN 建锅炉代理模型" → 主贡献是代理建模 → Domain 3；"锅炉" 仅是应用场景
- "用 LLM 做 CFD 工作流自动化" → 若主贡献是 Agent 架构 → Domain 1；若主贡献是 CFD 工作流本身 → Domain 3
- "Offline RL 优化燃烧配风" → 主贡献是解决锅炉问题 → Domain 2（不单独归 RL 域）
- "GraphRAG 辅助锅炉故障诊断" → 若主贡献是 GraphRAG 架构 → Domain 4；若主贡献是诊断性能 → Domain 2

### 子域规则

**`{{subfield_wikilinks}}` 填写规则**：
- 子域比域更细，可以**跨越不同大域**（交叉学科论文很常见）
- 格式：`[[多智能体强化学习]]`，1-3 个
- 若子域页不存在，**按需创建**（懒创建）：在 `域/子域/{名称}.md` 写 2-3 行说明该子域的范围即可，**不需要 parent_domain 字段**
- 若无明显子域，留空

### 论文间连接

**section 10 相关工作**（精读）用 `[[论文文件名]]` 格式，不用纯文本
→ 创建 Paper→Paper 连线，是图谱中"方法演进"的依据

写完后执行 Step 5 同步 `graph_data.json`。

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

**保存路径规则（所有来源统一，不区分 Zotero/arXiv/日常）**：

| 类型 | 路径 |
|------|------|
| 研究论文·精读 | `10_精读笔记/{主domain}/{标题缩写}.md` |
| 研究论文·粗读 | `20_粗读卡/{主domain}/{标题缩写}-粗读.md` |
| 综述论文·任意深度 | `30_综述/{主domain}/{标题缩写}-综述.md` |

主 domain 优先级（用于确定子目录名，必须用以下全名之一）：
1. `Intelligent Boiler Operation, Monitoring and Combustion Optimization`
2. `Agentic AI and Multi-Agent Systems`
3. `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling`
4. `Knowledge-Centric AI Infrastructure`

保存路径示例：`{notes_dir}/Agentic AI and Multi-Agent Systems/MAKA-论文标题缩写.md`

**研究精读** → 严格按 `精读笔记模板.md`，文件 ≥ 80 行
- Zotero 来源额外加 frontmatter：`zotero_key: {item_key}`, `source: Zotero`

**研究粗读** → 按 `粗读卡模板.md`

**综述（精读或粗读）** → 按 `综述模板.md`
- 精读：填全部章节；粗读：只填核心信息表 + 方法时间线 + 文献池

## Step 5: 更新知识图谱
```powershell
python D:\lunwen\boiler-research-system\scripts\update_graph.py --vault "D:/lunwen/论文阅读" --note "{笔记完整路径}"
```

## 错误处理
- PDF 获取失败 → fallback 到摘要级分析，注明"仅摘要，未读全文"
- 公式无法确认 → 写"公式待人工确认"，不捏造
- 架构图无法获取 → section 5.1 留空，不强制

---

## 附录：综述精读增强流程（必须执行）

当论文被判定为综述、survey、review、overview、perspective、tutorial 或 state-of-the-art 时，不要按普通研究论文的“方法-实验-结果”模板简单摘要。综述阅读的目标是产出一张可复用的领域地图，必须额外完成以下步骤：

### S1. 先读结构，不先写摘要

优先读取并记录：
- abstract、introduction 最后一段、contribution/organization 段。
- 目录或一级/二级标题。
- taxonomy / classification / framework / roadmap / timeline 相关图表。
- summary、discussion、challenges、future perspectives、conclusion。
- 综述表格，包括方法对比表、应用表、benchmark 表、open problems 表。

### S2. 重建 taxonomy

在笔记中必须用表格或树状结构重建作者的分类法，至少包含：
- 一级分类和二级分类。
- 每类方法的核心思想。
- 每类代表文献或代表算法。
- 优点、局限、适用场景。
- 作者明显偏好的路线，以及偏好的理由。

如果原文有多张 taxonomy 图（例如 preliminaries、intrusive methods、non-intrusive methods），需要分别重建，不要只写“分为若干类”。

### S3. 抽取代表文献池

综述精读必须建立“文献池”，不要只列本文引用。文献池至少包括：
- 奠基综述或早期代表。
- 每个方法分支的代表论文。
- 作者特别强调的 promising 方法。
- 与用户研究方向最相关、值得后续精读的论文。

每条文献池记录应说明：角色、贡献、局限、是否需要后续精读。若 Vault 中已有对应笔记，使用 `[[笔记文件名]]` wikilink；若没有，先用纯文本标题并标记“待建笔记”。

### S4. 生成方法选择矩阵

综述笔记必须包含一个“如果我要做 X，该选什么路线”的决策表。表格至少包含：
- 任务场景。
- 优先路线。
- 不推荐路线。
- 关键风险。
- 需要验证的数据或实验。

这一步比普通摘要更重要，因为综述的价值在于指导后续选题和系统设计。

### S5. 分离共识、分歧和缺口

必须单独写三类结论：
- 领域共识：多数文献都同意的判断。
- 主要分歧：路线之间的取舍、评价指标不统一、适用范围冲突。
- 研究缺口：缺少 benchmark、缺少真实工程验证、缺少误差/安全/VVUQ、缺少开源代码等。

不要把“局限”写成泛泛的“需要更多研究”。

### S6. 面向用户研究方向做迁移设计

最后必须写“对我的研究的启发”，并且落到可执行层面：
- 可直接借鉴的模块。
- 必须改造的模块。
- 可形成的论文切入点。
- 初步系统架构或实验设计。
- 暂时不值得投入的方向。

对于锅炉、CFD、数字孪生、能源 AI 相关综述，必须明确回答：这篇综述能否帮助构建实时代理模型、数字孪生在线层、仿真自动化或 LLM-Agent 工具链。

### S7. 综述笔记质量自检

完成笔记前检查：
- frontmatter `type: survey-note`，`domain: ["完整领域名"]` 为单行数组。
- 核心信息表包含领域 wikilink。
- 至少一个 taxonomy 表或树。
- 至少一个方法选择矩阵。
- 至少 5 条文献池记录，其中已有笔记尽量用 `[[...]]`。
- 有“共识/分歧/缺口/迁移设计/后续精读清单”。
- 更新知识图谱脚本并确认 `domain=[...]` 非空。
