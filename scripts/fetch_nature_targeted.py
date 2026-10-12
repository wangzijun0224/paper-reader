#!/usr/bin/env python3
"""
专项抓取：Nature/Science 正刊 × 两个方向
方向A: 多智能体 + 交叉学科（multi-agent + interdisciplinary science）
方向B: CFD + 数字孪生（CFD + digital twin / surrogate）
去重：排除已在 existing_json 中的论文
输出: JSON，同 tmp_papers.json 格式
"""
import argparse, json, re, time, unicodedata, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from difflib import SequenceMatcher

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user-config.json"

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def _get(url, headers=None, timeout=25):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "boiler-research-system/1.0 (research@example.com)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

def normalize(text):
    t = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"[^\w一-鿿]+", " ", t).strip()

def norm_title(t):
    t = re.sub(r"^\s*\[[^\]]+\]\s*", "", t or "")
    return normalize(t)

def norm_arxiv(v):
    return re.sub(r"v\d+$", "", (v or "").strip().lower())

def norm_doi(v):
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", (v or "").strip().lower())

def same_paper(a, b):
    if norm_arxiv(a.get("arxiv_id")) and norm_arxiv(a.get("arxiv_id")) == norm_arxiv(b.get("arxiv_id")):
        return True
    da, db = norm_doi(a.get("doi")), norm_doi(b.get("doi"))
    if da and da == db:
        return True
    ta, tb = norm_title(a.get("title")), norm_title(b.get("title"))
    if ta and tb and SequenceMatcher(None, ta, tb).ratio() >= 0.94:
        return True
    return False

def dedup_against(new_papers, existing_papers):
    out = []
    for p in new_papers:
        if not any(same_paper(p, e) for e in existing_papers):
            out.append(p)
    return out

def dedup_self(papers):
    unique = []
    for p in papers:
        if not any(same_paper(p, u) for u in unique):
            unique.append(p)
    return unique

# ── Nature/Science 正刊 ISSN ────────────────────────────────
TOP_JOURNAL_ISSNS = {
    "Nature":                          "0028-0836",
    "Nature Energy":                   "2058-7546",
    "Nature Communications":           "2041-1723",
    "Nature Machine Intelligence":     "2522-5839",
    "Nature Chemical Engineering":     "2731-0582",
    "Nature Methods":                  "1548-7091",
    "Nature Reviews Materials":        "2058-8437",
    "npj Computational Materials":     "2057-3960",
    "Science":                         "0036-8075",
    "Science Advances":                "2375-2548",
    "Science Robotics":                "2470-9476",
    "Joule":                           "2542-4351",
    "Cell Reports Physical Science":   "2666-3864",
    "Energy and Environmental Science":"1754-5692",
    "Journal of Computational Physics":"0021-9991",
    "Physics of Fluids":               "1070-6631",
    "Journal of Fluid Mechanics":      "0022-1120",
    "Flow Turbulence and Combustion":  "1386-6184",
    "Physical Review Letters":         "0031-9007",
    "Physical Review Applied":         "2331-7019",
    "PNAS":                            "0027-8424",
    "Advanced Materials":              "0935-9648",
    "ACS Nano":                        "1936-0851",
    "Angewandte Chemie":               "1433-7851",
}

# ── 方向关键词 ────────────────────────────────────────────────
DIRECTION_A_KEYWORDS = [
    "multi-agent", "multi agent", "autonomous research", "AI scientist",
    "agentic AI", "self-evolving", "collaborative agents", "agent framework",
    "large language model agent", "LLM agent", "autonomous discovery",
    "automated science", "robotic scientist", "closed-loop discovery",
    "scientific automation", "foundation model discovery",
]
DIRECTION_B_KEYWORDS = [
    "computational fluid dynamics", "digital twin", "surrogate model",
    "reduced-order model", "physics-informed neural network", "PINN",
    "neural operator", "DeepONet", "FNO", "turbulence modeling",
    "combustion simulation", "CFD surrogate", "flow simulation",
    "data assimilation", "Navier-Stokes", "ROM fluid", "fluid emulator",
]
ALL_KEYWORDS = list(dict.fromkeys(DIRECTION_A_KEYWORDS + DIRECTION_B_KEYWORDS))

