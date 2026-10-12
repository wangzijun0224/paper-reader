---
name: boiler-zotero
description: Zotero文献处理。支持两种模式：①单篇阅读（精读/粗读/综述）——用户说"读一下Zotero里的{标题}""精读{作者}的论文"时触发；②批量处理——用户说"批量处理{collection}""处理Zotero里的{分类}"时触发。
---

# Zotero 文献处理

## Step 0: 读配置

唯一硬编码路径（迁移时只需改这一行）：
```
CONFIG = D:\lunwen\boiler-research-system\config\user-config.json
```

读取后派生所有变量：
```
vault          = config.paths.obsidian_vault
zotero_db      = config.paths.zotero_db
zotero_storage = config.paths.zotero_storage
notes_dir      = {vault}/{config.paths.paper_notes_folder}   # 10_精读笔记
quick_dir      = {vault}/{config.paths.quick_notes_folder}   # 20_粗读卡
survey_dir     = {vault}/{config.paths.surveys_folder}       # 30_综述
templates_dir  = {CONFIG所在目录的上级}\templates
template_深读  = {templates_dir}\精读笔记模板.md
template_综述  = {templates_dir}\综述模板.md
template_粗读  = {templates_dir}\粗读卡模板.md
graph_data     = config.paths.graph_data
```

后续步骤统一使用上述变量，不再出现任何硬编码路径。

## 四个核心域（frontmatter domain 字段必须用以下全名）

| 域全名 | 核心范围 |
|--------|---------|
| `Agentic AI and Multi-Agent Systems` | LLM 自主智能体、多智能体、MARL、工具调用、自动科研 |
| `Intelligent Boiler Operation, Monitoring and Combustion Optimization` | 锅炉燃烧/运行/监控/诊断，以及为此使用的 RL/MPC/贝叶斯/时序等方法 |
| `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling` | CFD 仿真、降阶模型、PINN/FNO/DeepONet、代理模型、数字孪生架构 |
| `Knowledge-Centric AI Infrastructure` | 知识图谱、RAG、GraphRAG、知识库、智能体记忆基础设施 |

## 知识图谱规范（写笔记时必须遵守）
1. **frontmatter `domain`** 用域全名数组，如 `domain: ["Agentic AI and Multi-Agent Systems", "Knowledge-Centric AI Infrastructure"]`
2. **核心信息表"所属领域"行**：保留实际所属的 `[[域全名]]` wikilink，删除其余  
   → 这是 Obsidian 图谱中 Paper→Domain 连接的来源
3. **section 10 相关工作**（精读）/ **section 3 代表性工作**（综述精读）/ **section 9 文献池**：  
   用 `[[论文文件名]]` 格式填写，不要用纯文本  
   → 这是 Obsidian 图谱中 Paper→Paper 连接的来源
4. 写完后运行更新图谱脚本（A5步骤），同步 `graph_data.json`

---

## 模式 A：单篇阅读（精读 / 粗读）

### A1. 查找论文 + 获取元数据

**优先尝试数据库**（可获取元数据 + 批注）：
```powershell
python D:\lunwen\boiler-research-system\scripts\zotero_helper.py info --title "{标题关键词}" --db "D:/zetero/zotero.sqlite" --storage "D:/zetero/storage"
```
返回：`item_key`, `title`, `doi`, `abstract`, `date`, `pdf_paths`, `cache_paths`, `highlights`

**若数据库被锁（Zotero 正在运行）→ 不报错，直接降级**：
- 在 `D:/zetero/storage` 中用文件名关键词搜索 PDF 和 `.zotero-ft-cache`
- 记录：`annotations: unavailable (Zotero running)` — 内容照常读，批注缺失不影响流程
- **不需要提示用户关闭 Zotero**，继续执行

若未指定标题，先列出所有 collection 让用户选择：
```powershell
python D:\lunwen\boiler-research-system\scripts\zotero_helper.py list-collections --db "D:/zetero/zotero.sqlite"
```

### A2. 两层判断：论文类型 × 阅读深度

**第一层：判断论文类型**

优先从标题/abstract/Zotero item type 判断：

| 信号 | 判定为综述 |
|------|-----------|
| 标题含 review / survey / overview / perspective / 综述 / 进展 | ✅ |
| abstract 首句含 "we review" / "this paper reviews" / "systematic review" | ✅ |
| Zotero item type = `journalArticle` 且期刊为 Chem. Rev. / Prog. Energy / Renewable & Sustainable Energy Reviews 等综述类期刊 | ✅ |
| 正文结构以"分类+代表性工作列举"为主，无自有实验数据 | ✅ |
| 否则 | 研究论文 |

**第二层：判断阅读深度**

- 用户明确说"精读" → 精读
- 用户明确说"粗读"/"快速看" → 粗读
- 未指定 → 根据 `highlights` 数量（>5 → 精读，否则粗读）

**组合结果 → 4种模式**：

| 类型 | 深度 | 模式 |
|------|------|------|
| 研究论文 | 精读 | **研究精读** |
| 研究论文 | 粗读 | **研究粗读** |
| 综述论文 | 精读 | **综述精读** |
| 综述论文 | 粗读 | **综述粗读** |

