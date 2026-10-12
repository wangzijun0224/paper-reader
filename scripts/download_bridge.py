# -*- coding: utf-8 -*-
"""下载桥接脚本：tmp_papers.json -> arXiv 直下 / Unpaywall OA / instsci 待下载清单。

用法:
    python download_bridge.py --input tmp_papers.json --out-dir OUT_DIR
        [--limit N] [--write-doi-list] [--instsci] [--instsci-exec]
        [--config PATH] [--instsci-exe PATH]

分类逻辑:
    a. 有 arxiv_id   -> https://arxiv.org/pdf/{arxiv_id} 直接下载 PDF
    b. 无 arxiv_id 但有 doi -> Unpaywall 查 best_oa_location.url_for_pdf, 命中则下载,
       否则记入待 instsci 清单 (status=oa-miss)
    c. 两者都没有     -> 记入待 instsci 清单 (status=pending-instsci, 用 url/标题记录)

最后总是写 {out-dir}/manifest.json:
    {doi或arxiv_id: {"pdf": 相对路径或null, "status": ok|oa-miss|pending-instsci|failed, "title": ...}}
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Windows 控制台默认 GBK, 中文输出需强制 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "user-config.json"
DEFAULT_INSTSCI_EXE = Path(r"E:/自动文献/instsci-main/.venv/Scripts/instsci.exe")

REQUEST_TIMEOUT = 60
REQUEST_INTERVAL = 0.5

# 与 instsci publisher_profiles.py 的 DOI 前缀 -> profile key 对应(常用子集)
DOI_PREFIX_TO_PROFILE = {
    "10.1021": "acs",
    "10.1016": "elsevier",
    "10.1002": "wiley",
    "10.1111": "wiley",
    "10.1007": "springer",
    "10.1038": "springer",
    "10.1109": "ieee",
    "10.1088": "iop",
    "10.1039": "rsc",
    "10.1063": "aip",
    "10.1103": "aps",
    "10.1145": "acm",
    "10.5555": "acm",
    "10.1146": "annual-reviews",
    "10.3389": "frontiers",
    "10.1142": "world-scientific",
    "10.1371": "plos",
    "10.1073": "pnas",
    "10.1126": "science",
    "10.1093": "oxfordacademic",
    "10.1098": "royalsocietypublishing",
    "10.3390": "mdpi",
    "10.5194": "copernicus",
    "10.1090": "ams",
}

_ILLEGAL_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")


def sanitize_title(title: str, max_len: int = 60) -> str:
    """去掉文件名非法字符, 空白折叠为下划线, 截断 max_len 字符。"""
    name = _ILLEGAL_FILENAME.sub("", title or "untitled")
    name = _WS.sub("_", name).strip("._ ")
    return (name[:max_len].rstrip("._ ") or "untitled")


def load_mailto(config_path: Path) -> str:
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        mailto = cfg.get("journal_sources", {}).get("crossref_mailto", "").strip()
        if mailto:
            return mailto
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] 无法读取 config ({exc}), 使用占位 mailto", file=sys.stderr)
    print("[warn] config 中没有 journal_sources.crossref_mailto, 使用占位 mailto", file=sys.stderr)
    return "boiler-research@example.com"


def http_get(url: str, mailto: str, binary: bool = False):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"boiler-research-download-bridge/1.0 (mailto:{mailto})",
            "Accept": "application/pdf,application/json,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = resp.read()
    return data if binary else data.decode("utf-8", errors="replace")


def download_pdf(url: str, dest: Path, mailto: str) -> bool:
    """下载并校验 PDF 头。已存在同名文件则跳过(视为成功)。失败返回 False。"""
    if dest.exists():
        print(f"  [skip] 已存在: {dest.name}")
        return True
    try:
        data = http_get(url, mailto, binary=True)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"  [fail] 下载失败 {url}: {exc}")
        return False
    if not data.startswith(b"%PDF"):
        print(f"  [fail] 非 PDF 内容 ({len(data)} bytes): {url}")
        return False
    dest.write_bytes(data)
    print(f"  [ok] {dest.name} ({len(data)} bytes)")
    return True


def query_unpaywall_pdf_url(doi: str, mailto: str) -> str | None:
    """返回 best_oa_location.url_for_pdf; 查询失败或无 OA 返回 None。"""
    api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(mailto)}"
    try:
        payload = json.loads(http_get(api, mailto))
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  [fail] Unpaywall 查询失败 {doi}: {exc}")
        return None
    location = payload.get("best_oa_location") or {}
    return location.get("url_for_pdf")


def profile_for_doi(doi: str) -> str | None:
    prefix = doi.strip().lower().partition("/")[0]
    return DOI_PREFIX_TO_PROFILE.get(prefix)


def build_instsci_commands(pending_dois: list[str], out_dir: Path, instsci_exe: Path) -> list[list[str]]:
    """按 publisher profile 分组, 每组写一个 DOI 文件并生成一条 instsci papers 命令。"""
    if not pending_dois:
        return []
    instsci_dir = out_dir / "instsci"
    instsci_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[str]] = {}
    for doi in pending_dois:
        groups.setdefault(profile_for_doi(doi) or "unknown", []).append(doi)

    commands = []
    for key, dois in sorted(groups.items()):
        doi_file = instsci_dir / f"dois_{key}.txt"
        doi_file.write_text("\n".join(dois) + "\n", encoding="utf-8")
        run_out = instsci_dir / key
        if key == "unknown":
            # instsci 无法对未知前缀离线推断 publisher, 需要先 queue 拆分
            commands.append([str(instsci_exe), "queue", str(doi_file), "--output", str(run_out)])
        else:
            commands.append([
                str(instsci_exe), "papers", str(doi_file),
                "--publisher", key,
                "--output", str(run_out),
            ])
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description="arXiv/Unpaywall 下载 + instsci 付费墙清单桥接")
    parser.add_argument("--input", required=True, help="tmp_papers.json 路径")
    parser.add_argument("--out-dir", required=True, help="下载输出目录")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 条 (0=全部)")
    parser.add_argument("--write-doi-list", action="store_true", help="把待 instsci 的 DOI 写到 {out-dir}/pending_dois.txt")
    parser.add_argument("--instsci", action="store_true", help="拼好并打印 instsci 批量下载命令(默认不执行)")
    parser.add_argument("--instsci-exec", action="store_true", help="真正执行 instsci 命令(需配合 --instsci, 浏览器登录需用户在场)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="user-config.json 路径")
    parser.add_argument("--instsci-exe", default=str(DEFAULT_INSTSCI_EXE), help="instsci 可执行文件路径")
    args = parser.parse_args()

    if args.instsci_exec and not args.instsci:
        parser.error("--instsci-exec 需要配合 --instsci")

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mailto = load_mailto(Path(args.config))

    data = json.loads(input_path.read_text(encoding="utf-8"))
    papers = list(data.get("deep_read", [])) + list(data.get("quick_read", []))
    if args.limit > 0:
        papers = papers[: args.limit]
    print(f"共 {len(papers)} 条待处理, 输出目录: {out_dir}")

    manifest: dict[str, dict] = {}
    pending_dois: list[str] = []
    pending_other: list[dict] = []

    for i, paper in enumerate(papers, 1):
        title = (paper.get("title") or "").strip()
        arxiv_id = (paper.get("arxiv_id") or "").strip()
        doi = (paper.get("doi") or "").strip()
        key = doi or arxiv_id or paper.get("url") or title or f"row-{i}"
        entry = {"pdf": None, "status": "failed", "title": title}
        print(f"\n[{i}/{len(papers)}] {title[:70]}")

        if i > 1:
            time.sleep(REQUEST_INTERVAL)

        if arxiv_id:
            url = f"https://arxiv.org/pdf/{arxiv_id}"
            dest = out_dir / f"{sanitize_title(title)}_{arxiv_id.replace('/', '_')}.pdf"
            if download_pdf(url, dest, mailto):
                entry["pdf"] = dest.name
                entry["status"] = "ok"
            else:
                entry["status"] = "failed"
        elif doi:
            pdf_url = query_unpaywall_pdf_url(doi, mailto)
            if pdf_url:
                dest = out_dir / f"{sanitize_title(title)}_{doi.replace('/', '_')}.pdf"
                if download_pdf(pdf_url, dest, mailto):
                    entry["pdf"] = dest.name
                    entry["status"] = "ok"
                else:
                    entry["status"] = "failed"
            else:
                entry["status"] = "oa-miss"
                pending_dois.append(doi)
                print(f"  [oa-miss] 无 OA PDF, 转入 instsci 清单: {doi}")
        else:
            entry["status"] = "pending-instsci"
            pending_other.append({"title": title, "url": paper.get("url", "")})
            print("  [pending] 无 arxiv_id/doi, 记入待处理清单")

        manifest[key] = entry

    if args.write_doi_list:
        doi_list_path = out_dir / "pending_dois.txt"
        doi_list_path.write_text("\n".join(pending_dois) + ("\n" if pending_dois else ""), encoding="utf-8")
        print(f"\n待 instsci DOI 清单 ({len(pending_dois)} 条): {doi_list_path}")
        if pending_other:
            other_path = out_dir / "pending_no_doi.json"
            other_path.write_text(json.dumps(pending_other, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"无 DOI 待处理 ({len(pending_other)} 条): {other_path}")

    if args.instsci:
        if not Path(args.instsci_exe).exists():
            print(f"[warn] instsci 不存在: {args.instsci_exe}", file=sys.stderr)
        commands = build_instsci_commands(pending_dois, out_dir, Path(args.instsci_exe))
        print("\ninstsci 批量下载命令 (可见浏览器, 需手动完成机构登录):")
        for cmd in commands:
            print("  " + subprocess.list2cmdline(cmd))
        if args.instsci_exec:
            for cmd in commands:
                print(f"\n[exec] {subprocess.list2cmdline(cmd)}")
                subprocess.run(cmd, check=False)
        else:
            print("\n(默认不执行; 加 --instsci-exec 才会真正调用, 浏览器登录需用户在场)")

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for entry in manifest.values():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print(f"\n完成: {counts}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