def classify_direction(title, abstract):
    text = normalize(title + " " + abstract)
    score_a = sum(1 for k in DIRECTION_A_KEYWORDS if normalize(k) in text)
    score_b = sum(1 for k in DIRECTION_B_KEYWORDS if normalize(k) in text)
    dirs = []
    if score_a >= 1: dirs.append("MultiAgent-Interdisciplinary")
    if score_b >= 1: dirs.append("CFD-DigitalTwin")
    return dirs, score_a + score_b

# ── Crossref：按 ISSN + 关键词 ──────────────────────────────
def fetch_crossref_top(start_date, end_date, max_per_journal=5, mailto="research@example.com"):
    papers = []
    kw_query = " ".join(ALL_KEYWORDS[:8])
    for journal, issn in TOP_JOURNAL_ISSNS.items():
        rows = max_per_journal
        params = urllib.parse.urlencode({
            "query": kw_query,
            "filter": f"issn:{issn},from-pub-date:{start_date},until-pub-date:{end_date}",
            "rows": rows,
            "select": "DOI,title,abstract,author,published,container-title,type",
            "mailto": mailto,
            "sort": "relevance",
        })
        url = f"https://api.crossref.org/works?{params}"
        try:
            data = json.loads(_get(url, timeout=20))
        except Exception as e:
            print(f"[Crossref] {journal}: {e}")
            time.sleep(0.3)
            continue

        for item in data.get("message", {}).get("items", []):
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            if not title:
                continue
            abstract = re.sub(r"<[^>]+>", "", item.get("abstract") or "").strip()
            doi = item.get("DOI", "")
            doc_type = item.get("type", "")  # journal-article, report, ...
            pub = item.get("published") or {}
            date_parts = pub.get("date-parts", [[""]])[0]
            date_str = "-".join(str(d).zfill(2) for d in date_parts if d)
            if not date_str:
                continue
            try:
                y = int(date_str[:4])
                if not (int(str(start_date)[:4]) <= y <= int(str(end_date)[:4])):
                    continue
            except Exception:
                pass
            authors = [
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in (item.get("author") or [])[:5]
            ]
            jname = (item.get("container-title") or [journal])[0]
            papers.append({
                "arxiv_id": None,
                "title": title,
                "abstract": abstract,
                "year": str(date_parts[0]) if date_parts else "",
                "date": date_str,
                "authors": authors,
                "categories": [],
                "source": f"Crossref/{jname}",
                "doi": doi,
                "url": f"https://doi.org/{doi}" if doi else "",
                "needs_download": True,
                "is_target_journal": True,
                "doc_type": doc_type,
            })
        time.sleep(0.25)

    print(f"[Crossref/Top] 获取 {len(papers)} 篇")
    return papers

# ── OpenAlex：按顶刊来源 + 关键词 ───────────────────────────
TOP_ISSN_LIST = list(TOP_JOURNAL_ISSNS.values())

