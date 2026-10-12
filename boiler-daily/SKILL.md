---
name: boiler-daily
description: 每日文献雷达。用户说"今日论文推荐""过去N天论文""每日推荐"时触发标准模式；说"找XX方向论文""Nature/Science正刊""专项推荐"时触发专项模式。自动抓取→评分→批量生成粗读卡+精读笔记→带全量wikilink的Obsidian推荐笔记，且每次不与历史重复。
---

# 每日文献雷达

## 配置加载
唯一硬编码路径：`D:\lunwen\boiler-research-system\config\user-config.json`

派生变量（后续步骤统一使用，不再硬编码）：
```
project_dir = D:\lunwen\boiler-research-system
vault       = config.paths.obsidian_vault          # D:/lunwen/论文阅读
system_dir  = {vault}/90_系统
daily_dir   = {vault}/00_每日推荐
quick_dir   = {vault}/20_粗读卡
seen_path   = {system_dir}/seen_papers.json        # 历史去重文件
tmp_json    = {system_dir}/tmp_papers.json         # 当次抓取结果
```

---

## 模式判断

| 用户说的 | 触发模式 |
|---------|---------|
| "今日推荐""每日推荐""过去N天论文" | **标准模式**（全域7方向，多源抓取） |
| "找XX方向""只看CFD""只看LLM-Agent" | **标准模式 + `--domains-filter`** |
| "Nature/Science正刊""顶刊推荐" | **专项模式**（`fetch_nature_targeted.py`） |
| "多智能体+交叉学科""CFD+数字孪生" | **专项模式 + `--directions`** |
| "再找XX篇""补充推荐""不和之前重复" | 任意模式 + `--exclude-seen` 自动去重 |

---

## 标准模式执行流程

### Step 1: 抓取论文

```powershell
# 每日默认（昨天的论文）
python {project_dir}/scripts/fetch_papers.py \
  --days 1 \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen

# 指定时间范围
python {project_dir}/scripts/fetch_papers.py \
  --start-date YYYY-MM-DD --end-date YYYY-MM-DD \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen

# 指定方向（只保留 Boiler 和 CFD 论文）
python {project_dir}/scripts/fetch_papers.py \
  --days 7 \
  --domains-filter Boiler,CFD \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen

# 覆盖推荐总数（用户要50篇）
python {project_dir}/scripts/fetch_papers.py \
  --start-date 2024-01-01 \
  --top-n 50 \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen

# 指定期刊预设（只从工程期刊抓 Crossref）
python {project_dir}/scripts/fetch_papers.py \
  --days 30 \
  --journal-preset engineering \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen
```

**新参数说明：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `--exclude-seen PATH` | 读取历史记录，过滤已推荐论文 | `--exclude-seen {seen_path}` |
| `--update-seen` | 运行后将本次选出论文写入历史记录 | （与 `--exclude-seen` 配合） |
| `--top-n N` | 覆盖 config 的 top_n（推荐总数） | `--top-n 50` |
| `--domains-filter A,B` | 只保留命中指定 domain 的论文 | `--domains-filter Boiler,CFD` |
| `--journal-preset NAME` | Crossref 只查指定期刊组 | `--journal-preset nature` |
| `--extra-keywords kw1,kw2` | 追加额外搜索关键词 | `--extra-keywords "flow control"` |
| `--no-aiaa` | 跳过 AIAA 会议源 | |
| `--no-dblp` | 跳过 DBLP 会议兜底源 | |

**会议源：** OpenReview（ICLR/NeurIPS/ICML/AAAI）+ AIAA 会议 + DBLP 兜底（CVPR/ICCV/ACL/KDD/IJCAI，OpenReview 抓不到接受论文的会，无摘要、按年份过滤）

