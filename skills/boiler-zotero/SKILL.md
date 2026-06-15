---
name: boiler-zotero
description: Zotero文献处理。支持两种模式：①单篇阅读（精读/粗读/综述）——用户说"读一下Zotero里的{标题}""精读{作者}的论文"时触发；②批量处理——用户说"批量处理{collection}""处理Zotero里的{分类}"时触发。
---

# Zotero 文献处理

## 配置
先读项目 `config/user-config.json`：
- Zotero DB: `paths.zotero_db`
- Zotero Storage: `paths.zotero_storage`
- 输出根目录: `{Vault}/{paths.zotero_folder}`

---

## 模式 A：单篇阅读（精读 / 粗读 / 综述）

### A1. 查找论文
```powershell
python {项目目录}/scripts/zotero_helper.py info --title "{标题关键词}" --db "{zotero_db}" --storage "{zotero_storage}"
```
返回：`item_key`, `title`, `doi`, `abstract`, `date`, `pdf_paths`, `cache_paths`, `highlights`

若未指定标题，用：
```powershell
python {项目目录}/scripts/zotero_helper.py list-collections --db "{zotero_db}"
```
让用户从列表中选择。

### A2. 判断阅读深度
- 用户明确说"精读" → 精读模式
- 用户明确说"粗读"/"快速看" → 粗读模式
- 用户说"综述"/"做综述用" → 综述摘录模式
- 未指定 → 根据 `highlights` 数量判断（>5条批注 → 精读，否则粗读）

### A3. 获取语料（优先级）
1. Zotero 批注和高亮（`highlights`）
2. `.zotero-ft-cache` 全文缓存（`cache_paths`）
3. 本地 PDF（`pdf_paths`）
4. arXiv HTML（若有 arxiv_id）→ 用 WebFetch 获取

### A4. 生成笔记

**精读** → 参考 `{项目目录}/templates/精读笔记模板.md`
- 额外添加 frontmatter 字段：`zotero_key: {item_key}`，`source: Zotero`
- 保存至：`60_Zotero导入/{domain}/{标题缩写}.md`

**粗读** → 参考 `{项目目录}/templates/粗读卡模板.md`
- 额外添加 `zotero_key: {item_key}`
- 保存至：`60_Zotero导入/{domain}/{标题缩写}-粗读.md`

**综述摘录** → 只提取：核心贡献（3句）、关键方法、数据/指标、对综述的价值
- 格式更紧凑，无需完整精读结构
- 保存至：`60_Zotero导入/{domain}/{标题缩写}-综述摘录.md`

### A5. 更新知识图谱
```powershell
python {项目目录}/scripts/update_graph.py --vault "{Vault}" --note "{笔记路径}"
```

---

## 模式 B：批量处理 Collection

### B1. 读取 Collection
```powershell
python {项目目录}/scripts/zotero_helper.py list-collection --name "{分类名}" --db "{zotero_db}"
```
输出：条目列表（`item_key`, `title`, `doi`, `abstract`, `date`, `pdf_keys`）

若不知道 collection 名称，先列出所有 collection：
```powershell
python {项目目录}/scripts/zotero_helper.py list-collections --db "{zotero_db}"
```

### B2. 断点续传
读取 `{输出目录}/_进度记录.md`，过滤已处理（✅成功/⚠️跳过）条目，生成待处理队列。

### B3. 逐篇处理（串行，同模式A步骤A1-A5）
批量模式默认生成精读笔记。每篇完成后立即追加进度：
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