def fetch_openalex_top(start_date, end_date, max_results=80):
    kw_a = " OR ".join(f'"{k}"' for k in DIRECTION_A_KEYWORDS[:5])
    kw_b = " OR ".join(f'"{k}"' for k in DIRECTION_B_KEYWORDS[:5])
    kw = f"({kw_a}) OR ({kw_b})"

    # 用ISSN过滤顶刊
    issn_filter = "|".join(TOP_ISSN_LIST[:15])  # OpenAlex支持|分隔
    filt = (
        f"title_and_abstract.search:{urllib.parse.quote(kw[:300])},"
        f"from_publication_date:{start_date},to_publication_date:{end_date},"
        f"is_paratext:false"
    )
    params = urllib.parse.urlencode({
        "filter": filt,
        "sort": "relevance_score:desc",
        "per-page": max_results,
        "select": "id,doi,title,abstract_inverted_index,authorships,publication_year,publication_date,primary_location,open_access",
        "mailto": "research@example.com"
    })
    url = f"https://api.openalex.org/works?{params}"
    try:
        data = json.loads(_get(url))
    except Exception as e:
        print(f"[OpenAlex/Top] 请求失败: {e}")
        return []

    papers = []
    for w in data.get("results", []):
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        src_name = src.get("display_name", "")
        issn_list = src.get("issn_l", "") or ""
        # 过滤：只留顶刊
        if not any(issn.replace("-","") in str(issn_list).replace("-","")
                   for issn in TOP_ISSN_LIST):
            # 名字匹配作备用
            if not any(j.lower() in src_name.lower() for j in TOP_JOURNAL_ISSNS):
                continue

        inv = w.get("abstract_inverted_index") or {}
        abstract = ""
        if inv:
            words = sorted([(pos, word) for word, positions in inv.items() for pos in positions])
            abstract = " ".join(wd for _, wd in words)

        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        authors = [a["author"]["display_name"] for a in (w.get("authorships") or [])[:5]]
        pub_date = w.get("publication_date", "")
        oa = w.get("open_access") or {}

        papers.append({
            "arxiv_id": None,
            "title": w.get("title") or "",
            "abstract": abstract,
            "year": str(w.get("publication_year", "")),
            "date": pub_date,
            "authors": authors,
            "categories": [],
            "source": f"OpenAlex/{src_name}" if src_name else "OpenAlex",
            "doi": doi,
            "url": oa.get("oa_url") or (f"https://doi.org/{doi}" if doi else ""),
            "needs_download": not bool(oa.get("is_oa")),
            "is_target_journal": True,
        })
    print(f"[OpenAlex/Top] 获取 {len(papers)} 篇（顶刊过滤后）")
    return papers

# ── Scopus：顶刊方向精准搜索 ─────────────────────────────────
def fetch_scopus_top(start_date, end_date, api_key=None, target_count=60):
    if not api_key:
        print("[Scopus/Top] 跳过（无key）")
        return []
    issn_filter = " OR ".join(f'ISSN({v})' for v in list(TOP_JOURNAL_ISSNS.values())[:20])
    kw_a = " OR ".join(f'"{k}"' for k in DIRECTION_A_KEYWORDS[:4])
    kw_b = " OR ".join(f'"{k}"' for k in DIRECTION_B_KEYWORDS[:4])
    query = (
        f"TITLE-ABS-KEY(({kw_a}) OR ({kw_b})) AND ({issn_filter}) "
        f"AND PUBYEAR > {int(str(start_date)[:4])-1} AND PUBYEAR <= {int(str(end_date)[:4])}"
    )
    fields = "dc:title,dc:description,prism:doi,dc:creator,prism:publicationName,prism:coverDate,prism:issn"
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
    all_papers = []
    page_size = 25
    for start in range(0, target_count, page_size):
        params = urllib.parse.urlencode({
            "query": query,
            "field": fields,
            "count": page_size,
            "start": start,
            "sort": "coverDate-desc",
        })
        url = f"https://api.elsevier.com/content/search/scopus?{params}"
        try:
            data = json.loads(_get(url, headers=headers))
        except Exception as e:
            print(f"[Scopus/Top] 第{start//page_size+1}页失败: {e}")
            break
        batch = data.get("search-results", {}).get("entry", []) or []
        for e in batch:
            title = e.get("dc:title", "")
            if not title:
                continue
            abstract = re.sub(r"<[^>]+>", "", e.get("dc:description") or "").strip()
            doi = e.get("prism:doi", "")
            journal = e.get("prism:publicationName", "")
            date = (e.get("prism:coverDate") or "")[:10]
            try:
                y = int(date[:4])
                if not (int(str(start_date)[:4]) <= y <= int(str(end_date)[:4])):
                    continue
            except Exception:
                pass
            creator = e.get("dc:creator", "")
            all_papers.append({
                "arxiv_id": None,
                "title": title,
                "abstract": abstract,
                "year": date[:4] if date else "",
                "date": date,
                "authors": [creator] if creator else [],
                "categories": [],
                "source": f"Scopus/{journal}" if journal else "Scopus",
                "doi": doi,
                "url": f"https://doi.org/{doi}" if doi else "",
                "needs_download": True,
                "is_target_journal": True,
            })
        if len(batch) < page_size:
            break
        time.sleep(0.5)

    print(f"[Scopus/Top] 获取 {len(all_papers)} 篇")
    return all_papers

