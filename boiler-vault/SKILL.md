---
name: boiler-vault
description: Vault内文献检索与问答。将所有用户输入默认视为检索触发。先读索引，再定位笔记，只基于Vault已有笔记内容回答。
---

# Vault 检索

## 触发
Vault工作区内的所有提问。不要等用户说"检索"或"搜索"。

## 配置
先读项目 `config/user-config.json`，获取 `paths.obsidian_vault` 和 `paths.system_folder`。

## 检索流程

### 1. 读索引（按顺序，缺失跳过）
```powershell
Get-Content "{Vault}/{system_folder}/索引/文献总索引.md" -Encoding UTF8 -Raw
Get-Content "{Vault}/{system_folder}/索引/{domain}领域索引.md" -Encoding UTF8 -Raw
```

### 2. 关键词搜索
```powershell
rg -n --include="*.md" "{keyword1}|{keyword2}" "{Vault}"
```
同时搜索中英文关键词、方法名别名。

### 3. 读证据笔记
优先精读笔记 > 粗读卡 > 综述 > Zotero导入。
打开最相关的1-3篇完整笔记。

## 回答结构（固定）
1. **结论**（只基于Vault内容）
2. **支持文献**（笔记标题+精确字段引用）
3. **差异/争议**（如有）
4. **对本研究的启发**

## 约束
- 不编造内容，不用外部知识填补空白
- Vault依据不足时明确写：`Vault中未找到足够依据`，再决定是否给有限回答
- 不修改任何笔记（除非用户明确要求）