**期刊预设（`--journal-preset`）可选值：**
- `nature`：Nature 系 + Science 系 + PNAS + Joule（白名单含 Nature Chemistry/Catalysis/Synthesis/Materials/Physics/Sustainability、Nature Reviews Chemistry/Methods Primers、Science Signaling、Energy Material Advances 等新增刊）
- `top`：Nature/Science + Physical Review + Advanced Materials + JCP + JFM
- `engineering`：Applied Energy / Combustion and Flame / Fuel / IEEE TII 等工程期刊
- `cfd`：JCP / Computers and Fluids / Physics of Fluids / JFM 等 CFD 期刊

**Domain 可选值（`--domains-filter`）：**
`Agentic AI and Multi-Agent Systems` / `Intelligent Boiler Operation, Monitoring and Combustion Optimization` / `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling` / `Knowledge-Centric AI Infrastructure`

---

## 专项模式执行流程（Nature/Science + 指定方向）

适用于用户要求特定方向的顶刊论文，与标准模式互不重复。

### Step 1: 专项抓取

```powershell
# 两个方向（A：多智能体+交叉，B：CFD+数字孪生），顶刊来源，20篇，不与历史重复
python {project_dir}/scripts/fetch_nature_targeted.py \
  --start-date 2024-01-01 --end-date 2026-06-15 \
  --exclude-seen {seen_path} \
  --update-seen \
  --out {system_dir}/tmp_targeted.json \
  --top-n 20 \
  --deep-n 5

# 只要方向A（多智能体）
python {project_dir}/scripts/fetch_nature_targeted.py \
  --directions A \
  --top-n 20 \
  --exclude-seen {seen_path} \
  --update-seen \
  --out {system_dir}/tmp_targeted.json
```

**专项参数：**

| 参数 | 说明 |
|------|------|
| `--directions A,B` | A=多智能体+交叉学科；B=CFD+数字孪生；默认 A,B |
| `--top-n N` | 总选出篇数（默认20） |
| `--deep-n N` | 精读上限（默认5） |
| `--exclude-seen PATH` | 历史去重（同标准模式） |
| `--update-seen` | 追加本次结果到历史 |

---

## 历史去重系统（seen_papers.json）

文件位置：`{system_dir}/seen_papers.json`

格式：
```json
{
  "last_updated": "YYYY-MM-DD",
  "papers": [
    {"arxiv_id": "...", "doi": "...", "title": "...", "date_seen": "...", "source": "..."},
    ...
  ]
}
```

**规则：**
- 每次执行 `--exclude-seen + --update-seen` 后自动更新
- 去重键优先级：arxiv_id → DOI → 标题规范化（90%+ 相似视为同篇）
- 不要手动删除此文件，否则历史记录丢失
- 如需重置历史（重新推荐已见论文），删除或清空 papers 数组

---

## Step 2: 批量生成粗读卡笔记

**不使用脚本，由 Claude 逐篇分析摘要并生成。**

读取 `tmp_papers.json` 中所有 `quick_read` 论文，对每篇：

### 摘要分析规则（必须做到，不能用"待读全文确认"）

**一句话总结**（必须包含三要素）：
```
[研究对象/场景] + 提出/分析了 + [具体方法/角度] + 实现/发现了 + [核心结果]
```
示例：`工业 LLM 智能体中，本文提出基于本体论的工具架构，解决语义训练差距，提升跨场景工具调用准确率。`

**研究问题**：从摘要中提炼出作者明确针对的问题，一句话，不复制摘要原句。

**核心方法**：摘要中提到的具体技术手段（如 RAG、PINN、DeepONet、MPC 等），无法判断时写"[方法词]+（待确认细节）"，**禁止留空或写"待读全文确认"**。

**主要结果**：摘要末尾通常有定量或定性结论，提取出来；若摘要无结果则写"摘要未披露，需读全文"。

**可能价值**：结合用户研究方向，具体说明这篇文章能用在哪里。格式：`[我的系统的哪个模块] 可参考此方法，因为 [具体理由]`。示例：`锅炉智能体工具调用模块可参考其本体论设计，解决领域词汇 OOD 问题。`