# ── 评分（方向专用）────────────────────────────────────────
def score_targeted(paper):
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    text = normalize(title + " " + abstract)
    title_n = normalize(title)

    dirs, dir_score = classify_direction(title, abstract)

    # 负向过滤（非相关领域）
    neg = ["medical imaging", "drug delivery", "cancer treatment", "social media",
           "recommendation system", "weather forecast", "autonomous driving vehicle",
           "course promotion", "product advertisement"]
    for n in neg:
        if normalize(n) in text:
            return -999, dirs

    score = float(dir_score) * 1.5

    # 顶刊加成
    if paper.get("is_target_journal"):
        score += 3.0

    # 关键词标题命中加成
    for k in DIRECTION_A_KEYWORDS + DIRECTION_B_KEYWORDS:
        if normalize(k) in title_n:
            score += 2.0
        elif normalize(k) in text:
            score += 0.8

    # 多方向交叉加成（最重要！）
    if len(dirs) >= 2:
        score += 4.0
    elif len(dirs) == 1:
        score += 1.0

    # Nature/Science 顶刊额外加成
    src = paper.get("source", "").lower()
    for top in ["nature", "science", "cell", "joule", "pnas", "physical review"]:
        if top in src:
            score += 2.0
            break

    return round(score, 2), dirs