### A3. 获取语料（优先级）
1. Zotero 批注和高亮（`highlights`，仅数据库可用时）
2. `.zotero-ft-cache` 全文缓存（直接读取，无需数据库）
3. 本地 PDF（`pdf_paths`）→ 用 Read 工具直接读取
4. arXiv HTML（若有 arxiv_id）→ 用 WebFetch 获取

### A3.5. 架构图识别（仅研究论文精读时执行）

**目标**：找到论文的方法架构图，用视觉读取后填入 section 5.1。

**步骤一：优先检查 Zotero storage 目录下的图片文件**
```powershell
Get-ChildItem "D:/zetero/storage/{item_key}/" -Include "*.png","*.jpg","*.jpeg" | Select-Object Name
```
若存在图片文件（用户已手动截图），直接用 Read 工具读取并描述。

**步骤二：若无图片，从缓存文本定位架构图页码**

在 `.zotero-ft-cache` 文字中搜索以下模式，推断架构图所在页：
- `"Fig. 1"` / `"Figure 1"` 附近出现 `"architecture"` / `"framework"` / `"overview"` / `"pipeline"` / `"proposed"` 等词
- 架构图通常在论文第 2–5 页

**步骤三：用 Read 工具视觉读取 PDF 对应页**
```
Read(file_path="{pdf_path}", pages="{推断页码，如 '2-4'}")
```
Read 工具会以图像方式呈现 PDF 页面，直接看到图。

**步骤四：将视觉理解写入笔记**
- 用自然语言描述架构图的核心流程和模块
- 如果有图片文件，在 section 5.1 插入 `![[文件名|700]]`
- 综述论文的分类 taxonomy 图（通常也是 Fig. 1）同样适用此步骤

**跳过条件**：粗读模式、或 PDF 不存在且无缓存 → 跳过，section 5.1 留空。

### A4. 生成笔记

**保存路径（不区分 Zotero/arXiv/日常，与其他来源完全一致）**：

| 类型 | 路径 |
|------|------|
| 研究论文·精读 | `{notes_dir}/{主domain全名}/{标题缩写}.md` |
| 研究论文·粗读 | `{quick_dir}/{主domain全名}/{标题缩写}-粗读.md` |
| 综述论文·任意深度 | `{survey_dir}/{主domain全名}/{标题缩写}-综述.md` |

**`{主domain全名}` 必须从以下四个名称中选一个（文件夹已按此命名）**：
- `Intelligent Boiler Operation, Monitoring and Combustion Optimization`
- `Agentic AI and Multi-Agent Systems`
- `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling`
- `Knowledge-Centric AI Infrastructure`

优先级：Boiler域 > Agentic AI域 > CFD域 > Knowledge域

所有 Zotero 来源额外加：`zotero_key: {item_key}`, `import_source: Zotero`
（注意：不要用 `source: Zotero`，`source` 字段已被期刊/会议名占用，重复会导致 YAML 解析失败）

**研究精读** → 按 `D:\lunwen\boiler-research-system\templates\精读笔记模板.md`
- 重点：方法架构、关键公式、实验结果对比表、可迁移点

**研究粗读** → 按 `D:\lunwen\boiler-research-system\templates\粗读卡模板.md`

**综述（精读）** → 按 `D:\lunwen\boiler-research-system\templates\综述模板.md`，填全部章节

**综述（粗读）** → 按综述模板简化版，只填：综述范围、分类框架（一级目录）、关键引用（≤3篇）、对我的价值

### A5. 更新知识图谱
```powershell
python D:\lunwen\boiler-research-system\scripts\update_graph.py --vault "D:/lunwen/论文阅读" --note "{笔记完整路径}"
```

---

## 模式 B：批量处理 Collection

### B1. 读取 Collection
```powershell
python D:\lunwen\boiler-research-system\scripts\zotero_helper.py list-collection --name "{分类名}" --db "D:/zetero/zotero.sqlite"
```
输出：条目列表（`item_key`, `title`, `doi`, `abstract`, `date`, `pdf_keys`）

若不知道 collection 名称，先列出：
```powershell
python D:\lunwen\boiler-research-system\scripts\zotero_helper.py list-collections --db "D:/zetero/zotero.sqlite"
```

### B2. 断点续传
读取 `{输出目录}/_进度记录.md`，过滤已处理（✅成功/⚠️跳过）条目，生成待处理队列。

### B3. 逐篇处理（串行，同模式A步骤A1-A5）
批量模式对每篇独立执行 A2 两层判断（类型×深度），默认深度为精读。每篇完成后立即追加进度：
```
- [x] {timestamp} | {状态} | {item_key} | {标题}
```

### B4. 汇报
输出：成功N篇，失败N篇，跳过N篇，新增知识图谱节点N个。

---

## 约束
- 不存储 Zotero 会话/Cookie/密码
- PDF 不存在且无网络版本 → 标记⚠️跳过
- 批量模式单次不超过 20 篇（避免 context 过长）
- 单篇模式无数量限制

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
