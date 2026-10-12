#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zotero 导入模块
把检索脚本输出的 tmp_papers.json（deep_read + quick_read）导入 Zotero 指定 collection，
有 PDF 的挂为附件。

用法:
  python zotero_import.py --input tmp_papers.json [--pdf-manifest manifest.json] \
      --collection 每日阅读 [--dry-run]

写入路径（两级策略，自动选择）:
  1. Zotero web API（首选）：config/user-config.json 的 zotero.user_id / zotero.api_key
     均非空时走此路径（需要 pyzotero）。
  2. 直连 sqlite（fallback）：要求 Zotero 桌面版未运行，否则报锁退出。

去重: 按 DOI（小写）和 arxiv_id 跳过库中已有条目。
标记: extra 字段与 tags 中写入 `auto-import {date}` 和 read_depth。
"""
import argparse
import datetime
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import string
import sys
import tempfile
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "user-config.json"
DEFAULT_DB = "D:/zetero/zotero.sqlite"
DEFAULT_STORAGE = "D:/zetero/storage"

ARXIV_ABS_RE = re.compile(r"arxiv\.org/abs/([^/\s?#]+)", re.I)
ARXIV_PREFIX_RE = re.compile(r"arXiv:\s*([0-9]{4}\.[0-9]{4,5}(v\d+)?|[a-z\-]+/\d{7}(v\d+)?)", re.I)


# ── 通用工具 ──────────────────────────────────────────────────
def normalize_doi(doi):
    if not doi:
        return ""
    doi = str(doi).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip()


def normalize_arxiv_id(value):
    if not value:
        return ""
    v = str(value).strip()
    m = ARXIV_ABS_RE.search(v)
    if m:
        v = m.group(1)
    if v.lower().startswith("arxiv:"):
        v = v.split(":", 1)[1].strip()
    return v.lower()


def arxiv_variants(arxiv_id):
    """返回带/不带版本号的两种形式，用于宽松匹配"""
    aid = normalize_arxiv_id(arxiv_id)
    if not aid:
        return set()
    base = re.sub(r"v\d+$", "", aid)
    return {aid, base}


def make_key(length=8):
    """Zotero 风格的 8 位随机 key（大写字母+数字）"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.SystemRandom().choice(alphabet) for _ in range(length))


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def split_author(name):
    """'Zhang San' -> (firstName='Zhang', lastName='San')；单名 -> fieldMode=1"""
    name = str(name).strip()
    if not name:
        return None
    if "," in name:  # "Last, First" 形式
        last, _, first = name.partition(",")
        return {"firstName": first.strip(), "lastName": last.strip(), "fieldMode": 0}
    parts = name.split()
    if len(parts) == 1:
        return {"firstName": "", "lastName": parts[0], "fieldMode": 1}
    return {"firstName": " ".join(parts[:-1]), "lastName": parts[-1], "fieldMode": 0}


