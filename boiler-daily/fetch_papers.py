#!/usr/bin/env python3
"""
多源论文抓取脚本
来源: arXiv + OpenAlex + HuggingFace Daily Papers + Semantic Scholar
输出: JSON文件，字段包含 title/abstract/doi/arxiv_id/source/score/domains/year/authors
"""
import argparse, json, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "user-config.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "boiler-research-system/1.0 (research@example.com)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)  # add_header 保留原始大小写，不做 capitalize()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")

# ── arXiv ────────────────────────────────────────────────────
def fetch_arxiv(categories, keywords, days=1, max_results=200):
    end = _utcnow()
    start = end - timedelta(days=days)
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    kw_query = " OR ".join(f'(ti:"{k}" OR abs:"{k}")' for k in keywords[:10])
    query = f"({cat_query}) AND ({kw_query})"
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    })
    try:
        data = _get(f"https://export.arxiv.org/api/query?{params}")
    except Exception as e:
        print(f"[arXiv] 请求失败: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(data)
    papers = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        abstract = (entry.find("atom:summary", ns).text or "").strip().replace("\n", " ")
        pub_date = entry.find("atom:published", ns).text[:10]
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
        cats = [c.get("term") for c in entry.findall("atom:category", ns)]
        papers.append({
            "arxiv_id": arxiv_id, "title": title, "abstract": abstract,
            "year": pub_date[:4], "date": pub_date, "authors": authors[:5],
            "categories": cats, "source": "arXiv", "doi": None,
            "url": f"https://arxiv.org/abs/{arxiv_id}"
        })
    print(f"[arXiv] 获取 {len(papers)} 篇")
    return papers

# ── HuggingFace Daily Papers ──────────────────────────────────
def fetch_huggingface(days=1):
    """
    HuggingFace 每日热门论文（社区 upvote 排行）
    API: https://huggingface.co/api/daily_papers?date=YYYY-MM-DD
    无需 API key，返回带 arxiv_id 的列表
    """
    papers = []
    for d in range(days):
        date_str = (_utcnow() - timedelta(days=d)).strftime("%Y-%m-%d")
        url = f"https://huggingface.co/api/daily_papers?date={date_str}"
        try:
            data = json.loads(_get(url))
        except Exception as e:
            print(f"[HuggingFace] {date_str} 请求失败: {e}")
            continue
        for item in data:
            p = item.get("paper", {})
            arxiv_id = p.get("id", "")
            if not arxiv_id:
                continue
            authors = [a.get("name", "") for a in p.get("authors", [])[:5]]
            papers.append({
                "arxiv_id": arxiv_id,
                "title": p.get("title", ""),
                "abstract": p.get("summary", ""),
                "year": (p.get("publishedAt") or date_str)[:4],
                "date": (p.get("publishedAt") or date_str)[:10],
                "authors": authors,
                "categories": [],
                "source": f"HuggingFace(upvotes:{item.get('upvotes',0)})",
                "doi": None,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "hf_upvotes": item.get("upvotes", 0)
            })
    print(f"[HuggingFace] 获取 {len(papers)} 篇")
    return papers

# ── Semantic Scholar ──────────────────────────────────────────
def fetch_semantic_scholar(keywords, days=1, max_results=50, api_key=None):
    """
    Semantic Scholar 论文搜索
    无 key：10 req/min；免费 key：100 req/min
    申请免费 key: https://www.semanticscholar.org/product/api
    """
    since = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    query = " OR ".join(f'"{k}"' for k in keywords[:8])
    fields = "title,abstract,year,authors,externalIds,publicationDate,venue"
    params = urllib.parse.urlencode({
        "query": query,
        "fields": fields,
        "limit": max_results,
        "publicationDateOrYear": f"{since}:"
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    try:
        data = json.loads(_get(url, headers=headers))
    except Exception as e:
        print(f"[S2] 请求失败: {e}")
        return []

    papers = []
    for w in data.get("data", []):
        ext_ids = w.get("externalIds") or {}
        arxiv_id = ext_ids.get("ArXiv")
        doi = ext_ids.get("DOI")
        authors = [a.get("name", "") for a in (w.get("authors") or [])[:5]]
        papers.append({
            "arxiv_id": arxiv_id,
            "title": w.get("title", ""),
            "abstract": w.get("abstract") or "",
            "year": str(w.get("year") or ""),
            "date": w.get("publicationDate") or "",
            "authors": authors,
            "categories": [],
            "source": f"SemanticScholar/{w.get('venue','')}" if w.get("venue") else "SemanticScholar",
            "doi": doi,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else (f"https://doi.org/{doi}" if doi else "")
        })
    print(f"[S2] 获取 {len(papers)} 篇")
    return papers

# ── 目标期刊 ISSN 列表（Crossref/Scopus 用）────────────────────
JOURNAL_ISSNS = {
    # ── Nature 系列 ──
    "Nature":                          "0028-0836",
    "Nature Energy":                   "2058-7546",
    "Nature Communications":           "2041-1723",
    "Nature Machine Intelligence":     "2522-5839",
    "Nature Chemical Engineering":     "2731-0582",
    "npj Computational Materials":     "2057-3960",
    # ── Science 系列 ──
    "Science":                         "0036-8075",
    "Science Advances":                "2375-2548",
    # ── Cell Press ──
    "Joule":                           "2542-4351",
    "Cell Reports Physical Science":   "2666-3864",
    # ── RSC ──
    "Energy and Environmental Science":"1754-5692",
    # ── CFD 核心期刊 ──
    "Journal of Computational Physics":           "0021-9991",   # JCP - CFD顶刊
    "Computers and Fluids":                       "0045-7930",   # Elsevier
    "International Journal of Heat and Fluid Flow":"0142-727X",  # Elsevier
    "Physics of Fluids":                          "1070-6631",   # AIP
    "Journal of Fluid Mechanics":                 "0022-1120",   # Cambridge
    "Flow Turbulence and Combustion":             "1386-6184",   # Springer
    "Theoretical and Computational Fluid Dynamics":"0935-4964",  # Springer
    "International Journal for Numerical Methods in Fluids": "0271-2091",  # Wiley
    "Particuology":                               "1674-2001",   # 颗粒学(DEM-CFD)
    "Powder Technology":                          "0032-5910",   # 粉体(煤粉相关)
    "AIAA Journal":                               "0001-1452",   # 航空CFD
    # ── Elsevier 燃烧/热工 ──
    "Combustion and Flame":            "0010-2180",
    "Progress in Energy and Combustion Science": "0360-1285",
    "Fuel":                            "0016-2361",
    "Applied Thermal Engineering":     "1359-4311",
    "International Journal of Heat and Mass Transfer": "0017-9310",
    "Chemical Engineering Science":    "0009-2509",
    "Chemical Engineering Journal":    "1385-8947",   # CEJ
    # ── Elsevier 能源 ──
    "Applied Energy":                  "0306-2619",
    "Energy":                          "0360-5442",
    "Energy Conversion and Management":"0196-8904",
    "Renewable and Sustainable Energy Reviews": "1364-0321",
    "Energy and AI":                   "2666-5468",   # 能源+AI专刊
    "International Journal of Hydrogen Energy": "0360-3199",
    # ── Elsevier AI/控制 ──
    "Expert Systems with Applications":"0957-4174",
    "Engineering Applications of Artificial Intelligence": "0952-1976",
    "Knowledge-Based Systems":         "0950-7051",
    "Computers and Chemical Engineering": "0098-1354",
    "Neurocomputing":                  "0925-2312",
    "Applied Soft Computing":          "1568-4946",
    # ── 顶级 AI 期刊 ──
    "Journal of Machine Learning Research": "1532-4435",   # JMLR
    "Artificial Intelligence":         "0004-3702",
    "Transactions on Machine Learning Research": "2835-8856",  # TMLR
    # ── IEEE 期刊（Crossref备用，IEEE API主抓）──
    "IEEE Transactions on Industrial Electronics":   "0278-0046",
    "IEEE Transactions on Industrial Informatics":   "1551-3203",
    "IEEE Transactions on Energy Conversion":        "0885-8969",
    "IEEE Transactions on Power Systems":            "0885-8950",
    "IEEE Transactions on Neural Networks and Learning Systems": "2162-237X",
    "IEEE Transactions on Intelligent Transportation Systems": "1524-9050",
    "IEEE Transactions on Automation Science and Engineering": "1545-5955",
    "IEEE Transactions on Systems Man and Cybernetics Systems": "2168-2216",
    "IEEE Transactions on Control Systems Technology": "1063-6536",
    "IEEE Transactions on Cybernetics": "2168-2267",
    "IEEE Transactions on Pattern Analysis and Machine Intelligence": "0162-8828",
    "IEEE Access":                     "2169-3536",
}

# IEEE API 目标期刊名
IEEE_TARGET_JOURNALS = [
    "IEEE Transactions on Industrial Electronics",
    "IEEE Transactions on Industrial Informatics",
    "IEEE Transactions on Energy Conversion",
    "IEEE Transactions on Power Systems",
    "IEEE Transactions on Neural Networks and Learning Systems",
    "IEEE Transactions on Intelligent Transportation Systems",
    "IEEE Transactions on Automation Science and Engineering",
    "IEEE Transactions on Systems, Man, and Cybernetics: Systems",
    "IEEE Transactions on Control Systems Technology",
    "IEEE Transactions on Cybernetics",
    "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "IEEE Access",
]

# OpenReview 顶级 AI 会议（接受论文）
AI_CONFERENCES = [
    ("ICLR.cc/2025/Conference",      "ICLR 2025"),
    ("NeurIPS.cc/2024/Conference",   "NeurIPS 2024"),
    ("ICML.cc/2024/Conference",      "ICML 2024"),
    ("AAAI.org/2025/Conference",     "AAAI 2025"),
]

def fetch_scopus(keywords, days=1, target_count=100, api_key=None):
    """
    Elsevier Scopus API，分页抓取约 target_count 篇
    单次上限25条，每页间隔0.5s，每日额度5000次调用
    """
    import re
    if not api_key:
        print("[Scopus] 未配置 api_keys.scopus，跳过")
        return []

    since = _utcnow() - timedelta(days=days)
    kw_parts = " OR ".join(f'"{k}"' for k in keywords[:6])
    query = f"TITLE-ABS-KEY({kw_parts}) AND SRCTYPE(j) AND PUBYEAR > {since.year - 1}"
    fields = "dc:title,dc:description,prism:doi,dc:creator,prism:publicationName,prism:coverDate,prism:issn"
    encoded_query = urllib.parse.quote(query)
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
    target_issns = {v.replace("-", "") for v in JOURNAL_ISSNS.values()}

    all_entries = []
    page_size = 25
    for start in range(0, target_count, page_size):
        url = (
            f"https://api.elsevier.com/content/search/scopus"
            f"?query={encoded_query}"
            f"&field={fields}"
            f"&count={page_size}"
            f"&start={start}"
            f"&sort=coverDate-desc"
        )
        try:
            data = json.loads(_get(url, headers=headers))
        except Exception as e:
            print(f"[Scopus] 第{start//page_size+1}页失败: {e}")
            break
        batch = data.get("search-results", {}).get("entry", []) or []
        all_entries.extend(batch)
        if len(batch) < page_size:
            break
        time.sleep(0.5)

    # 目标期刊优先排列
    target_entries = [(e, True) for e in all_entries if (e.get("prism:issn") or "").replace("-","") in target_issns]
    other_entries  = [(e, False) for e in all_entries if (e.get("prism:issn") or "").replace("-","") not in target_issns]
    selected = target_entries + other_entries

    papers = []
    for entry, is_target in selected:
        title = entry.get("dc:title", "")
        if not title:
            continue
        abstract = re.sub(r"<[^>]+>", "", entry.get("dc:description") or "").strip()
        doi = entry.get("prism:doi", "")
        journal = entry.get("prism:publicationName", "")
        date = entry.get("prism:coverDate", "")
        creator = entry.get("dc:creator", "")
        papers.append({
            "arxiv_id": None,
            "title": title,
            "abstract": abstract,
            "year": date[:4] if date else "",
            "date": date[:10] if date else "",
            "authors": [creator] if creator else [],
            "categories": [],
            "source": f"Scopus/{journal}" if journal else "Scopus",
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else "",
            "needs_download": True,
            "is_target_journal": is_target,
        })

    target_cnt = sum(1 for p in papers if p.get("is_target_journal"))
    print(f"[Scopus] 获取 {len(papers)} 篇（目标期刊 {target_cnt} 篇）")
    return papers


def fetch_openreview(keywords, conferences=None, max_per_conf=50):
    """
    OpenReview API — 抓取顶级 AI 会议已接受论文
    覆盖: ICLR / NeurIPS / ICML / AAAI（无需key）
    会议论文通常也在 arXiv，此函数补充官方接受版本
    """
    if conferences is None:
        conferences = AI_CONFERENCES
    kw_set = {k.lower() for k in keywords}
    papers = []

    for venue_id, conf_name in conferences:
        # 先尝试获取 oral/spotlight/poster 接受论文
        for decision in ["Oral", "Spotlight", "Poster", ""]:
            inv = f"{venue_id}/-/{'Submission' if not decision else decision + '_Submission'}"
            url = (
                f"https://api.openreview.net/notes"
                f"?invitation={urllib.parse.quote(inv)}"
                f"&limit={max_per_conf}&offset=0"
                f"&select=id,content.title,content.abstract,content.keywords,content.authors"
            )
            try:
                data = json.loads(_get(url, timeout=15))
            except Exception:
                continue

            notes = data.get("notes", [])
            if not notes:
                continue

            for note in notes:
                content = note.get("content", {})
                title = (content.get("title") or {})
                title = title.get("value", "") if isinstance(title, dict) else str(title)
                abstract = (content.get("abstract") or {})
                abstract = abstract.get("value", "") if isinstance(abstract, dict) else str(abstract)
                if not title:
                    continue

                # 关键词过滤（只留与研究方向相关的）
                text = (title + " " + abstract).lower()
                if not any(k in text for k in kw_set):
                    continue

                kws = content.get("keywords", {})
                kws = kws.get("value", []) if isinstance(kws, dict) else []
                authors_raw = content.get("authors", {})
                authors = authors_raw.get("value", []) if isinstance(authors_raw, dict) else []

                papers.append({
                    "arxiv_id": None,
                    "title": title,
                    "abstract": abstract,
                    "year": "2024" if "2024" in venue_id else "2025",
                    "date": "",
                    "authors": authors[:5],
                    "categories": kws[:3],
                    "source": f"OpenReview/{conf_name}",
                    "doi": "",
                    "url": f"https://openreview.net/forum?id={note.get('id','')}",
                    "needs_download": False,  # OpenReview 全文可直接访问
                    "is_target_journal": False,
                })
            if notes:
                break  # 找到数据后跳出 decision 循环

    print(f"[OpenReview] 获取 {len(papers)} 篇（AI会议）")
    return papers


def fetch_crossref_journals(keywords, days=1, max_results=30, mailto="research@example.com"):
    """
    通过 Crossref API 按期刊 ISSN 抓取最新论文摘要
    无需 API key，免费使用
    """
    since = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    kw_query = " ".join(keywords[:6])
    all_papers = []

    # 按 ISSN 批量查询（每个期刊独立查，避免超时）
    for journal_name, issn in JOURNAL_ISSNS.items():
        params = urllib.parse.urlencode({
            "query": kw_query,
            "filter": f"issn:{issn},from-pub-date:{since}",
            "rows": min(max_results // len(JOURNAL_ISSNS) + 1, 10),
            "select": "DOI,title,abstract,author,published,container-title",
            "mailto": mailto
        })
        url = f"https://api.crossref.org/works?{params}"
        try:
            data = json.loads(_get(url, timeout=20))
        except Exception as e:
            print(f"[Crossref] {journal_name} 请求失败: {e}")
            continue

        for item in data.get("message", {}).get("items", []):
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            if not title:
                continue
            abstract = item.get("abstract") or ""
            # 去除 Crossref 返回的 JATS XML 标签
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
            doi = item.get("DOI", "")
            pub = item.get("published") or {}
            date_parts = pub.get("date-parts", [[""]])[0]
            date_str = "-".join(str(d).zfill(2) for d in date_parts if d)
            authors = [
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in (item.get("author") or [])[:5]
            ]
            journal = (item.get("container-title") or [journal_name])[0]
            all_papers.append({
                "arxiv_id": None,
                "title": title,
                "abstract": abstract,
                "year": str(date_parts[0]) if date_parts else "",
                "date": date_str,
                "authors": authors,
                "categories": [],
                "source": f"Crossref/{journal}",
                "doi": doi,
                "url": f"https://doi.org/{doi}" if doi else "",
                "needs_download": True,  # 标记需要手动下载全文
            })
        time.sleep(0.2)  # Crossref polite 间隔

    print(f"[Crossref] 获取 {len(all_papers)} 篇（Elsevier+IEEE期刊）")
    return all_papers


def fetch_ieee(keywords, days=1, max_results=25, api_key=None):
    """
    IEEE Xplore API — 只抓 IEEE_TARGET_JOURNALS 中的期刊
    key 状态 "waiting" 通常几分钟到几小时后激活
    """
    if not api_key:
        print("[IEEE] 未配置 api_keys.ieee，跳过")
        return []

    since = _utcnow() - timedelta(days=days)
    # IEEE API 使用 start_year/start_month 日期过滤
    kw = " OR ".join(f'"{k}"' for k in keywords[:6])
    # 按目标期刊逐本查询，确保精准
    all_papers = []
    queried = 0
    for journal in IEEE_TARGET_JOURNALS:
        if queried >= 5:  # 每天 200 次调用限额，控制查询数
            break
        params = urllib.parse.urlencode({
            "querytext": kw,
            "publication_title": journal,
            "start_year": since.year,
            "max_records": min(5, max_results // len(IEEE_TARGET_JOURNALS) + 1),
            "sort_order": "desc",
            "sort_field": "publication_date",
            "apikey": api_key
        })
        url = f"https://ieeexploreapi.ieee.org/api/v1/search/articles?{params}"
        try:
            data = json.loads(_get(url, timeout=15))
        except Exception as e:
            print(f"[IEEE] {journal[:30]} 失败: {e}")
            continue

        for item in data.get("articles", []):
            doi = item.get("doi", "")
            authors = [a.get("full_name", "") for a in (item.get("authors", {}).get("authors") or [])[:5]]
            all_papers.append({
                "arxiv_id": None,
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "year": str(item.get("publication_year", "")),
                "date": item.get("publication_date", ""),
                "authors": authors,
                "categories": [],
                "source": f"IEEE/{item.get('publication_title', journal)}",
                "doi": doi,
                "url": item.get("html_url") or (f"https://doi.org/{doi}" if doi else ""),
                "needs_download": True,
                "is_target_journal": True,
            })
        queried += 1
        time.sleep(0.3)

    print(f"[IEEE] 获取 {len(all_papers)} 篇")
    return all_papers


# ── OpenAlex 期刊 ─────────────────────────────────────────────
def fetch_openalex(keywords, days=1, max_results=30):
    since = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    kw = " OR ".join(f'"{k}"' for k in keywords[:5])
    params = urllib.parse.urlencode({
        "filter": f"title_and_abstract.search:{kw},from_publication_date:{since},is_paratext:false",
        "sort": "publication_date:desc",
        "per-page": max_results,
        "select": "id,doi,title,abstract_inverted_index,authorships,publication_year,publication_date,primary_location"
    })
    url = f"https://api.openalex.org/works?{params}&mailto=research@example.com"
    try:
        data = json.loads(_get(url))
    except Exception as e:
        print(f"[OpenAlex] 请求失败: {e}")
        return []

    papers = []
    for w in data.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        abstract = ""
        if inv:
            words = sorted([(pos, word) for word, positions in inv.items() for pos in positions])
            abstract = " ".join(wd for _, wd in words)
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        authors = [a["author"]["display_name"] for a in (w.get("authorships") or [])[:5]]
        loc = w.get("primary_location") or {}
        source_name = (loc.get("source") or {}).get("display_name", "")
        papers.append({
            "arxiv_id": None, "title": w.get("title") or "",
            "abstract": abstract,
            "year": str(w.get("publication_year", "")),
            "date": w.get("publication_date", ""),
            "authors": authors, "categories": [],
            "source": f"OpenAlex/{source_name}" if source_name else "OpenAlex",
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else ""
        })
    print(f"[OpenAlex] 获取 {len(papers)} 篇")
    return papers

# ── 评分与域标注 ──────────────────────────────────────────────
def score_paper(paper, config):
    cfg = config["daily_papers"]
    text = (paper["title"] + " " + paper["abstract"]).lower()
    for neg in cfg["negative_keywords"]:
        if neg.lower() in text:
            return -999, []

    score = 0.0
    for kw in cfg["keywords"]:
        kl = kw.lower()
        if kl in paper["title"].lower():
            score += 3.0
        elif kl in text:
            score += 1.0

    for cat in paper.get("categories", []):
        if cat in cfg["arxiv_categories"]:
            score += 1.0

    # HuggingFace upvotes 加成（热门论文额外 +1~+3）
    upvotes = paper.get("hf_upvotes", 0)
    if upvotes >= 100:
        score += 3.0
    elif upvotes >= 30:
        score += 1.5
    elif upvotes >= 10:
        score += 0.5

    matched_domains = []
    for domain, boost_kws in cfg["domain_boost_keywords"].items():
        hits = sum(1 for k in boost_kws if k.lower() in text)
        if hits >= 1:
            matched_domains.append(domain)
            score += hits * 0.5

    if len(matched_domains) >= 2:
        score += 1.5
    if len(matched_domains) >= 3:
        score += 1.0

    return round(score, 2), matched_domains

def classify_depth(papers, config):
    cfg = config["daily_papers"]
    threshold = cfg["auto_deep_read_score_threshold"]
    kw_threshold = cfg["auto_deep_read_keyword_threshold"]
    max_deep = cfg["auto_deep_read_max"]
    top_n = cfg["top_n"]
    # 期刊论文（Crossref/IEEE）保留名额，避免被arXiv/HF淹没
    journal_reserved = cfg.get("journal_reserved_slots", 5)

    valid = [p for p in papers if p["score"] >= 0]

    # 分离期刊论文和预印本/会议论文
    journal_papers = [p for p in valid if p.get("needs_download")]
    other_papers = [p for p in valid if not p.get("needs_download")]

    def mark_depth(p):
        is_deep = (
            p["score"] >= threshold or
            (len(p["domains"]) >= 2 and p["score"] >= 6.5) or
            any(
                len([k for k in cfg["domain_boost_keywords"].get(d, [])
                     if k.lower() in (p["title"] + p["abstract"]).lower()]) >= kw_threshold
                for d in p["domains"]
            )
        )
        return is_deep

    deep_read, quick_read = [], []

    # 先从非期刊论文里选，留出 journal_reserved 个名额
    other_budget = top_n - journal_reserved
    for p in other_papers:
        if len(deep_read) + len(quick_read) >= other_budget:
            break
        if mark_depth(p) and len(deep_read) < max_deep:
            p["read_depth"] = "精读"
            deep_read.append(p)
        else:
            p["read_depth"] = "粗读"
            quick_read.append(p)

    # 再从期刊论文里选 journal_reserved 篇（按分数排序，但分数>0即可入选）
    for p in journal_papers[:journal_reserved]:
        if mark_depth(p) and len(deep_read) < max_deep:
            p["read_depth"] = "精读"
            deep_read.append(p)
        else:
            p["read_depth"] = "粗读"
            quick_read.append(p)

    return deep_read, quick_read

# ── 主流程 ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--no-hf", action="store_true", help="跳过HuggingFace源")
    parser.add_argument("--no-s2", action="store_true", help="跳过Semantic Scholar源")
    parser.add_argument("--no-crossref", action="store_true", help="跳过Crossref期刊源")
    parser.add_argument("--no-scopus", action="store_true", help="跳过Scopus源")
    parser.add_argument("--no-ieee", action="store_true", help="跳过IEEE源")
    parser.add_argument("--no-openreview", action="store_true", help="跳过AI会议源")
    args = parser.parse_args()

    config = load_config()
    cfg = config["daily_papers"]
    api_keys = config.get("api_keys", {})
    s2_key = api_keys.get("semantic_scholar")
    ieee_key = api_keys.get("ieee")
    scopus_key = api_keys.get("scopus")
    crossref_mailto = config.get("journal_sources", {}).get("crossref_mailto", "research@example.com")

    all_papers = []
    all_papers.extend(fetch_arxiv(cfg["arxiv_categories"], cfg["keywords"], days=args.days))
    all_papers.extend(fetch_openalex(cfg["keywords"], days=args.days))

    if not args.no_hf:
        all_papers.extend(fetch_huggingface(days=args.days))

    if not args.no_s2:
        time.sleep(1)
        all_papers.extend(fetch_semantic_scholar(cfg["keywords"], days=args.days, api_key=s2_key))

    if not args.no_scopus:
        scopus_target = cfg.get("scopus_target_count", 100)
        all_papers.extend(fetch_scopus(cfg["keywords"], days=args.days, target_count=scopus_target, api_key=scopus_key))

    if not args.no_crossref:
        all_papers.extend(fetch_crossref_journals(cfg["keywords"], days=args.days, mailto=crossref_mailto))

    if not args.no_ieee:
        all_papers.extend(fetch_ieee(cfg["keywords"], days=args.days, api_key=ieee_key))

    if not args.no_openreview:
        all_papers.extend(fetch_openreview(cfg["keywords"]))

    # 去重：同一篇论文可能同时出现在 arXiv + Scopus + Crossref
    # 策略：维护 arxiv_id 集合和 doi 集合，两者任一命中即视为重复
    seen_arxiv = set()
    seen_doi = set()
    seen_title = set()
    unique = []
    for p in all_papers:
        aid = (p.get("arxiv_id") or "").strip()
        doi = (p.get("doi") or "").strip().lower()
        title_key = p.get("title", "")[:50].lower().strip()

        if aid and aid in seen_arxiv:
            continue
        if doi and doi in seen_doi:
            continue
        if not aid and not doi and title_key and title_key in seen_title:
            continue

        if aid:
            seen_arxiv.add(aid)
        if doi:
            seen_doi.add(doi)
        if title_key:
            seen_title.add(title_key)
        unique.append(p)

    for p in unique:
        p["score"], p["domains"] = score_paper(p, config)

    unique.sort(key=lambda x: x["score"], reverse=True)
    deep_read, quick_read = classify_depth(unique, config)

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_fetched": len(unique),
        "sources": {
            "arxiv": sum(1 for p in unique if p["source"] == "arXiv"),
            "openalex": sum(1 for p in unique if "OpenAlex" in p["source"]),
            "huggingface": sum(1 for p in unique if "HuggingFace" in p["source"]),
            "semantic_scholar": sum(1 for p in unique if "SemanticScholar" in p["source"]),
            "scopus": sum(1 for p in unique if "Scopus" in p["source"]),
            "crossref": sum(1 for p in unique if "Crossref" in p["source"]),
            "ieee": sum(1 for p in unique if "IEEE" in p["source"]),
            "openreview": sum(1 for p in unique if "OpenReview" in p["source"]),
        },
        "needs_download_count": sum(1 for p in deep_read + quick_read if p.get("needs_download")),
        "deep_read": deep_read,
        "quick_read": quick_read
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"完成: 精读{len(deep_read)}篇, 粗读{len(quick_read)}篇")
    print(f"来源统计: {result['sources']}")
    print(f"→ {args.out}")

if __name__ == "__main__":
    main()