def load_seen_papers(path):
    """统一工具：加载历史记录（同 fetch_papers.py 格式）"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # 支持两种格式：{papers:[...]} 或 {deep_read:[...], quick_read:[...]}
        if "papers" in data:
            return data["papers"]
        return data.get("deep_read", []) + data.get("quick_read", [])
    except Exception as e:
        print(f"[去重] 无法加载 {path}: {e}")
        return []

def save_seen_papers(seen_path, new_papers, existing_seen=None):
    """将新论文追加到历史记录"""
    from datetime import datetime
    records = list(existing_seen or [])
    today = datetime.now().strftime("%Y-%m-%d")
    existing_keys = {
        norm_arxiv(r.get("arxiv_id")) or norm_doi(r.get("doi")) or norm_title(r.get("title",""))
        for r in records
    }
    for p in new_papers:
        key = norm_arxiv(p.get("arxiv_id")) or norm_doi(p.get("doi")) or norm_title(p.get("title",""))
        if key and key not in existing_keys:
            records.append({
                "arxiv_id": p.get("arxiv_id") or "",
                "doi": p.get("doi") or "",
                "title": (p.get("title") or "").strip(),
                "date_seen": today,
                "source": p.get("source", ""),
            })
            existing_keys.add(key)
    Path(seen_path).parent.mkdir(parents=True, exist_ok=True)
    with open(seen_path, "w", encoding="utf-8") as f:
        json.dump({"last_updated": today, "papers": records}, f, ensure_ascii=False, indent=2)
    print(f"[历史去重] seen_papers.json 更新至 {len(records)} 篇")
    return records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-06-15")
    parser.add_argument("--existing", default="",
                        help="已有论文JSON（去重用，旧式接口，优先用 --exclude-seen）")
    parser.add_argument("--exclude-seen", type=str, metavar="PATH",
                        help="seen_papers.json 路径，过滤历史已见论文（推荐）")
    parser.add_argument("--update-seen", action="store_true",
                        help="运行完成后将本次选出的论文追加到 --exclude-seen 文件")
    parser.add_argument("--out", required=True)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--deep-n", type=int, default=5, help="精读上限，默认5")
    parser.add_argument("--directions", type=str, default="A,B",
                        help="启用方向，逗号分隔：A=多智能体, B=CFD+数字孪生, AB=两者（默认AB）")
    args = parser.parse_args()

    config = load_config()
    api_keys = config.get("api_keys", {})
    scopus_key = api_keys.get("scopus")

    # 兼容旧式 --existing 和新式 --exclude-seen
    seen_path = args.exclude_seen or ""
    existing = []
    if seen_path:
        existing = load_seen_papers(seen_path)
        print(f"[去重] 已有 {len(existing)} 篇历史记录作为排除基准")
    elif args.existing:
        existing = load_seen_papers(args.existing)
        print(f"[去重] 已有 {len(existing)} 篇作为排除基准（旧式）")

    all_papers = []
    all_papers.extend(fetch_crossref_top(args.start_date, args.end_date, max_per_journal=6))
    all_papers.extend(fetch_openalex_top(args.start_date, args.end_date, max_results=100))
    all_papers.extend(fetch_scopus_top(args.start_date, args.end_date,
                                        api_key=scopus_key, target_count=80))

    # 自身去重
    unique = dedup_self(all_papers)
    # 对比已有去重
    unique = dedup_against(unique, existing)

    # 评分 + 方向标注
    scored = []
    for p in unique:
        s, dirs = score_targeted(p)
        if s > 0 and dirs:  # 必须命中至少一个方向
            p["score"] = s
            p["domains"] = dirs
            scored.append(p)

    scored.sort(key=lambda x: x["score"], reverse=True)

    # 按方向均衡：A/B各至少保留若干
    top_n = args.top_n
    dir_a = [p for p in scored if "MultiAgent-Interdisciplinary" in p["domains"]]
    dir_b = [p for p in scored if "CFD-DigitalTwin" in p["domains"]]
    cross  = [p for p in scored if len(p["domains"]) >= 2]

    # 优先保留交叉，然后按分数合并
    selected_ids = set()
    final = []
    for p in cross:
        pid = norm_doi(p.get("doi")) or norm_title(p.get("title"))
        if pid not in selected_ids:
            final.append(p)
            selected_ids.add(pid)
    for p in scored:
        if len(final) >= top_n:
            break
        pid = norm_doi(p.get("doi")) or norm_title(p.get("title"))
        if pid not in selected_ids:
            final.append(p)
            selected_ids.add(pid)

    final = final[:top_n]

    # 精读/粗读分类
    deep_n = args.deep_n
    deep_read, quick_read = [], []
    for p in final:
        if p["score"] >= 8.0 and len(deep_read) < deep_n:
            p["read_depth"] = "精读"
            deep_read.append(p)
        else:
            p["read_depth"] = "粗读"
            quick_read.append(p)

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "date_range": {"start": args.start_date, "end": args.end_date},
        "total_fetched": len(unique),
        "run_type": "targeted_nature_science",
        "directions": ["MultiAgent-Interdisciplinary", "CFD-DigitalTwin"],
        "run_params": {
            "top_n": top_n,
            "deep_n": deep_n,
            "directions": args.directions,
            "exclude_seen": seen_path,
        },
        "sources": {
            "crossref_top": sum(1 for p in unique if "Crossref" in p.get("source","")),
            "openalex_top": sum(1 for p in unique if "OpenAlex" in p.get("source","")),
            "scopus_top": sum(1 for p in unique if "Scopus" in p.get("source","")),
        },
        "deep_read": deep_read,
        "quick_read": quick_read,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 更新历史记录
    if args.update_seen and seen_path:
        all_selected = deep_read + quick_read
        save_seen_papers(seen_path, all_selected, existing)

    print(f"完成: 候选{len(unique)}篇 → 选出{len(final)}篇（精读{len(deep_read)}，粗读{len(quick_read)}）")
    print(f"方向A(多智能体): {sum(1 for p in final if 'MultiAgent-Interdisciplinary' in p['domains'])}篇")
    print(f"方向B(CFD+DT): {sum(1 for p in final if 'CFD-DigitalTwin' in p['domains'])}篇")
    print(f"→ {args.out}")

if __name__ == "__main__":
    main()
