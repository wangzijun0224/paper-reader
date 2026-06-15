---
name: boiler-zotero
description: Zotero文献处理。支持两种模式：①单篇阅读（精读/粗读/综述）——用户说"读一下Zotero里的{标题}""精读{作者}的论文"时触发；②批量处理——用户说"批量处理{collection}""处理Zotero里的{分类}"时触发。
---

# Zotero 文献处理

## 配置（固定路径）
- 项目目录: `D:\lunwen\boiler-research-system`
- Zotero DB: `D:/zetero/zotero.sqlite`
- Zotero Storage: `D:/zetero/storage`
- Vault: `D:/lunwen/论文阅读`
- 输出根目录: `D:/lunwen/论文阅读/60_Zotero导入/`
- 研究精读模板: `D:\lunwen\boiler-research-system\templates\精读笔记模板.md`
- 综述模板: `D:\lunwen\boiler-research-system\templates\综述模板.md`
- 粗读模板: `D:\lunwen\boiler-research-system\templates\粗读卡模板.md`

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

**研究精读** → 按 `D:\lunwen\boiler-research-system\templates\精读笔记模板.md`
- 重点：方法架构、关键公式、实验结果对比表、可迁移点
- 额外字段：`zotero_key: {item_key}`, `source: Zotero`
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{domain}/{标题缩写}.md`

**研究粗读** → 按 `D:\lunwen\boiler-research-system\templates\粗读卡模板.md`
- 额外字段：`zotero_key: {item_key}`
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{domain}/{标题缩写}-粗读.md`

**综述精读** → 不套研究论文模板，改用以下结构：
```
## 综述范围与定位
## 文献分类框架（综述的骨架）
## 各方向代表性工作与进展
## 共识与争议点
## 研究空白与未解问题
## 对我写综述/做研究的参考价值
## 值得深读的关键引用（列出3-5篇）
```
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{domain}/{标题缩写}-综述精读.md`

**综述粗读** → 只提取：
- 综述覆盖范围（1-2句）
- 分类框架（列出一级目录）
- 最关键引用（≤3篇）
- 对我的价值（1句）
- 保存至：`D:/lunwen/论文阅读/60_Zotero导入/{domain}/{标题缩写}-综述粗读.md`

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
