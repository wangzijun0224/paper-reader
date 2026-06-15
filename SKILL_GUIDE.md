# 文献雷达系统使用说明

> 适用对象：已安装本系统的用户。在 Claude Code 对话窗口中直接说以下指令即可触发对应 skill。

---

## 系统概览

```
每日自动流程：
  arXiv + HuggingFace + Scopus + Crossref + IEEE + S2 + OpenReview
       ↓ 多域评分 + 去重
  每日30篇推荐（≤5精读 + 25粗读）→ Obsidian 00_每日推荐/
       ↓ 最多5篇精读候选
  精读笔记 → 10_精读笔记/{domain}/
       ↓ 期刊论文手动下载后
  放入Zotero → /boiler-zotero 精读 → 60_Zotero导入/
       ↓ 积累足够笔记后
  /boiler-survey → 30_综述/{domain}/
```

**Vault 路径**：`D:\lunwen\论文阅读\`
**脚本路径**：`D:\lunwen\boiler-research-system\`
**Skills 路径**：`C:\Users\Administrator\.claude\skills\`

---

## 一、每日论文推荐（`/boiler-daily`）

### 触发词

```
今日论文推荐
过去3天论文推荐
最近一周有什么新论文
```

### 输出

生成 `00_每日推荐/YYYY-MM-DD-论文推荐.md`，包含：
- 来源统计（arXiv / HuggingFace / Scopus / Crossref / IEEE）
- 精读队列（≤5篇，自动触发精读）
- 粗读队列（25篇，带一行摘要）
- ⚠️ 需下载标记（Scopus/Crossref/IEEE 来源的期刊论文）

可指定固定时间范围，例如：
```powershell
python scripts/fetch_papers.py --start-date 2026-05-01 --end-date 2026-05-31 --out papers.json
```

推荐总数、最低分、精读阈值和最多精读篇数统一从 `config/user-config.json` 读取。

### 处理期刊论文（有 ⚠️ 标记的）

```
1. 复制 DOI → 东南大学图书馆 / ScienceDirect / IEEE Xplore 下载 PDF
2. PDF 拖入 Zotero
3. 说：精读 Zotero 里的 {论文标题关键词}
```

### 手动触发推荐列表里某篇精读

```
精读推荐列表里第3篇
对 [论文标题] 做精读
```

---

## 二、单篇论文深度阅读（`/boiler-reader`）

### 触发词

| 模式 | 触发词示例 |
|------|-----------|
| **精读**（完整笔记） | `精读 https://arxiv.org/abs/2506.xxxxx` |
| **精读**（完整笔记） | `详细分析这篇论文 [标题]` |
| **粗读**（速读卡片） | `粗读 https://doi.org/10.1016/j.fuel.2026.xxx` |
| **粗读**（速读卡片） | `快速看一下这篇 [标题/链接]` |
| **综述用精读** | `综述 这篇论文 [链接]` |
| **本地PDF** | `精读 D:\下载\paper.pdf` |

### 输出位置

| 模式 | 位置 |
|------|------|
| 精读 | `10_精读笔记/{domain}/{方法名}.md` |
| 粗读 | `20_粗读卡/{方法名}-粗读.md` |

### 多域论文

一篇论文可属于多个领域，frontmatter 自动生成：
```yaml
domain: [CFD, ROM, DigitalTwin]
```

---

## 三、Zotero 文献处理（`/boiler-zotero`）

### 单篇阅读

```
精读 Zotero 里的 CFDAgent 那篇
粗读一下 Zotero 里 Wang 2023 的数字孪生论文
对 Zotero 里的 NOx预测那篇做综述摘录
读一下 Zotero 里的 {任意标题关键词}
```

未指定模式时：有批注>5条 → 精读；否则 → 粗读。

### 批量处理整个 Collection

```
批量处理 Zotero 里的 CFD 分类
处理 Zotero 的 RL 合集（批量精读）
批量读 Zotero 里 LLM+DRL 分类下的论文
```

### 查看 Zotero 中有哪些分类

```
Zotero 里有哪些分类
列出我的 Zotero 文件夹
```

### 输出位置

- 单篇：`60_Zotero导入/{domain}/{标题}.md`
- 批量：`60_Zotero导入/{collection名}/`，含 `_进度记录.md`（断点续传）

---

## 四、综述生成（`/boiler-survey`）

### 触发词

```
生成 CFD 方向的综述
更新 LLM-Agent 综述
整理 ROM 降阶模型方向的文献综述
帮我写一个锅炉NOx控制的综述
```

### 流程

扫描 `10_精读笔记/` + `20_粗读卡/` + `60_Zotero导入/`
→ 时间线 + 方法对比表 + 研究空白
→ 生成 `30_综述/{domain}/{subfield}-综述.md`

### 建议积累量

至少 5 篇精读笔记后再生成综述，效果更好。