### 保存规则

- 路径：`{quick_dir}/{主domain全名}/{slug}-粗读.md`
- `{主domain全名}` 按优先级取第一个（必须用以下完整名称之一）：
  1. `Intelligent Boiler Operation, Monitoring and Combustion Optimization`
  2. `Agentic AI and Multi-Agent Systems`
  3. `CFD-Enabled Digital Twins and Physics-Informed Surrogate Modeling`
  4. `Knowledge-Centric AI Infrastructure`
- `domain`: 用**全名数组**，仅写实际相关域，如 `["Agentic AI and Multi-Agent Systems"]`
- `evidence_level: abstract`（粗读固定值，不改）
- 使用 `D:\lunwen\boiler-research-system\templates\粗读卡模板.md` 作为结构参考

**⚠️ 必须在 H1 标题之后、`## 一句话总结` 之前插入以下行（Obsidian 图谱 Paper→Domain 连线的唯一来源）：**
```
所属领域：[[{主domain全名}]]
```
若论文跨两个域，两个 wikilink 并排：`[[域A]] / [[域B]]`

---

## Step 3: 生成每日推荐笔记

写入 `{daily_dir}/YYYY-MM-DD[-标签]-论文推荐.md`（加标签区分多次推荐）

**笔记结构：**
```markdown
---
date: YYYY-MM-DD
tags: [daily-recommend, llm-generated]
domains: [...]
run_type: standard | targeted_nature_science
directions: [...]    # 专项模式时填写
selected: N
deep_read: N
quick_read: N
sources: "..."
---

## 今日概览 / 专项说明
[3-5句：热点方向、刊物分布、阅读建议、不重复声明]

## 🔥 精读推荐（N篇）
### N. [[精读笔记文件名|论文标题]]
- **来源**：xxx | **作者**：xxx
- **链接**：https://...
- **Score**：X.X  ✅ 精读笔记已生成 / ⚠️ 需下载PDF
- **一句话**：摘要首句

---

## 👀 粗读推荐（N篇）
> 点击标题跳转粗读卡笔记

### 🔥 Intelligent Boiler（N篇）
1. [[slug-粗读|标题...]] ⚠️
   - 来源 | domains | score X.X
   - [一句话真实总结，包含方法+结果，不复制摘要原句]

### 🤖 Agentic AI（N篇）
...

---
## 💤 跳过原因
[≤5条，含API失败/历史去重信息]

---
## 📋 操作清单
- [ ] 精读N：[[笔记名]] — 说明
- [ ] 下载PDF：doi链接
```

**wikilink 规则：**
- 精读笔记（已由 boiler-reader 生成）：`[[文件名|标题]]`
- 粗读卡：`[[{slug}-粗读|标题前52字]]`
- 需下载PDF的精读：`*标题*（待精读）`+ 操作清单中列DOI

---

## Step 4: 对精读候选触发 boiler-reader

对 `deep_read` 中**有 arXiv 链接**的论文调用 `/boiler-reader 精读`，上限为配置的 `auto_deep_read_max`（默认5）。
无摘要 / 需下载PDF 的期刊论文**跳过**，在操作清单中标注待下载。

---

## Step 5: 刷新索引

```powershell
python {project_dir}/scripts/update_graph.py --refresh-index
```

---

## 规则约束

- **历史去重**：每次必须带 `--exclude-seen {seen_path} --update-seen`，确保跨次不重复
- **多次推荐同一天**：用文件名后缀区分，如 `2026-06-15-Nature专项推荐.md`
- domain 用短名数组，frontmatter `domain: [A, B]`
- 精读数量不超过 `auto_deep_read_max`（标准）或 `--deep-n`（专项）
- 所有链接必须是真实可达的 doi.org 或 arxiv.org 格式
- 无摘要论文标注"仅标题判断"，粗读卡仍生成
