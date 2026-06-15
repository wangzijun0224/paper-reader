# 锅炉文献雷达系统

**Vault**: `D:\lunwen\论文阅读`  
**Zotero**: `D:\zetero`  
**Skills目录**: `C:\Users\Administrator\.claude\skills\`

## 快速启动

### Step 1: 初始化Vault目录
```powershell
powershell -ExecutionPolicy Bypass -File D:\lunwen\boiler-research-system\scripts\setup_vault.ps1
```

### Step 2: 安装Skills
```powershell
$skills = "$env:USERPROFILE\.claude\skills"
New-Item -ItemType Directory -Force -Path $skills | Out-Null

# 从已下载的skill包安装基础框架
Copy-Item -Recurse -Force "C:\Users\Administrator\Documents\skill\dailypaper-skills-main\skills\*" "$skills\"

# 安装本系统自定义skill
Copy-Item -Recurse -Force "D:\lunwen\boiler-research-system\skills\*" "$skills\"
```

### Step 3: 配置邮箱（可选，用于journal-digest）
编辑 `D:\lunwen\boiler-research-system\config\daily-digest.config.json`，填入 `crossref_mailto`。

### Step 4: 验证
在Claude Code中输入：`今日论文推荐`

---

## 日常使用

| 命令 | 功能 |
|------|------|
| `今日论文推荐` | 每日30篇，自动精读3-5篇 |
| `过去3天论文推荐` | 补推过去3天 |
| `/boiler-reader https://arxiv.org/abs/xxxx` | 手动精读单篇 |
| `/boiler-reader 快速 https://arxiv.org/abs/xxxx` | 粗读单篇 |
| `/boiler-reader 综述 https://arxiv.org/abs/xxxx` | 提取综述素材 |
| `/boiler-zotero CFD` | 批量处理Zotero的CFD分类 |
| `/boiler-survey LLM-Agent/agentic-RAG` | 生成综述 |
| `/boiler-vault {问题}` | 检索已有笔记回答问题 |
| `更新索引` | 刷新所有domain索引页 |

---

## 系统架构

```
[arXiv API]         ──┐
[OpenAlex API]      ──┤──→ fetch_papers.py ──→ 评分分档 ──→ boiler-daily SKILL
                      │        ↓精读候选
[ScienceDirect]     ──┘    boiler-reader ──→ 精读笔记 (10_精读笔记/)
(手动登录批量PDF)            ↓粗读候选
                         粗读卡 (20_粗读卡/)

[Zotero D:\zetero]  ──→ boiler-zotero SKILL ──→ 60_Zotero导入/

10_精读笔记/ ──→ boiler-survey ──→ 30_综述/
10_精读笔记/ ──→ update_graph.py ──→ graph_data.json (RAG知识库)
所有笔记 ──→ boiler-vault SKILL (Vault内检索问答)
```

## Vault目录说明

| 目录 | 说明 |
|------|------|
| `00_每日推荐/` | 每日推荐笔记，格式: `YYYY-MM-DD-论文推荐.md` |
| `10_精读笔记/{Domain}/` | 精读结构化笔记 |
| `20_粗读卡/` | 粗读速览卡，按月分文件夹 |
| `30_综述/{Domain}/` | 综述笔记 |
| `40_概念库/` | 方法/概念定义笔记 |
| `50_我的笔记/` | 用户手写阅读心得 |
| `60_Zotero导入/{Domain}/` | Zotero批处理输出 |
| `90_系统/索引/` | 自动生成的Dataview索引页 |
| `90_系统/知识图谱/` | graph_data.json (供LLM RAG使用) |
| `模板/` | 精读/粗读/综述模板 |

## 关于ScienceDirect
ScienceDirect需要机构账号，不进入每日自动管道。
使用方式：
1. 手动登录ScienceDirect
2. 准备DOI列表CSV文件
3. 运行 `sciencedirect-live-session-fetcher` (已在skill目录中)
4. 下载的PDF放入Zotero后，用 `/boiler-zotero` 处理

## 多Domain支持
一篇论文可同时属于多个domain。在笔记frontmatter中：
```yaml
domain: [Boiler, CFD, ROM]
```
Obsidian的wikilink + Dataview会自动在各domain索引页中显示该论文。
