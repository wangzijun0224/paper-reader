---
name: boiler-daily
description: 每日文献雷达。用户说"今日论文推荐""过去N天论文""每日推荐"时触发。自动从arXiv+OpenAlex抓取→多域评分→分类精读/粗读→生成Obsidian推荐笔记。
---

# 每日文献雷达

## 配置加载
先读项目 `config/user-config.json`。推荐数量、最低分、精读阈值、精读上限和全部路径只从该文件读取，不在 Skill 中重复定义。

## 执行流程

### Step 1: 抓取论文

相对时间范围：
```powershell
python {项目目录}/scripts/fetch_papers.py --days {N} --out {Vault}/{system_folder}/tmp_papers.json
```

固定时间范围：
```powershell
python {项目目录}/scripts/fetch_papers.py --start-date 2026-05-01 --end-date 2026-05-31 --out {Vault}/{system_folder}/tmp_papers.json
```

只给 `--start-date` 时结束日期默认为今天；未给起止日期时使用 `--days`，再回退到 `daily_papers.default_days`。

输出：`tmp_papers.json`，每条包含 title/abstract/doi/arxiv_id/source/score/domains[]

### Step 2: 阅读深度分类
直接读取脚本生成的 `deep_read` 和 `quick_read`：
- 推荐总数由 `daily_papers.top_n` 决定，默认约 30 篇。
- 精读上限由 `daily_papers.auto_deep_read_max` 决定，最多 5 篇。
- 最低分、普通精读阈值和跨领域精读阈值均从配置读取。

### Step 3: 生成每日推荐笔记
写入 `{Vault}/{daily_papers_folder}/YYYY-MM-DD-论文推荐.md`

**笔记结构：**
```markdown
---
date: YYYY-MM-DD
tags: [daily-recommend, llm-generated]
domains: [覆盖的domain列表]
---
## 今日概览
[3-5句：今日热点方向、质量分布、阅读建议]

## 🔥 精读推荐（N篇）
### [[论文标题]]
- 来源/作者/链接/domains
- 一句话贡献
- 核心方法要点（3条）
- 关键结果

---

## 👀 粗读推荐（N篇）
### 论文标题 [doi/arxiv链接]
- 来源 | domains | score
- 一句话摘要

---
## 💤 跳过原因
[简列，不超过5条]
```

### Step 4: 对精读候选触发 boiler-reader
对 `deep_read` 中的论文调用 `/boiler-reader`，不得超过配置中的精读上限。

### Step 5: 刷新索引
```powershell
python {项目目录}/scripts/update_graph.py --refresh-index
```

## 规则约束
- 一篇论文可属于多个 domain，文献笔记 Frontmatter 使用 `domain: [A, B]`
- 精读数量不得超过 `daily_papers.auto_deep_read_max`
- 所有论文链接必须是真实可达的（doi.org或arxiv.org格式）
- 粗读只写标题+来源+domains+一句话，不展开
- 没有摘要的论文只做title-level判断，需标注"仅标题判断"
