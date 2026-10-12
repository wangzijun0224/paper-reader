#!/usr/bin/env python3
"""
批量生成粗读卡笔记
从 tmp_papers.json 读取 quick_read 列表，为每篇写 Obsidian 粗读卡
输出 JSON 到 stdout：[{title, filename, wikilink, domain, score, source, url, domains}, ...]
"""
import json, re, sys
from pathlib import Path
from datetime import date

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user-config.json"

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def slugify(text, max_len=45):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len].rstrip("-")

DOMAIN_PRIORITY = ["Boiler", "LLM-Agent", "CFD", "DigitalTwin", "ROM", "CS-Foundations", "KnowledgeInfra"]

def main_domain(domains):
    for d in DOMAIN_PRIORITY:
        if d in domains:
            return d
    return domains[0] if domains else "CS-Foundations"

def domain_wikilinks(domains):
    return " / ".join(f"[[{d}]]" for d in domains) if domains else "[[CS-Foundations]]"

def make_note(paper, today_str):
    title   = paper.get("title", "")
    authors = paper.get("authors") or []
    source  = paper.get("source", "")
    year    = paper.get("year", "")
    url     = paper.get("url", "")
    doi     = paper.get("doi") or ""
    arxiv   = paper.get("arxiv_id") or ""
    abstract= paper.get("abstract") or ""
    domains = paper.get("domains") or []
    score   = paper.get("score", 0)
    needs_dl= paper.get("needs_download", False)

    link = url or (f"https://arxiv.org/abs/{arxiv}" if arxiv else (f"https://doi.org/{doi}" if doi else ""))

    # 一句话总结
    if abstract and len(abstract) > 30:
        first = abstract.split(".")[0].strip()
        summary = (first[:200] + "...") if len(first) > 200 else first + "."
        evidence = "摘要首句"
        research_q = abstract[:180].rstrip() + "..."
    else:
        summary = f"（仅标题判断）{title}"
        evidence = "仅标题"
        research_q = "待读全文确认"

    dl_row = f"\n| 备注 | ⚠️ 需手动下载PDF |" if needs_dl else ""

    return f"""---
type: literature-note
title: "{title.replace('"', "'")}"
arxiv_id: "{arxiv}"
doi: "{doi}"
year: "{year}"
authors: {json.dumps(authors[:4], ensure_ascii=False)}
source: "{source}"
url: "{link}"
domain: {json.dumps(domains, ensure_ascii=False)}
score: {score}
read_depth: 粗读
evidence_level: {"abstract" if abstract else "title"}
status: draft
tags: [quick-read, daily-{today_str}]
created: "{today_str}"
updated: "{today_str}"
---

# {title}

## 元信息

| 项目 | 内容 |
| ---- | ---- |
| 标题 | {title} |
| 作者 | {"; ".join(authors[:4]) or "未知"} |
| 来源 | {source} / {year} |
| 链接 | {link} |
| 所属领域 | {domain_wikilinks(domains)} |
| 分数 | {score} |{dl_row}

---

## 一句话总结

{summary}

---

## 初步判断

- **研究问题**：{research_q}
- **核心方法**：待读全文确认
- **主要结果**：待读全文确认
- **可能价值**：领域 {', '.join(domains) or '未知'}，评分 {score}
- **证据来源**：{evidence}

---

## 与我研究的关系

- **相关方向**：{', '.join(domains) or '未知'}
- **可能服务的系统构件**：待确认
- **是否值得精读**：待定
- **精读时重点看**：

---

## 待确认

-\x20
"""

def main():
    json_path = sys.argv[1] if len(sys.argv) > 1 else "D:/lunwen/论文阅读/90_系统/tmp_papers.json"
    today_str = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()

    config   = load_config()
    vault    = config["paths"]["obsidian_vault"]
    qfolder  = config["paths"]["quick_notes_folder"]
    base_dir = Path(vault) / qfolder

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for paper in data.get("quick_read", []):
        title  = paper.get("title", "untitled")
        dom    = main_domain(paper.get("domains") or [])
        slug   = slugify(title)
        fname  = f"{slug}-粗读"
        out_dir = base_dir / dom
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{fname}.md"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(make_note(paper, today_str))

        print(f"[OK] {dom}/{fname}.md", file=sys.stderr)
        results.append({
            "title":    title,
            "filename": fname,
            "wikilink": f"[[{fname}|{title[:55]}{'...' if len(title)>55 else ''}]]",
            "domain":   dom,
            "score":    paper.get("score", 0),
            "source":   paper.get("source", ""),
            "url":      paper.get("url", ""),
            "domains":  paper.get("domains") or [],
            "abstract": (paper.get("abstract") or "")[:120],
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
