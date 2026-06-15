# Boiler Research System — Claude Code Skills

锅炉燃烧研究 + LLM文献工作流的 Claude Code 技能集。配合 `boiler-research-system` 项目使用。

## 安装

将 `skills/` 目录下的5个文件夹复制到：

```
C:\Users\{用户名}\.claude\skills\
```

即：

```
.claude/skills/
├── boiler-daily/      → 每日文献雷达
├── boiler-reader/     → 单篇论文阅读（arXiv/DOI/PDF）
├── boiler-survey/     → 综述生成与更新
├── boiler-vault/      → Vault检索问答
└── boiler-zotero/     → Zotero文献处理
```

重启 Claude Code 后即可使用。

---

## 技能说明

### boiler-zotero — Zotero 文献处理

**触发**：「精读 Zotero 里的 XXX」「读一下{作者}的论文」「批量处理{分类}」

两种模式：
- **单篇阅读**：两层判断（综述 vs 研究论文 × 精读 vs 粗读）→ 4种笔记格式
- **批量处理**：整个 Zotero Collection 自动逐篇处理，断点续传

特性：
- Zotero 运行时（数据库锁定）自动降级，直接读 PDF + 缓存，不中断
- 研究论文精读自动识别架构图（PDF视觉读取）
- 写完笔记自动更新 `graph_data.json` 知识图谱

---

### boiler-reader — 单篇论文阅读（非Zotero）

**触发**：「精读这篇」「读一下 arxiv.org/abs/xxxx」「分析这个DOI」

输入：arXiv 链接/ID、DOI、本地 PDF 路径、论文标题

两层判断同 boiler-zotero：
- 综述论文 → 使用综述模板（方法脉络、关键文献、文献池）
- 研究论文精读 → 使用精读模板 + 架构图识别

---

### boiler-survey — 综述生成与更新

**触发**：「生成{子方向}综述」「更新综述」「整理{topic}的文献」

扫描指定 domain/subfield 下的精读笔记，聚合生成结构化综述文档。

---

### boiler-vault — Vault 检索问答

**触发**：所有在 Vault 已有笔记范围内的检索和问答

先读索引定位笔记，只基于 Vault 已有内容回答，不联网。

---

### boiler-daily — 每日文献雷达

**触发**：「今日论文推荐」「过去N天论文」「每日推荐」

自动从 arXiv + OpenAlex 抓取 → 多域评分 → 分类精读/粗读 → 生成 Obsidian 推荐笔记。

---

## 配套路径（需与 boiler-research-system 项目对应）

| 配置项 | 默认路径 |
|--------|----------|
| 项目目录 | `D:\lunwen\boiler-research-system` |
| Zotero DB | `D:\zetero\zotero.sqlite` |
| Zotero Storage | `D:\zetero\storage` |
| Obsidian Vault | `D:\lunwen\论文阅读` |
| 笔记输出 | `D:\lunwen\论文阅读\60_Zotero导入\` |
| 精读模板 | `D:\lunwen\boiler-research-system\templates\精读笔记模板.md` |
| 综述模板 | `D:\lunwen\boiler-research-system\templates\综述模板.md` |
| 粗读模板 | `D:\lunwen\boiler-research-system\templates\粗读卡模板.md` |

迁移到新机器时，修改各 SKILL.md 中对应的路径即可。

---

## 知识图谱领域短名

frontmatter `domain` 字段必须使用以下短名：

| 短名 | 含义 |
|------|------|
| `Boiler` | 燃煤锅炉 · 燃烧 · NOx |
| `LLM-Agent` | 大模型智能体 · 自主科研 |
| `CFD` | CFD · 燃烧仿真 · 湍流 |
| `DigitalTwin` | 数字孪生 · 软测量 · 故障诊断 |
| `ROM` | 降阶模型 · 代理模型 · PINN |
| `CS-Foundations` | ML/DL · 时序 · RL · MPC |
| `KnowledgeInfra` | 知识图谱 · RAG · 文献工作流 |
