#!/usr/bin/env python3
"""
知识图谱维护脚本
- add-paper: 添加/更新论文节点
- update-survey: 标记subfield综述已更新
- refresh-index: 扫描Vault重建索引页
"""
import argparse, json, glob, re
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user-config.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_graph(graph_path):
    p = Path(graph_path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"nodes": [], "edges": [], "last_updated": ""}

def save_graph(graph, graph_path):
    p = Path(graph_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    graph["last_updated"] = datetime.now().isoformat()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

def resolve_graph_path(config, vault_override=None):
    if vault_override:
        return (
            Path(vault_override)
            / config["paths"]["system_folder"]
            / "知识图谱"
            / "graph_data.json"
        )
    return Path(config["paths"]["graph_data"])

def extract_frontmatter(md_path):
    """提取Markdown frontmatter为dict"""
    try:
        content = Path(md_path).read_text(encoding="utf-8")
    except:
        return {}
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end < 0:
        return {}
    fm_text = content[3:end]
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"')
    # 兼容统一字段 domain 和旧字段 domains。
    domain_match = re.search(r"^(?:domain|domains):\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if domain_match:
        result["domain"] = [
            d.strip().strip("\"'")
            for d in domain_match.group(1).split(",")
            if d.strip()
        ]
    return result

def note_directories(config, vault):
    folders = [
        config["paths"].get("paper_notes_folder"),
        config["paths"].get("zotero_folder"),
    ]
    return [Path(vault) / folder for folder in folders if folder]

def add_note(note_path, config, graph, vault_override=None):
    vault = Path(vault_override or config["paths"]["obsidian_vault"])
    path = Path(note_path)
    if not path.is_absolute():
        path = vault / path
    if not path.exists():
        print(f"[graph] 笔记不存在: {path}")
        return False

    fm = extract_frontmatter(path)
    node_id = fm.get("arxiv_id") or fm.get("doi") or fm.get("zotero_key") or path.stem
    domains = fm.get("domain") or []
    if isinstance(domains, str):
        domains = [domains]

    try:
        relative_path = path.relative_to(vault)
    except ValueError:
        relative_path = path

    node_data = {
        "id": node_id,
        "type": "paper",
        "title": fm.get("title", path.stem),
        "year": fm.get("year", ""),
        "domain": domains,
        "read_depth": fm.get("read_depth", ""),
        "evidence_level": fm.get("evidence_level", ""),
        "status": fm.get("status", ""),
        "note_path": str(relative_path),
        "updated": datetime.now().isoformat()
    }
    existing = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if existing:
        existing.update(node_data)
    else:
        graph["nodes"].append(node_data)

    graph["edges"] = [
        edge for edge in graph["edges"]
        if not (edge.get("target") == node_id and edge.get("type") == "contains")
    ]
    for domain in domains:
        graph["edges"].append({"source": domain, "target": node_id, "type": "contains"})

    print(f"[graph] 已添加节点: {node_id} (domain: {domains})")
    return True

def add_paper(arxiv_id_or_doi, config, graph):
    """从Vault中找到对应笔记，添加到图谱节点"""
    vault = config["paths"]["obsidian_vault"]
    # 搜索对应笔记
    target_note = None
    for notes_dir in note_directories(config, vault):
        for md in glob.glob(str(notes_dir / "**/*.md"), recursive=True):
            fm = extract_frontmatter(md)
            note_ids = [fm.get("arxiv_id", ""), fm.get("doi", ""), fm.get("zotero_key", "")]
            if arxiv_id_or_doi and any(arxiv_id_or_doi in note_id for note_id in note_ids if note_id):
                target_note = md
                break
        if target_note:
            break

    if not target_note:
        print(f"[graph] 未找到匹配笔记: {arxiv_id_or_doi}")
        return

    add_note(target_note, config, graph, vault)

def refresh_index(config):
    """扫描Vault，重建各domain索引页"""
    vault = Path(config["paths"]["obsidian_vault"])
    index_dir = vault / config["paths"]["system_folder"] / "索引"
    index_dir.mkdir(parents=True, exist_ok=True)

    domain_papers = {d: [] for d in config["domains"]}
    all_papers = []

    seen_paths = set()
    for notes_dir in note_directories(config, vault):
        for md in sorted(glob.glob(str(notes_dir / "**/*.md"), recursive=True)):
            if md in seen_paths:
                continue
            seen_paths.add(md)
            fm = extract_frontmatter(md)
            title = fm.get("title", Path(md).stem)
            rel_path = Path(md).relative_to(vault)
            domains = fm.get("domain") or []
            if isinstance(domains, str):
                domains = [domains]
            link_path = rel_path.with_suffix("").as_posix()
            entry = f"- [[{link_path}|{title}]] | {', '.join(domains)} | {fm.get('year','')}"
            all_papers.append(entry)
            for domain in domains:
                if domain in domain_papers:
                    domain_papers[domain].append(entry)

    # 写总索引
    total_index = index_dir / "文献总索引.md"
    content = "---\ntags: [index, auto-generated]\n---\n# 文献总索引\n\n"
    content += f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    content += f"总计：{len(all_papers)} 篇精读笔记\n\n"
    content += "\n".join(all_papers)
    total_index.write_text(content, encoding="utf-8")

    # 写各domain索引
    for domain, papers in domain_papers.items():
        d_index = index_dir / f"{domain}领域索引.md"
        content = f"---\ntags: [index, {domain}]\n---\n# {domain} 领域索引\n\n"
        content += f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 共 {len(papers)} 篇\n\n"
        content += "\n".join(papers) if papers else "暂无笔记"
        d_index.write_text(content, encoding="utf-8")

    print(f"[index] 索引刷新完成：{len(all_papers)} 篇，{len(config['domains'])} 个domain")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--add-paper", type=str, help="添加论文到图谱（arxiv_id或doi）")
    parser.add_argument("--note", type=str, help="按笔记路径添加或更新图谱节点")
    parser.add_argument("--vault", type=str, help="临时覆盖配置中的 Vault 路径")
    parser.add_argument("--update-survey", type=str, help="标记综述更新（subfield名）")
    parser.add_argument("--refresh-index", action="store_true", help="重建索引页")
    args = parser.parse_args()

    config = load_config()
    graph_path = resolve_graph_path(config, args.vault)
    graph = load_graph(graph_path)

    if args.add_paper:
        add_paper(args.add_paper, config, graph)
        save_graph(graph, graph_path)

    if args.note:
        if add_note(args.note, config, graph, args.vault):
            save_graph(graph, graph_path)

    if args.update_survey:
        # 记录综述更新事件
        graph.setdefault("surveys", {})[args.update_survey] = datetime.now().isoformat()
        save_graph(graph, graph_path)
        print(f"[graph] 综述节点更新: {args.update_survey}")

    if args.refresh_index:
        refresh_index(config)
        save_graph(graph, graph_path)

if __name__ == "__main__":
    main()
