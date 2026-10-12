---
name: boiler-survey
description: 综述生成与更新。用户说"生成{subfield}综述""更新综述""整理{topic}的文献"时触发。扫描指定domain/subfield下的精读笔记，聚合生成结构化综述。
---

# 综述生成

## 触发方式
- `生成 {domain}/{subfield} 综述` → 新建综述
- `更新 {topic} 综述` → 追加新文献
- `整理 {关键词} 的文献` → 按关键词跨domain收集后生成

## Step 1: 收集文献
先从项目 `config/user-config.json` 读取 Vault 和各笔记目录。

**来源A：精读笔记**
```powershell
# Grep搜索包含目标关键词的精读笔记
rg -l "{topic_keywords}" "{Vault}/{paper_notes_folder}" --include="*.md"
```

**来源B：粗读卡**
```powershell
rg -l "{topic_keywords}" "{Vault}/{quick_notes_folder}" --include="*.md"
```

## Step 2: 提取结构化信息
对每篇候选笔记，提取：
- `algorithm`（方法/算法）、`key_finding`（核心结论）、`year`（年份）
- `relevance_to_my_system`（来自笔记的“对本研究启发”）

## Step 3: 生成/更新综述文件
保存路径：`{Vault}/{surveys_folder}/{domain}/{subfield}-综述.md`

按 `{项目目录}/templates/综述模板.md` 生成，包含：
- 方法演进时间线（按年份）
- 各方法对比表（输入/输出/精度/计算代价/是否可迁移到锅炉）
- 研究空白与开放问题
- 与本研究方向的结合点

## Step 4: 更新图谱
```powershell
python D:\lunwen\boiler-research-system\scripts\update_graph.py --update-survey "{subfield}"
```

## 约束
- 综述结论必须基于笔记中已有内容，不捏造
- 不确定的迁移价值标注"待验证"
- 综述文件格式必须保持Dataview可解析（frontmatter完整）
