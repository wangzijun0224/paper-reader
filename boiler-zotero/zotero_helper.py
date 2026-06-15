#!/usr/bin/env python3
"""
Zotero数据库辅助脚本
用法:
  python zotero_helper.py list-collection --name "CFD" --db "D:/zetero/zotero.sqlite"
  python zotero_helper.py info --key ABCD1234 --db "D:/zetero/zotero.sqlite"
  python zotero_helper.py list-all --db "D:/zetero/zotero.sqlite"
"""
import argparse, json, sqlite3, os
from pathlib import Path

DEFAULT_DB = "D:/zetero/zotero.sqlite"
DEFAULT_STORAGE = "D:/zetero/storage"

def get_connection(db_path):
    """只读连接Zotero SQLite"""
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)

def list_collections(db_path):
    """列出所有collection"""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT collectionID, collectionName, parentCollectionID
        FROM collections ORDER BY collectionName
    """).fetchall()
    conn.close()
    result = []
    for cid, name, parent in rows:
        result.append({"id": cid, "name": name, "parent_id": parent})
    return result

def list_collection_items(db_path, collection_name):
    """列出指定collection下的所有文献"""
    conn = get_connection(db_path)
    # 查找collection ID
    row = conn.execute(
        "SELECT collectionID FROM collections WHERE collectionName = ?", (collection_name,)
    ).fetchone()
    if not row:
        # 模糊匹配
        rows = conn.execute(
            "SELECT collectionID, collectionName FROM collections WHERE collectionName LIKE ?",
            (f"%{collection_name}%",)
        ).fetchall()
        if not rows:
            print(f"未找到collection: {collection_name}")
            conn.close()
            return []
        cid, matched_name = rows[0]
        print(f"模糊匹配到: {matched_name}")
    else:
        cid = row[0]

    # 查询文献
    items = conn.execute("""
        SELECT i.itemID, i.key,
               MAX(CASE WHEN f.fieldName='title' THEN iv.value END) as title,
               MAX(CASE WHEN f.fieldName='DOI' THEN iv.value END) as doi,
               MAX(CASE WHEN f.fieldName='abstractNote' THEN iv.value END) as abstract,
               MAX(CASE WHEN f.fieldName='date' THEN iv.value END) as date
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        LEFT JOIN itemData id ON i.itemID = id.itemID
        LEFT JOIN fields f ON id.fieldID = f.fieldID
        LEFT JOIN itemDataValues iv ON id.valueID = iv.valueID
        WHERE ci.collectionID = ?
        GROUP BY i.itemID
    """, (cid,)).fetchall()

    result = []
    for item_id, key, title, doi, abstract, date in items:
        if not title:
            continue
        # 查找PDF附件
        attachments = conn.execute("""
            SELECT ia.path FROM itemAttachments ia
            JOIN items i ON ia.itemID = i.itemID
            WHERE ia.parentItemID = ? AND ia.contentType = 'application/pdf'
        """, (item_id,)).fetchall()
        pdf_paths = []
        for (att_path,) in attachments:
            if att_path:
                clean = att_path.replace("storage:", "")
                pdf_paths.append(clean)
        result.append({
            "item_key": key,
            "title": title or "",
            "doi": doi or "",
            "abstract": abstract or "",
            "date": date or "",
            "pdf_keys": pdf_paths
        })

    conn.close()
    return result

def get_item_info(db_path, storage_path, item_key):
    """获取单篇论文详情+PDF路径"""
    conn = get_connection(db_path)
    item = conn.execute("""
        SELECT i.itemID FROM items i WHERE i.key = ?
    """, (item_key,)).fetchone()
    if not item:
        conn.close()
        return None
    item_id = item[0]

    fields = conn.execute("""
        SELECT f.fieldName, iv.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues iv ON id.valueID = iv.valueID
        WHERE id.itemID = ?
    """, (item_id,)).fetchall()
    meta = {f: v for f, v in fields}

    # 找PDF
    attachments = conn.execute("""
        SELECT i.key, ia.path FROM itemAttachments ia
        JOIN items i ON ia.itemID = i.itemID
        WHERE ia.parentItemID = ? AND ia.contentType = 'application/pdf'
    """, (item_id,)).fetchall()

    pdf_paths = []
    for att_key, att_path in attachments:
        if att_path:
            subdir = att_path.replace("storage:", "").split("/")[0] if "/" in att_path else att_key
            filename = att_path.split("/")[-1] if "/" in att_path else att_path.replace("storage:", "")
            full_path = os.path.join(storage_path, subdir, filename)
            if os.path.exists(full_path):
                pdf_paths.append(full_path)

    # 找全文缓存
    cache_paths = []
    for att_key, _ in attachments:
        cache = os.path.join(storage_path, att_key, ".zotero-ft-cache")
        if os.path.exists(cache):
            cache_paths.append(cache)

    # 找Zotero批注
    highlights = conn.execute("""
        SELECT ian.text, ian.comment FROM itemAnnotations ian
        WHERE ian.parentItemID IN (
            SELECT itemID FROM items WHERE key IN ({})
        )
    """.format(",".join("?" * len([a[0] for a in attachments])),),
        [a[0] for a in attachments] if attachments else [""]
    ).fetchall() if attachments else []

    conn.close()
    return {
        "item_key": item_key,
        "title": meta.get("title", ""),
        "doi": meta.get("DOI", ""),
        "abstract": meta.get("abstractNote", ""),
        "date": meta.get("date", ""),
        "pdf_paths": pdf_paths,
        "cache_paths": cache_paths,
        "highlights": [{"text": h[0], "comment": h[1]} for h in highlights if h[0]]
    }

def find_item_by_title(db_path, storage_path, title_query):
    """按标题模糊搜索单篇论文，返回最佳匹配的详情"""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT i.key FROM items i
        JOIN itemData id ON i.itemID = id.itemID
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues iv ON id.valueID = iv.valueID
        WHERE f.fieldName = 'title' AND iv.value LIKE ?
        LIMIT 5
    """, (f"%{title_query}%",)).fetchall()
    conn.close()
    if not rows:
        return None
    if len(rows) > 1:
        print(f"[zotero] 找到{len(rows)}个匹配，使用第一个: {rows[0][0]}")
    return get_item_info(db_path, storage_path, rows[0][0])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list-collection", "list-all", "info"])
    parser.add_argument("--name", type=str, help="collection名称")
    parser.add_argument("--key", type=str, help="item key")
    parser.add_argument("--title", type=str, help="按标题模糊搜索")
    parser.add_argument("--db", type=str, default=DEFAULT_DB)
    parser.add_argument("--storage", type=str, default=DEFAULT_STORAGE)
    args = parser.parse_args()

    if args.command == "list-all":
        cols = list_collections(args.db)
        print(json.dumps(cols, ensure_ascii=False, indent=2))
    elif args.command == "list-collection":
        items = list_collection_items(args.db, args.name or "")
        print(json.dumps(items, ensure_ascii=False, indent=2))
    elif args.command == "info":
        if args.title:
            info = find_item_by_title(args.db, args.storage, args.title)
        else:
            info = get_item_info(args.db, args.storage, args.key or "")
        print(json.dumps(info, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
