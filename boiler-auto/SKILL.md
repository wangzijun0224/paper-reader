---
name: boiler-auto
description: 自动文献流水线。用户说"自动找文献""全流程找XX方向""检索+下载+入库+阅读"时触发。给定范围后：多源检索（含Nature/Science正刊子刊、AIAA/AAAI）→ arXiv/OA直接下载 + instsci浏览器走校园网下付费墙全文（登录人工完成）→ PDF存本地并全部导入Zotero「每日阅读」→ 精读5篇+粗读20+篇 → 笔记写入Obsidian。
---

# 自动文献流水线（检索→下载→入库→阅读→笔记）

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
instsci_exe = E:/自动文献/instsci-main/.venv/Scripts/instsci.exe
dl_root     = E:/自动文献/downloads
```

## 触发与参数确认

用户给一个范围即可，例如："自动找锅炉×机器学习交叉方向，近30天"。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 关键词/方向 | 用户指定 | 映射为 `--extra-keywords` 和/或 `--domains-filter` |
| 时间窗 | 30 天 | `--days 30` 或 `--start-date/--end-date` |
| 总量 top-n | 100 | 大批量场景 |
| 精读数 | 5 | 不超过此数 |
| 粗读数 | 20+ | top-n 减精读 |

用户没说的参数用默认值，不要逐项追问。

**运行目录**：`{dl_root}/YYYY-MM-DD_主题slug/`，本次运行所有产物（PDF、pending 清单、manifest）都放这里。

---

## Step 1: 多源检索

```powershell
python {project_dir}/scripts/fetch_papers.py \
  --days 30 \
  --top-n 100 \
  --extra-keywords "用户给的关键词" \
  --out {tmp_json} \
  --exclude-seen {seen_path} \
  --update-seen
```

- 来源：arXiv + OpenAlex + Crossref 期刊白名单（含 Nature/Science 正刊及子刊，新增 Nature Chemistry/Catalysis/Synthesis/Materials/Physics/Sustainability、Nature Reviews Chemistry/Methods Primers、Science Signaling、Energy Material Advances）+ Scopus + IEEE + OpenReview（ICLR/NeurIPS/ICML/AAAI）+ AIAA 会议 + DBLP 兜底（CVPR/ICCV/ACL/KDD/IJCAI）。**已无 HuggingFace / Semantic Scholar**。
- 只要顶刊时加 `--journal-preset nature`；只要某方向加 `--domains-filter`（取值见 boiler-daily）。
- 跑完读 tmp_json 确认：`total_fetched`、sources 分布、deep_read 是否满 5 篇。

## Step 2: 直接下载（arXiv + OA）

```powershell
python {project_dir}/scripts/download_bridge.py \
  --input {tmp_json} \
  --out-dir "{dl_root}/YYYY-MM-DD_主题" \
  --write-doi-list --instsci
```

- arXiv → 直下；DOI → Unpaywall 找 OA；其余进 `pending_dois.txt`。
- 脚本会按出版社分组打印 instsci 命令。**只打印，不自动执行**。
- 产物：`manifest.json`（doi/arxiv_id → pdf 路径 + 状态）。

## Step 3: 浏览器下载付费墙全文（人工登录，用户在场时执行）

pending 清单非空时，**先告知用户**"接下来要打开浏览器走校园网登录，请在场"，然后逐组执行 Step 2 打印的命令：

```powershell
{instsci_exe} papers {out-dir}/instsci/dois_{publisher}.txt --publisher {key} --output {out-dir}/instsci/{key}
```

- 首次使用需先 `{instsci_exe} setup --institution-cn "学校名"`（交互式，问用户）。
- 浏览器弹出后 SSO/验证码由**用户手动完成**，你只负责等待和观察下载结果。
- 一组失败不阻塞其他组；失败的 DOI 在每日笔记"操作清单"里列出。
- **instsci 完成后**：扫描 `{out-dir}/instsci/**/*.pdf`，按文件名/结果报告把 DOI→PDF 路径补进 `manifest.json`（status 改为 ok）。

## Step 4: 全部导入 Zotero「每日阅读」

**检索到的所有文献（含未下到 PDF 的）都导入**，有 PDF 的挂附件。

```powershell
# 先预演
python {project_dir}/scripts/zotero_import.py \
  --input {tmp_json} \
  --pdf-manifest "{out-dir}/manifest.json" \
  --collection 每日阅读 --dry-run

# 确认无误后正式导入
python {project_dir}/scripts/zotero_import.py \
  --input {tmp_json} \
  --pdf-manifest "{out-dir}/manifest.json" \
  --collection 每日阅读
```

- config 里 `zotero.user_id`/`api_key` 已配置 → 走 web API，**Zotero 开着也行**（推荐，提示用户填一次即可）。
- 未配置 → 走 sqlite 直连，**必须先请用户关闭 Zotero**；锁冲突时脚本会报错退出（exit 3），不要重试轰炸。
- 去重：DOI / arxiv_id 已在库中的自动跳过。
- 退出码：0 成功，1 collection 不存在，3 数据库被锁。

## Step 5: 阅读（精读 ≤5 + 粗读 20+）

### 精读
- 优先有 PDF 的 deep_read 论文，调用 `/boiler-zotero`（论文已进「每日阅读」，按标题精读）或 `/boiler-reader`（本地 PDF 路径）。
- 无 PDF 的精读候选跳过，进操作清单待下载。

### 粗读（大批量，分批 + 断点续跑）
- 对 quick_read 逐篇生成粗读卡，规则同 boiler-daily Step 2（摘要分析五要素、模板、wikilink）。
- **每批 ≤10 篇**，在 `{out-dir}/_进度记录.md` 用 ✅/⚠️ 记录每篇状态；中断后续跑时先读进度记录跳过已完成。
- 全部粗读卡写完再进 Step 6。

## Step 6: 汇总笔记 + 刷新索引

- 按 boiler-daily Step 3 的结构写 `{daily_dir}/YYYY-MM-DD-自动流水线-主题.md`，frontmatter `run_type: auto_pipeline`，额外加一段"下载与入库情况"：fetch 总数 / 直下成功 / instsci 成功 / 导入 Zotero 数 / 跳过重复数。
- 操作清单列出：待精读（无PDF）、instsci 失败 DOI、sqlite 锁冲突提醒（如发生）。
- 最后：`python {project_dir}/scripts/update_graph.py --refresh-index`

---

## 规则约束

- **历史去重**：Step 1 必须带 `--exclude-seen {seen_path} --update-seen`。
- **人工环节只有两处**：instsci 浏览器登录（Step 3）、sqlite 路径下关闭 Zotero（Step 4）。其余全自动，不要中途问用户。
- 大批量时每个 Step 之间报告一次进度（检索到 N / 下到 N / 入库 N / 笔记 N）。
- 精读 ≤5 篇是硬上限；粗读分批 ≤10 篇/批。
- 所有链接必须真实可达（doi.org / arxiv.org）。
- 下载失败的论文不丢弃：元数据照常入 Zotero，笔记照常出粗读卡，PDF 进操作清单。