---

## 五、Vault 知识图谱检索（`/boiler-vault`）

### 触发词（任何检索问题）

```
找一下关于 NOx 预测的所有笔记
数字孪生和 CFD 有哪些交叉研究
PINN 在燃烧模拟里有什么应用
我读过哪些关于强化学习控制锅炉的论文
{任何研究问题}
```

**只基于你已有的笔记回答**，不会编造内容。

---

## 六、概念笔记（自动 / 手动）

精读论文时遇到新方法会自动创建概念卡片，也可手动触发：

```
帮我记录一下 FNO 这个概念
POD 降阶方法的概念笔记
解释并记录 Agentic RAG
```

**输出位置**：`40_概念库/{类别}/`

10 个分类：锅炉燃烧 / CFD仿真 / 降阶代理模型 / 数字孪生在线智能 / LLM智能体 / 控制优化 / 时序异常检测 / 知识图谱RAG / 深度学习基础 / CFD自动化

---

## 七、每日工作流参考

```
早上：
  → "今日论文推荐"
  → 查看 00_每日推荐/今日.md
  → 精读自动生成在 10_精读笔记/

下载期刊论文（有 ⚠️ 标记）：
  → 复制 DOI → 学校数据库下载 PDF → 拖入 Zotero
  → "精读 Zotero 里的 {标题}"

读到感兴趣的 arXiv 论文：
  → "精读 https://arxiv.org/abs/xxxx"

深入某个方向：
  → "生成 ROM 方向综述"

搜索已有笔记：
  → "找锅炉NOx相关的所有精读笔记"

处理 Zotero 存量文献：
  → "批量处理 Zotero 里的 combustion 分类"
```

---

## 八、配置说明

### 主配置文件

`D:\lunwen\boiler-research-system\config\user-config.json`

| 字段 | 说明 | 修改场景 |
|------|------|---------|
| `keywords` | 搜索关键词列表 | 扩展/缩小搜索范围 |
| `domain_boost_keywords` | 各领域加分关键词 | 调整域识别准确度 |
| `arxiv_categories` | arXiv 分类 | 添加新学科 |
| `auto_deep_read_score_threshold` | 自动精读分数线（默认8.0） | 想要更多/更少精读 |
| `multi_domain_deep_read_score_threshold` | 跨领域论文精读分数线（默认6.5） | 调整交叉论文优先级 |
| `auto_deep_read_max` | 每日最多精读篇数（默认5） | 调整每日精读量 |
| `top_n` | 每日推荐总篇数（默认30） | 调整总推荐量 |
| `min_score` | 进入推荐队列的最低分（默认2） | 控制低相关论文 |
| `default_days` | 未指定日期时的默认回溯天数 | 控制日常检索窗口 |
| `journal_reserved_slots` | 期刊论文保留名额（默认8） | 期刊/预印本比例 |
| `scopus_target_count` | Scopus每日抓取量（默认100） | 控制Scopus调用次数 |

### API Keys

```json
"api_keys": {
  "ieee": "cvxqjyq5f9ewyfsbz8ag6q4p",         // 已配置
  "scopus": "b302b3c1732efc811e93c6ec9d1d8c33", // 已配置
  "semantic_scholar": ""                         // 待填（申请中）
}
```

### 期刊列表

`D:\lunwen\boiler-research-system\scripts\fetch_papers.py` 中的 `JOURNAL_ISSNS` 字典。
新增期刊只需加一行 `"期刊名": "ISSN号"`。

---

## 九、迁移到其他研究领域

> 本系统设计为领域无关，以下是将系统迁移到另一个领域（如医疗AI、材料科学、机器人等）的完整修改清单。

### 必须修改（3个文件）

#### 1. `config/user-config.json` — 核心配置

```json
// 修改搜索关键词
"keywords": ["your keyword 1", "your keyword 2", ...],

// 修改领域列表（最多7个）
"domains": ["DomainA", "DomainB", ...],

// 修改各域加分关键词
"domain_boost_keywords": {
  "DomainA": ["keyword1", "keyword2"],
  "DomainB": ["keyword3", "keyword4"]
},

// 修改 arXiv 分类（去 arxiv.org/search 查对应分类代码）
"arxiv_categories": ["cs.AI", "cs.LG", "eess.SP", ...],

// 修改负面关键词（过滤不相关论文）
"negative_keywords": ["irrelevant topic 1", ...]
```

#### 2. `scripts/fetch_papers.py` — 期刊列表

修改 `JOURNAL_ISSNS` 字典，改为目标领域的核心期刊：
```python
JOURNAL_ISSNS = {
    "Your Key Journal 1": "ISSN号",
    "Your Key Journal 2": "ISSN号",
    ...
}
```
> ISSN 查询：在 journal 官网或 issn.org 查找。

#### 3. `skills/paper-reader/references/concept-categories.md` — 概念分类

