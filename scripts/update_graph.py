#!/usr/bin/env python3
"""
知识图谱维护脚本 v2
节点类型: domain | paper
边类型:
  belongs_to  paper → domain   (frontmatter domain 字段)
  wikilink    paper → paper    (正文 [[双链]]，排除占位符)
"""
import argparse, json, glob, re
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user-config.json"

DOMAIN_FULL_NAMES = {
    "Boiler":         "Boiler Industrial Scenarios",
    "LLM-Agent":      "LLM-Agent and Autonomous Research",
    "CFD":            "CFD and Physics-based Simulation",
    "DigitalTwin":    "Digital Twin and Online Industrial Intelligence",
    "ROM":            "Reduced-order and Surrogate Modeling",
    "CS-Foundations": "Computer Science Foundations",
    "KnowledgeInfra": "Knowledge Infrastructure and RAG",
}

# ── 基础 IO ──────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_graph(graph_path):
    p = Path(graph_path)
    if p.exists():
        with open(p, "r", encoding="utf-8-sig") as f:   # utf-8-sig 兼容 BOM
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

# ── Markdown 解析 ─────────────────────────────────────────────────────────────

def extract_frontmatter(md_path):
    """返回 (frontmatter_dict, body_text)"""
    try:
        content = Path(md_path).read_text(encoding="utf-8")
    except Exception:
        return {}, ""
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end < 0:
        return {}, content
    fm_text = content[3:end]
    body = content[end + 4:]

    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"')

    # 解析 YAML 数组字段（用正则匹配带引号的元素，避免域名内部逗号被误拆）
    for field in ["domain", "subfield", "algorithm", "authors"]:
        m = re.search(rf"^{field}:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
        if m:
            items = re.findall(r'\s*"([^"]*)"\s*|\s*\'([^\']*)\'\s*|\s*([^,\[\]]+)', m.group(1))
            result[field] = [
                (a or b or c).strip()
                for a, b, c in items
                if (a or b or c).strip()
            ]
    return result, body

def parse_wikilinks(body: str) -> list[str]:
    """
    提取正文中的 [[目标]] 链接。
    规则：
      - 排除含 {{}} 的模板占位符
      - 排除含路径分隔符 / 的文件夹链接
      - 排除纯中文领域短名（Boiler / LLM-Agent 等）
    """
    raw = re.findall(r'\[\[([^\]{}|]+?)(?:\|[^\]]+)?\]\]', body)
    domain_shorts = set(DOMAIN_FULL_NAMES.keys())
    result = []
    for link in raw:
        link = link.strip()
        if "/" in link:          # 文件夹路径链接
            continue
        if link in domain_shorts: # 领域节点本身，不建 paper→paper 边
            continue
        result.append(link)
    return result

# ── 图谱操作 ──────────────────────────────────────────────────────────────────

def upsert_node(graph, node_id, node_type, **attrs):
    existing = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if existing:
        existing.update(attrs)
        return existing
    node = {"id": node_id, "type": node_type, **attrs}
    graph["nodes"].append(node)
    return node

def upsert_edge(graph, source, target, edge_type):
    for e in graph["edges"]:
        if e["source"] == source and e["target"] == target and e["type"] == edge_type:
            return   # 已存在，不重复
    graph["edges"].append({"source": source, "target": target, "type": edge_type})

def remove_edges_for_node(graph, node_id):
    """删除该节点的所有出边（重建前清理）"""
    graph["edges"] = [
        e for e in graph["edges"]
        if e["source"] != node_id
    ]

def ensure_domain_nodes(graph, config):
    for short in config["domains"]:
        upsert_node(
            graph, f"domain:{short}", "domain",
            label=DOMAIN_FULL_NAMES.get(short, short),
            short=short,
        )

# ── 核心：添加/更新单篇笔记 ───────────────────────────────────────────────────

def add_note(note_path, config, graph, vault_override=None):
    vault = Path(vault_override or config["paths"]["obsidian_vault"])
    path = Path(note_path)
    if not path.is_absolute():
        path = vault / path
    if not path.exists():
        print(f"[graph] 笔记不存在: {path}")
        return False

    fm, body = extract_frontmatter(path)

    # 唯一 ID 优先级: doi > arxiv_id > zotero_key > 文件名
    node_id = fm.get("doi") or fm.get("arxiv_id") or fm.get("zotero_key") or path.stem

    domains = fm.get("domain") or []
    if isinstance(domains, str):
        domains = [domains]
    subfields = fm.get("subfield") or []
    if isinstance(subfields, str):
        subfields = [subfields]

    try:
        rel_path = str(path.relative_to(vault))
    except ValueError:
        rel_path = str(path)

    # 确保所有 Domain 节点存在
    ensure_domain_nodes(graph, config)

    # 更新 Paper 节点
    upsert_node(
        graph, node_id, "paper",
        title=fm.get("title", path.stem),
        year=fm.get("year", ""),
        domain=domains,
        subfield=subfields,
        read_depth=fm.get("read_depth", ""),
        note_type=fm.get("type", ""),
        status=fm.get("status", ""),
        note_path=rel_path,
        updated=datetime.now().isoformat(),
    )

    # 清除旧出边，重建
    remove_edges_for_node(graph, node_id)

    # Paper → Domain (belongs_to)
    for d in domains:
        upsert_edge(graph, node_id, f"domain:{d}", "belongs_to")

    # Paper → Paper (wikilink，从正文双链提取)
    for link in parse_wikilinks(body):
        upsert_edge(graph, node_id, link, "wikilink")

    wikilink_count = len(parse_wikilinks(body))
    print(f"[graph] 节点更新: {node_id} | domain={domains} | wikilinks={wikilink_count}")
    return True

# ── 全量重建 ──────────────────────────────────────────────────────────────────

def rebuild_all(config, graph):
    vault = Path(config["paths"]["obsidian_vault"])
    note_dirs = [
        vault / config["paths"].get("paper_notes_folder", "10_精读笔记"),
        vault / config["paths"].get("zotero_folder", "60_Zotero导入"),
        vault / config["paths"].get("quick_notes_folder", "20_粗读卡"),
    ]
    ensure_domain_nodes(graph, config)

    count, seen = 0, set()
    for nd in note_dirs:
        for md in glob.glob(str(nd / "**/*.md"), recursive=True):
            if md in seen:
                continue
            seen.add(md)
            fm, _ = extract_frontmatter(md)
            # 只处理有论文标识符的笔记，跳过索引/进度记录等
            if fm.get("doi") or fm.get("arxiv_id") or fm.get("zotero_key"):
                if add_note(md, config, graph, str(vault)):
                    count += 1

    print(f"[graph] 全量重建: {count} 篇笔记 | {len(graph['nodes'])} 节点 | {len(graph['edges'])} 条边")

# ── 索引页刷新 ────────────────────────────────────────────────────────────────

def refresh_index(config):
    vault = Path(config["paths"]["obsidian_vault"])
    index_dir = vault / config["paths"]["system_folder"] / "索引"
    index_dir.mkdir(parents=True, exist_ok=True)

    domain_papers = {d: [] for d in config["domains"]}
    all_papers, seen = [], set()

    note_dirs = [
        vault / config["paths"].get("paper_notes_folder", ""),
        vault / config["paths"].get("zotero_folder", ""),
    ]
    for nd in note_dirs:
        for md in sorted(glob.glob(str(nd / "**/*.md"), recursive=True)):
            if md in seen:
                continue
            seen.add(md)
            fm, _ = extract_frontmatter(md)
            if not (fm.get("doi") or fm.get("arxiv_id") or fm.get("zotero_key")):
                continue
            title = fm.get("title", Path(md).stem)
            rel = Path(md).relative_to(vault)
            domains = fm.get("domain") or []
            if isinstance(domains, str):
                domains = [domains]
            link = rel.with_suffix("").as_posix()
            depth = fm.get("read_depth", "")
            entry = f"- [[{link}|{title}]] | {', '.join(domains)} | {fm.get('year','')} | {depth}"
            all_papers.append(entry)
            for d in domains:
                if d in domain_papers:
                    domain_papers[d].append(entry)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    (index_dir / "文献总索引.md").write_text(
        f"---\ntags: [index, auto-generated]\n---\n# 文献总索引\n\n"
        f"更新时间：{ts}\n\n总计：{len(all_papers)} 篇\n\n" + "\n".join(all_papers),
        encoding="utf-8"
    )
    for domain, papers in domain_papers.items():
        (index_dir / f"{domain}领域索引.md").write_text(
            f"---\ntags: [index, {domain}]\n---\n# {domain} 领域索引\n\n"
            f"更新时间：{ts} | 共 {len(papers)} 篇\n\n"
            + ("\n".join(papers) if papers else "暂无笔记"),
            encoding="utf-8"
        )
    print(f"[index] 刷新完成：{len(all_papers)} 篇，{len(config['domains'])} 个domain")

# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--note",          type=str,        help="按路径添加/更新单篇笔记")
    parser.add_argument("--add-paper",     type=str,        help="按 doi/arxiv_id 添加笔记")
    parser.add_argument("--vault",         type=str,        help="临时覆盖 Vault 路径")
    parser.add_argument("--rebuild",       action="store_true", help="清空后全量重建")
    parser.add_argument("--refresh-index", action="store_true", help="重建索引页")
    args = parser.parse_args()

    config = load_config()
    graph_path = resolve_graph_path(config, args.vault)

    if args.rebuild:
        graph = {"nodes": [], "edges": [], "last_updated": ""}
        rebuild_all(config, graph)
        save_graph(graph, graph_path)
    else:
        graph = load_graph(graph_path)
        if args.add_paper:
            add_paper(args.add_paper, config, graph)
            save_graph(graph, graph_path)
        if args.note:
            if add_note(args.note, config, graph, args.vault):
                save_graph(graph, graph_path)

    if args.refresh_index:
        refresh_index(config)

if __name__ == "__main__":
    main()