# ── 输入解析 ──────────────────────────────────────────────────
def load_papers(input_path):
    """读取 tmp_papers.json，合并 deep_read + quick_read"""
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        papers = data
    else:
        papers = list(data.get("deep_read", [])) + list(data.get("quick_read", []))
    out = []
    for p in papers:
        authors = p.get("authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";") if a.strip()]
        creators = []
        for a in authors:
            if isinstance(a, dict):
                fn = a.get("firstName") or a.get("first") or ""
                ln = a.get("lastName") or a.get("last") or a.get("name") or ""
                creators.append({"firstName": fn, "lastName": ln,
                                 "fieldMode": 0 if fn else 1})
            else:
                ca = split_author(a)
                if ca:
                    creators.append(ca)
        out.append({
            "title": (p.get("title") or "").strip(),
            "abstract": p.get("abstract") or "",
            "doi": normalize_doi(p.get("doi")),
            "arxiv_id": normalize_arxiv_id(p.get("arxiv_id")),
            "url": p.get("url") or "",
            "date": p.get("date") or (str(p.get("year")) if p.get("year") else ""),
            "source": p.get("source") or "",
            "read_depth": p.get("read_depth") or "",
            "creators": creators,
        })
    return [p for p in out if p["title"]]


def load_pdf_manifest(path):
    """{doi或arxiv_id: pdf路径 或 download_bridge 的 {pdf,status,title} 字典}，
    容忍 key 大小写 / None；相对路径按 manifest 所在目录解析"""
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    manifest = {}
    for k, v in raw.items():
        if not k or not v:
            continue
        if isinstance(v, dict):
            if v.get("status") != "ok" or not v.get("pdf"):
                continue
            v = v["pdf"]
        v = str(v)
        if not os.path.isabs(v):
            v = os.path.normpath(os.path.join(base, v))
        doi = normalize_doi(k)
        aid = normalize_arxiv_id(k)
        if doi:
            manifest.setdefault(doi, v)
        if aid:
            manifest.setdefault(aid, v)
            manifest.setdefault(re.sub(r"v\d+$", "", aid), v)
    return manifest


def find_pdf(paper, manifest):
    if not manifest:
        return None
    path = None
    if paper["doi"]:
        path = manifest.get(normalize_doi(paper["doi"]))
    if not path and paper["arxiv_id"]:
        for v in arxiv_variants(paper["arxiv_id"]):
            if v in manifest:
                path = manifest[v]
                break
    if path and os.path.exists(path):
        return path
    return None


# ── 去重（只读查询）──────────────────────────────────────────
def collect_identifiers_from_rows(rows):
    """rows: (fieldName, value) 迭代，抽取 doi 集合与 arxiv 集合"""
    dois, arxivs = set(), set()
    for field, value in rows:
        if not value:
            continue
        if field == "DOI":
            d = normalize_doi(value)
            if d:
                dois.add(d)
        elif field == "url":
            m = ARXIV_ABS_RE.search(value)
            if m:
                arxivs.update(arxiv_variants(m.group(1)))
        elif field == "extra":
            for m in ARXIV_PREFIX_RE.finditer(value):
                arxivs.update(arxiv_variants(m.group(1)))
    return dois, arxivs


def existing_identifiers_sqlite(db_path):
    """从 sqlite（只读）取已有 DOI / arxiv_id 集合"""
    conn = open_readonly(db_path)
    try:
        rows = conn.execute("""
            SELECT f.fieldName, v.value
            FROM itemData d
            JOIN fields f ON d.fieldID = f.fieldID
            JOIN itemDataValues v ON d.valueID = v.valueID
            WHERE f.fieldName IN ('DOI', 'url', 'extra')
        """)
        return collect_identifiers_from_rows(rows)
    finally:
        conn.close()


def existing_identifiers_api(zot):
    """从 web API 取已有 DOI / arxiv_id 集合（分页遍历顶层条目）"""
    rows = []
    start, limit = 0, 100
    while True:
        batch = zot.items(limit=limit, start=start, itemType="-attachment || note")
        if not batch:
            break
        for it in batch:
            d = it.get("data", {})
            for field in ("DOI", "url", "extra"):
                if d.get(field):
                    rows.append((field, d[field]))
        if len(batch) < limit:
            break
        start += limit
    return collect_identifiers_from_rows(rows)


def filter_new(papers, dois, arxivs):
    """按 DOI（小写）/ arxiv_id 去重，返回 (待导入, 跳过) 两组"""
    to_import, skipped = [], []
    seen_dois, seen_arxivs = set(dois), set(arxivs)
    for p in papers:
        dup = False
        if p["doi"] and p["doi"] in seen_dois:
            dup = True
        if not dup and p["arxiv_id"]:
            if arxiv_variants(p["arxiv_id"]) & seen_arxivs:
                dup = True
        if dup:
            skipped.append(p)
        else:
            to_import.append(p)
            if p["doi"]:
                seen_dois.add(p["doi"])
            seen_arxivs.update(arxiv_variants(p["arxiv_id"]))
    return to_import, skipped


def open_readonly(db_path):
    """只读连接。Zotero 运行导致直接只读失败时，复制 db(+wal/shm) 到临时目录再读。"""
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("SELECT COUNT(*) FROM items").fetchone()
        return conn
    except sqlite3.OperationalError:
        tmpdir = tempfile.mkdtemp(prefix="zotero_ro_")
        copy = os.path.join(tmpdir, "zotero.sqlite")
        shutil.copy2(db_path, copy)
        for suffix in ("-wal", "-shm"):
            src = db_path + suffix
            if os.path.exists(src):
                shutil.copy2(src, copy + suffix)
        return sqlite3.connect(f"file:{copy}?mode=ro", uri=True)


# ── 条目构造（两种路径共用）──────────────────────────────────
def build_extra(paper):
    lines = [f"auto-import: {today_str()}"]
    if paper["read_depth"]:
        lines.append(f"read_depth: {paper['read_depth']}")
    if paper["source"]:
        lines.append(f"source: {paper['source']}")
    if paper["arxiv_id"]:
        lines.append(f"arXiv: {paper['arxiv_id']}")
    return "\n".join(lines)


def build_tags(paper):
    tags = [f"auto-import {today_str()}"]
    if paper["read_depth"]:
        tags.append(f"read_depth:{paper['read_depth']}")
    return tags


def item_type_of(paper):
    if paper["doi"]:
        return "journalArticle"
    if paper["arxiv_id"]:
        return "preprint"
    return "report"


# ── 路径 1: Zotero web API ───────────────────────────────────
def get_zotero_api(config):
    zcfg = (config or {}).get("zotero", {})
    user_id = (zcfg.get("user_id") or "").strip()
    api_key = (zcfg.get("api_key") or "").strip()
    if not (user_id and api_key):
        return None
    try:
        from pyzotero import zotero
    except ImportError:
        print("[错误] 未安装 pyzotero，请先: pip install pyzotero", file=sys.stderr)
        sys.exit(2)
    return zotero.Zotero(user_id, "user", api_key)


def find_collection_key_api(zot, name):
    for col in zot.collections():
        if col["data"]["name"] == name:
            return col["key"]
    return None


def import_via_api(zot, collection_key, papers, manifest, dry_run=False):
    if dry_run:
        return len(papers), 0
    items = []
    for p in papers:
        tpl = {
            "itemType": item_type_of(p),
            "title": p["title"],
            "creators": [{"creatorType": "author",
                          "firstName": c["firstName"],
                          "lastName": c["lastName"]} for c in p["creators"]],
            "abstractNote": p["abstract"],
            "date": p["date"],
            "extra": build_extra(p),
            "url": p["url"],
            "tags": [{"tag": t} for t in build_tags(p)],
            "collections": [collection_key],
        }
        if p["doi"]:
            tpl["DOI"] = p["doi"]
        if p["arxiv_id"]:
            tpl["repository"] = "arXiv"
            tpl["archiveID"] = f"arXiv:{p['arxiv_id']}"
        items.append(tpl)
    created = 0
    created_keys = []
    # web API 单次 create_items 上限 50
    for i in range(0, len(items), 50):
        resp = zot.create_items(items[i:i + 50])
        for _, entry in (resp.get("successful") or {}).items():
            created += 1
            created_keys.append(entry["key"])
        for idx, entry in (resp.get("failed") or {}).items():
            print(f"[警告] 创建失败: {items[i + int(idx)]['title'][:60]} -> {entry}")
    # 上传 PDF 附件（按创建顺序对应）
    attached = 0
    for p, key in zip(papers, created_keys):
        pdf = find_pdf(p, manifest)
        if not pdf:
            continue
        try:
            zot.attachment_simple([pdf], key)
            attached += 1
        except Exception as e:
            print(f"[警告] 附件上传失败 {p['title'][:50]}: {e}")
    return created, attached


# ── 路径 2: 直连 sqlite ──────────────────────────────────────
def get_ids(conn, table, name_col, id_col):
    return {r[0]: r[1] for r in conn.execute(f"SELECT {name_col}, {id_col} FROM {table}")}


def get_or_create_value(conn, value):
    row = conn.execute("SELECT valueID FROM itemDataValues WHERE value = ?", (value,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO itemDataValues (value) VALUES (?)", (value,))
    return cur.lastrowid


def get_or_create_creator(conn, c):
    row = conn.execute(
        "SELECT creatorID FROM creators WHERE firstName=? AND lastName=? AND fieldMode=?",
        (c["firstName"], c["lastName"], c["fieldMode"])).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO creators (firstName, lastName, fieldMode) VALUES (?,?,?)",
        (c["firstName"], c["lastName"], c["fieldMode"]))
    return cur.lastrowid


def get_or_create_tag(conn, name):
    row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid


def unique_key(conn):
    while True:
        k = make_key()
        if not conn.execute("SELECT 1 FROM items WHERE key=?", (k,)).fetchone():
            return k


def insert_item_row(conn, item_type_id, key, library_id=1):
    cur = conn.execute("""
        INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified,
                           libraryID, key, version, synced)
        VALUES (?,?,?,?,?,?,0,0)
    """, (item_type_id, now_str(), now_str(), now_str(), library_id, key))
    return cur.lastrowid


def _attach_pdf(conn, type_ids, storage_dir, item_id, pdf):
    """把本地 PDF 复制进 storage 并挂为 item 的 imported-file 附件"""
    att_key = unique_key(conn)
    dest_dir = os.path.join(storage_dir, att_key)
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(pdf)
    dest = os.path.join(dest_dir, filename)
    shutil.copy2(pdf, dest)
    with open(dest, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    mtime_ms = int(os.path.getmtime(dest) * 1000)  # Zotero 用毫秒
    att_id = insert_item_row(conn, type_ids["attachment"], att_key)
    conn.execute("""
        INSERT INTO itemAttachments
            (itemID, parentItemID, linkMode, contentType, path,
             syncState, storageModTime, storageHash)
        VALUES (?,?,?,?,?,0,?,?)
    """, (att_id, item_id, 0, "application/pdf",
          f"storage:{filename}", mtime_ms, md5))


def _item_has_pdf(conn, item_id):
    return conn.execute(
        "SELECT 1 FROM itemAttachments WHERE parentItemID=? AND contentType='application/pdf' LIMIT 1",
        (item_id,)).fetchone() is not None


def import_via_sqlite(db_path, storage_dir, collection_name, papers, manifest,
                      dry_run=False, skipped_papers=None):
    # 集合 ID（只读连接查询）
    ro = open_readonly(db_path)
    try:
        row = ro.execute(
            "SELECT collectionID FROM collections WHERE collectionName = ?",
            (collection_name,)).fetchone()
    finally:
        ro.close()
    if not row:
        print(f"[错误] 未找到 collection: {collection_name}", file=sys.stderr)
        sys.exit(1)
    collection_id = row[0]

    if dry_run:
        n_attach = sum(1 for p in papers if find_pdf(p, manifest))
        n_attach_existing = sum(1 for p in (skipped_papers or []) if find_pdf(p, manifest))
        return len(papers), n_attach, n_attach_existing

    # 写库前检测锁：读写打开 + BEGIN IMMEDIATE，锁则明确报错退出
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as e:
        conn.close()
        if "locked" in str(e).lower():
            print("[错误] 数据库被锁定（Zotero 正在运行？）。\n"
                  "       请关闭 Zotero 桌面版后重试，或在 config 中配置 "
                  "zotero.user_id / zotero.api_key 使用 web API 路径。",
                  file=sys.stderr)
            sys.exit(3)
        raise

    type_ids = get_ids(conn, "itemTypes", "typeName", "itemTypeID")
    field_ids = get_ids(conn, "fields", "fieldName", "fieldID")
    author_type_id = conn.execute(
        "SELECT creatorTypeID FROM creatorTypes WHERE creatorType='author'").fetchone()[0]

    created = attached = attached_existing = 0
    try:
        for p in papers:
            item_id = insert_item_row(conn, type_ids[item_type_of(p)], unique_key(conn))
            field_values = {
                "title": p["title"],
                "abstractNote": p["abstract"],
                "date": p["date"],
                "url": p["url"],
                "extra": build_extra(p),
            }
            if p["doi"]:
                field_values["DOI"] = p["doi"]
            if item_type_of(p) == "preprint":
                field_values["repository"] = "arXiv"
                field_values["archiveID"] = f"arXiv:{p['arxiv_id']}"
            for fname, value in field_values.items():
                if not value or fname not in field_ids:
                    continue
                conn.execute(
                    "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?,?,?)",
                    (item_id, field_ids[fname], get_or_create_value(conn, value)))
            for idx, c in enumerate(p["creators"]):
                cid = get_or_create_creator(conn, c)
                conn.execute("""
                    INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex)
                    VALUES (?,?,?,?)
                """, (item_id, cid, author_type_id, idx))
            for t in build_tags(p):
                conn.execute(
                    "INSERT INTO itemTags (itemID, tagID, type) VALUES (?,?,0)",
                    (item_id, get_or_create_tag(conn, t)))
            conn.execute(
                "INSERT INTO collectionItems (collectionID, itemID, orderIndex) VALUES (?,?,0)",
                (collection_id, item_id))

            pdf = find_pdf(p, manifest)
            if pdf:
                _attach_pdf(conn, type_ids, storage_dir, item_id, pdf)
                attached += 1
            created += 1

        # 补挂：库里已存在的条目（本次被去重跳过），若还没有 PDF 附件则补上
        for p in skipped_papers or []:
            if not p.get("doi"):
                continue
            pdf = find_pdf(p, manifest)
            if not pdf:
                continue
            row = conn.execute("""
                SELECT itemData.itemID FROM itemData
                JOIN itemDataValues v ON itemData.valueID = v.valueID
                WHERE itemData.fieldID = ? AND LOWER(v.value) = ?
            """, (field_ids["DOI"], normalize_doi(p["doi"]))).fetchone()
            if not row:
                continue
            item_id = row[0]
            if _item_has_pdf(conn, item_id):
                continue
            _attach_pdf(conn, type_ids, storage_dir, item_id, pdf)
            attached_existing += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return created, attached, attached_existing


# ── 主流程 ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="把 tmp_papers.json 导入 Zotero collection")
    parser.add_argument("--input", required=True, help="tmp_papers.json 路径")
    parser.add_argument("--pdf-manifest", help="可选，{doi或arxiv_id: pdf路径} 的 JSON")
    parser.add_argument("--collection", default="每日阅读", help="目标 collection 名")
    parser.add_argument("--dry-run", action="store_true", help="只打印摘要，不写库")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="user-config.json 路径")
    parser.add_argument("--db", default=DEFAULT_DB, help="zotero.sqlite 路径")
    parser.add_argument("--storage", default=DEFAULT_STORAGE, help="Zotero storage 目录")
    args = parser.parse_args()

    config = {}
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as f:
            config = json.load(f)

    papers = load_papers(args.input)
    manifest = load_pdf_manifest(args.pdf_manifest)
    print(f"输入: {len(papers)} 篇（deep_read + quick_read 合并）")

    # 选择写入路径
    zot = get_zotero_api(config)
    mode = "web-api" if zot else "sqlite"
    print(f"写入路径: {mode}" + ("（dry-run，不写库）" if args.dry_run else ""))

    # 去重
    if zot:
        dois, arxivs = existing_identifiers_api(zot)
    else:
        dois, arxivs = existing_identifiers_sqlite(args.db)
    print(f"库中已有标识: DOI {len(dois)} 个, arXiv {len(arxivs)} 个")
    to_import, skipped = filter_new(papers, dois, arxivs)
    print(f"去重结果: 待导入 {len(to_import)} 篇, 跳过（库中已存在）{len(skipped)} 篇")

    for p in to_import:
        pdf = find_pdf(p, manifest)
        idpart = f"doi:{p['doi']}" if p["doi"] else (f"arxiv:{p['arxiv_id']}" if p["arxiv_id"] else "无标识")
        print(f"  + [{p['read_depth'] or '-'}] {p['title'][:70]} | {idpart}"
              + (" | +PDF" if pdf else ""))

    if not to_import and not skipped:
        print("没有需要导入的条目。")
        return
    if not to_import:
        print("本次无新条目，仅检查已存在条目的 PDF 补挂。")

    if zot:
        collection_key = find_collection_key_api(zot, args.collection)
        if not collection_key:
            print(f"[错误] 未找到 collection: {args.collection}", file=sys.stderr)
            sys.exit(1)
        created, attached = import_via_api(zot, collection_key, to_import,
                                           manifest, dry_run=args.dry_run)
        attached_existing = 0
    else:
        created, attached, attached_existing = import_via_sqlite(
            args.db, args.storage, args.collection,
            to_import, manifest, dry_run=args.dry_run, skipped_papers=skipped)

    verb = "将导入" if args.dry_run else "已导入"
    msg = f"{verb} {created} 篇条目"
    if not args.dry_run:
        msg += f"，其中 {attached} 个 PDF 附件"
    if attached_existing:
        msg += f"；为库中已存在条目补挂 {attached_existing} 个 PDF"
    print(msg)


if __name__ == "__main__":
    main()