替换为目标领域的10个概念类别（格式参考现有文件）：
```markdown
| `1-概念类别A` | 归类标准 | 示例 |
| `2-概念类别B` | 归类标准 | 示例 |
...
```

### 可选修改（按需）

#### 4. Vault 目录结构

修改 `setup_vault.ps1` 中的目录名，重新运行初始化：
```powershell
# 把 Boiler/LLM-Agent/CFD 等改成新领域名
$domains = @("DomainA", "DomainB", "DomainC", ...)
```

#### 5. Skills 中的路径

如果更换了 Vault 路径，需要同步修改 5 个 SKILL.md 文件中的路径：
- `skills/boiler-daily/SKILL.md`
- `skills/boiler-reader/SKILL.md`
- `skills/boiler-zotero/SKILL.md`
- `skills/boiler-survey/SKILL.md`
- `skills/boiler-vault/SKILL.md`

每个文件顶部都有 `## 配置` 部分，集中列出了需要修改的路径。

#### 6. 重命名 Skills（可选）

如果想把 `boiler-*` 改成 `medical-*` 或其他前缀：
1. 重命名 `skills/` 下的4个文件夹
2. 重新复制到 `~/.claude/skills/`
3. 无需修改 SKILL.md 内容

### 迁移检查清单

```
□ user-config.json: keywords / domains / domain_boost_keywords / arxiv_categories
□ fetch_papers.py: JOURNAL_ISSNS（目标领域期刊）
□ concept-categories.md: 10个领域概念分类
□ setup_vault.ps1: 目录名（重新运行）
□ 5个 SKILL.md: paths（如Vault路径变化）
□ API keys: 无需修改（与领域无关）
```

---

## 十、常见问题

**Q: 今天没有论文推荐？**
A: arXiv 周末不更新，改用 `过去3天论文推荐`。

**Q: 期刊论文评分很低（<2分）进不了推荐？**
A: 期刊论文有 `journal_reserved_slots=8` 个保留名额，即使评分低也会进入。如果还是看不到，检查关键词是否覆盖该领域术语。

**Q: 精读太多，token 消耗大？**
A: 提高 `auto_deep_read_score_threshold`（提高门槛）或降低 `auto_deep_read_max`（减少数量）。

**Q: Scopus 抓不到想要的期刊？**
A: 在 `fetch_papers.py` 的 `JOURNAL_ISSNS` 里加该期刊 ISSN。

**Q: IEEE key 还在 waiting？**
A: 通常几小时到1天激活。激活后无需任何操作，下次运行自动生效。

**Q: 想只看某个领域的今日推荐？**
A: 说 `今日 CFD 方向论文推荐` 或 `今日 LLM-Agent 相关论文`，skill 会按 domain 过滤输出。

**Q: 如何备份笔记？**
A: Obsidian Vault (`D:\lunwen\论文阅读\`) 是纯 Markdown 文件，直接用 Git 或 OneDrive 同步即可。

---

---

## 附：目标期刊覆盖范围（54个）

| 类别 | 期刊 |
|------|------|
| **Nature系列** | Nature, Nature Energy, Nature Communications, Nature Machine Intelligence, Nature Chemical Engineering, npj Computational Materials |
| **Science系列** | Science, Science Advances |
| **Cell/RSC** | Joule, Cell Reports Physical Science, Energy and Environmental Science |
| **CFD核心** | Journal of Computational Physics, Computers and Fluids, Physics of Fluids, Journal of Fluid Mechanics, Flow Turbulence and Combustion, Theoretical and Computational Fluid Dynamics, Int. J. Numerical Methods in Fluids, Int. J. Heat and Fluid Flow, AIAA Journal |
| **颗粒/粉体** | Particuology, Powder Technology |
| **燃烧/热工** | Combustion and Flame, Progress in Energy and Combustion Science, Fuel, Applied Thermal Engineering, Int. J. Heat and Mass Transfer, Chemical Engineering Science, Chemical Engineering Journal(CEJ) |
| **能源** | Applied Energy, Energy, Energy Conversion and Management, Renewable and Sustainable Energy Reviews, Energy and AI, Int. J. Hydrogen Energy |
| **AI/控制** | Expert Systems with Applications, Engineering Applications of Artificial Intelligence, Knowledge-Based Systems, Computers and Chemical Engineering, Neurocomputing, Applied Soft Computing |
| **顶级AI期刊** | JMLR, Artificial Intelligence, TMLR |
| **IEEE** | T-IE, T-II, T-EC, T-PS, T-NNLS, T-ITS, T-ASE, T-SMCS, T-CST, T-CYB, T-PAMI, IEEE Access |

*系统版本: 2026-06-15 | 数据源: arXiv + HuggingFace + Scopus(Elsevier) + Crossref + IEEE + Semantic Scholar*
