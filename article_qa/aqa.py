#!/usr/bin/env python3
"""文章問答 bot 的讀文工具（在 Mac 本機執行）。

把文章轉成乾淨、分段的文字快取，讓模型只讀需要的部分，並把介紹與問答寫進 Obsidian。

子指令：
  resolve <早報編號>            找出早報裡的文章，例如「工具 2」「⑤」「11/26 研究 1」
  fetch <編號|連結|檔案路徑>     抓原文、轉文字、去參考文獻、擷取圖片，印出目錄與正文
  section <快取ID> <章節>       印出某一節（章節編號或關鍵字）
  search <快取ID> <關鍵字...>   找出最相關的段落
  figure <快取ID> <圖號>        印出某張圖的檔案路徑（給模型看圖用）
  note create <快取ID>          從 stdin 讀介紹，建立 Obsidian 筆記
  note qa <快取ID> -q 問題       從 stdin 讀回答，追加到筆記的問答紀錄
  list                          列出最近的快取
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

HOME = Path(os.environ.get("AQA_HOME", Path.home() / ".article-qa"))
CACHE = HOME / "cache"
DEFAULT_VAULT = "/Users/alanhsu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Notes"
NOTE_DIR = "AI 早報/文章筆記"
ATTACH_DIR = "AI 早報/文章筆記/附件"
DIGEST_URL = "https://raw.githubusercontent.com/alanhsu0531/-OpenMausBot-News-Push/main/data/{date}/digest.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
TW = dt.timezone(dt.timedelta(hours=8))

CATEGORY_ALIASES = {
    "company": ["公司", "公司動態", "新聞", "company"],
    "tools": ["工具", "新工具", "tool", "tools"],
    "research": ["研究", "技術", "新技術", "論文", "research", "paper"],
}
CATEGORY_ZH = {"company": "公司", "tools": "工具", "research": "研究"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

REF_HEAD = re.compile(r"^(\d+\.?\s*)?(references|bibliography|參考文獻|acknowledg(e)?ments?|致謝)\b", re.I)
APPX_HEAD = re.compile(r"^(appendix|appendices|supplementary|附錄|[A-Z](\.\d+)*\.?\s+\S)", re.I)
ARXIV_ID = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])")


# ---------- 共用 ----------

def config() -> dict:
    cfg = {"vault": os.environ.get("AQA_VAULT", DEFAULT_VAULT)}
    f = HOME / "config.json"
    if f.exists():
        cfg.update(json.loads(f.read_text("utf-8")))
    return cfg


def today() -> dt.date:
    return dt.datetime.now(TW).date()


def est_tokens(text: str) -> int:
    cjk = len(re.findall(r"[　-鿿＀-￯]", text))
    return cjk + (len(text) - cjk) // 4


def http_get(url: str, **kw):
    import requests
    r = requests.get(url, headers={"User-Agent": UA}, timeout=40, **kw)
    return r


def die(msg: str, code: int = 1):
    print(f"錯誤：{msg}", file=sys.stderr)
    sys.exit(code)


# ---------- 早報編號 ----------

def parse_ref(ref: str):
    """回傳 (日期, 分類或 None, 序號)；無法解析回傳 None。"""
    s = ref.strip()
    date = today()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*", s)
    if m:
        date = dt.date(int(m[1]), int(m[2]), int(m[3]))
        s = s[m.end():]
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})\s+", s)
        if m:
            date = dt.date(today().year, int(m[1]), int(m[2]))
            if date > today():
                date = date.replace(year=date.year - 1)
            s = s[m.end():]
        else:
            for word, delta in (("今天", 0), ("昨天", 1), ("前天", 2)):
                if s.startswith(word):
                    date = today() - dt.timedelta(days=delta)
                    s = s[len(word):].strip()
    s = s.strip().lstrip("#第").rstrip("則篇")
    if len(s) == 1 and s in CIRCLED:
        return date, None, CIRCLED.index(s) + 1
    if s.isdigit():
        return date, None, int(s)
    m = re.match(r"^([^\d\s]+)\s*第?\s*(\d+|[" + CIRCLED + r"])\s*[則篇]?$", s)
    if m:
        word, num = m[1].lower(), m[2]
        n = CIRCLED.index(num) + 1 if num in CIRCLED else int(num)
        for cat, words in CATEGORY_ALIASES.items():
            if word in words:
                return date, cat, n
    return None


def load_digest(date: dt.date) -> dict:
    local = Path(__file__).resolve().parent.parent / "data" / date.isoformat() / "digest.json"
    try:
        r = http_get(DIGEST_URL.format(date=date.isoformat()))
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    if local.exists():
        return json.loads(local.read_text("utf-8"))
    die(f"找不到 {date.isoformat()} 的早報。")


def resolve(ref: str) -> dict:
    parsed = parse_ref(ref)
    if not parsed:
        die(f"看不懂「{ref}」。請用「工具 2」「⑤」或「11/26 研究 1」這種格式。")
    date, cat, n = parsed
    items = load_digest(date)["items"]
    pool = [i for i in items if i["category"] == cat] if cat else items
    if not 1 <= n <= len(pool):
        label = CATEGORY_ZH.get(cat, "全部") if cat else "全部"
        die(f"{date.isoformat()} 早報的「{label}」只有 {len(pool)} 則。")
    item = dict(pool[n - 1])
    item["digest_date"] = date.isoformat()
    item["digest_no"] = items.index(pool[n - 1]) + 1
    return item


# ---------- 轉文字 ----------

def html_to_md_arxiv(html: str, base: str):
    """arXiv HTML（LaTeXML）→ (標題, 正文 md, 附錄 md, 圖片清單)。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for m in soup.find_all("math"):
        alt = m.get("alttext") or m.get_text(" ", strip=True)
        m.replace_with(f"${alt}$")
    for tag in soup.select(".ltx_bibliography, .ltx_role_footnote, nav, header, footer, .ltx_page_footer"):
        tag.decompose()
    t = soup.select_one(".ltx_title_document") or soup.find("h1")
    title = t.get_text(" ", strip=True) if t else ""
    figures, main, appx = [], [], []

    def emit(node, out, depth):
        for child in node.children:
            name = getattr(child, "name", None)
            if not name:
                continue
            cls = " ".join(child.get("class", []))
            if re.match(r"h[1-6]$", name) and "ltx_title" in cls:
                if "ltx_title_document" in cls:
                    continue
                txt = child.get_text(" ", strip=True)
                if REF_HEAD.match(re.sub(r"^[\dA-Z.]+\s*", "", txt)):
                    return "stop"
                out.append("#" * min(depth, 4) + " " + txt)
            elif name == "figure" and "ltx_table" not in cls:
                # LaTeXML 的圖說可能是 <figcaption> 或 span.ltx_caption；圖可能是 <img> 或 <object data=*.svg>
                cap = child.find("figcaption") or child.select_one(".ltx_caption")
                img = child.find("img", src=True) or child.find("object", attrs={"data": True})
                src = img and (img.get("src") or img.get("data"))
                if src:
                    figures.append({"caption": " ".join(cap.get_text(" ", strip=True).split()) if cap else "",
                                    "src": urljoin(base, src)})
                    out.append(f"[圖 {len(figures)}] {figures[-1]['caption'][:200]}")
            elif name == "figure":
                cap = child.find("figcaption") or child.select_one(".ltx_caption")
                if cap:
                    out.append(cap.get_text(" ", strip=True))
                    cap.decompose()
                if emit(child, out, depth) == "stop":
                    return "stop"
            elif name == "div" and "ltx_abstract" in cls:
                out.append("## Abstract")
                out.append(child.get_text(" ", strip=True).removeprefix("Abstract").strip())
            elif name in ("p",):
                txt = child.get_text(" ", strip=True)
                if txt:
                    out.append(txt)
            elif name == "section":
                target = appx if ("ltx_appendix" in cls or out is appx) else out
                if emit(child, target, depth + 1) == "stop":
                    if target is out:
                        return None
            elif name in ("table",):
                rows = [" | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"]))
                        for tr in child.find_all("tr")]
                if rows:
                    out.append("\n".join(rows[:30]))
            elif name in ("ul", "ol"):
                for li in child.find_all("li", recursive=False):
                    out.append("- " + li.get_text(" ", strip=True))
            else:
                if emit(child, out, depth) == "stop":
                    return "stop"
        return None

    article = soup.select_one("article") or soup.body or soup
    emit(article, main, 1)
    return title, "\n\n".join(main), "\n\n".join(appx), figures


def split_refs_md(md: str):
    """從 Markdown 切掉參考文獻與致謝；參考文獻後面的部分當附錄。"""
    lines = md.splitlines()
    main, appx, mode, fence = [], [], "main", False
    for line in lines:
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        h = None if fence else re.match(r"^#{1,6}\s+(.*)", line)
        head = re.sub(r"[*_`]", "", h[1]).strip() if h else None
        if head is None and not fence and re.match(r"^\*\*[^*]{3,60}\*\*$", line.strip()):
            head = line.strip().strip("*")
        if head is not None:
            plain = re.sub(r"^[\dIVX]+\.?\s*", "", head)
            if REF_HEAD.match(plain) or REF_HEAD.match(head):
                mode = "skip"
                continue
            if mode == "skip" and (APPX_HEAD.match(head) or h):
                mode = "appx"
            elif mode == "appx" and not h:
                pass
        if "picture" in line and "omitted" in line:
            continue
        if mode == "main":
            main.append(line)
        elif mode == "appx":
            appx.append(line)
    return "\n".join(main).strip(), "\n".join(appx).strip()


def pdf_to_md(path: Path):
    import contextlib
    import io
    import pymupdf
    pymupdf.set_messages(stream=io.StringIO())
    with contextlib.redirect_stdout(io.StringIO()):
        import pymupdf4llm
        md = pymupdf4llm.to_markdown(str(path), write_images=False, ignore_images=True, show_progress=False)
    md = re.sub(r"<!-- Start of picture text -->.*?<!-- End of picture text -->", "", md, flags=re.S)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def pdf_title(path: Path) -> str:
    import pymupdf
    doc = pymupdf.open(str(path))
    t = (doc.metadata or {}).get("title") or ""
    if len(t) < 8:
        page = doc[0]
        spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
        if spans:
            big = max(s["size"] for s in spans)
            t = " ".join(s["text"] for s in spans if s["size"] >= big - 0.5).strip()
    return t


def pdf_figures(path: Path, out: Path, limit: int = 12):
    """依圖說（Figure N:）往上框出圖的範圍並截成 PNG，可抓到向量圖。"""
    import pymupdf
    doc = pymupdf.open(str(path))
    figs, seen = [], set()
    cap_re = re.compile(r"^\s*(Figure|Fig\.)\s*([A-Z]?\d+)\s*[:.|]", re.I)  # 也抓附錄的 Figure A1
    for pno, page in enumerate(doc):
        W, H = page.rect.width, page.rect.height
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        drawings = None
        for b in blocks:
            m = cap_re.match(b[4])
            if not m or m[2] in seen:
                continue
            x0, y0, x1, y1 = b[:4]
            if x1 - x0 > W * 0.55:
                cx0, cx1 = 36, W - 36
            elif x0 > W / 2 - 10:
                cx0, cx1 = W / 2, W - 36
            else:
                cx0, cx1 = 36, W / 2
            top = 36
            for o in blocks:
                if o is b or o[3] > y0 - 2:
                    continue
                overlap = min(o[2], cx1) - max(o[0], cx0)
                if overlap > 20 and len(o[4].strip()) > 180:
                    top = max(top, o[3])
            if y0 - top < 50:
                continue
            if drawings is None:
                drawings = page.get_drawings()
            band = pymupdf.Rect(0, top + 1, W, y0 - 1)
            rects = [dr["rect"] for dr in drawings if dr["rect"].intersects(band)]
            rects += [pymupdf.Rect(i["bbox"]) for i in page.get_image_info() if pymupdf.Rect(i["bbox"]).intersects(band)]
            rects += [pymupdf.Rect(o[:4]) for o in blocks if o is not b and len(o[4].strip()) <= 180
                      and pymupdf.Rect(o[:4]).intersects(band)]
            if rects:
                u = rects[0]
                for r in rects[1:]:
                    u = u | r
                cx0, cx1 = max(18, min(cx0, u.x0 - 6)), min(W - 18, max(cx1, u.x1 + 6))
                top = max(top, u.y0 - 8)
            clip = pymupdf.Rect(cx0, top + 2, cx1, y0 - 2)
            pix = page.get_pixmap(clip=clip, dpi=150)
            seen.add(m[2])
            fn = out / f"fig{m[2]}.png"
            pix.save(str(fn))
            figs.append({"n": len(figs) + 1, "caption": " ".join(b[4].split())[:400], "file": fn.name, "page": pno + 1})
            if len(figs) >= limit:
                return figs
    return figs


def build_toc(md: str, part: str):
    lines = md.splitlines()
    heads, fence = [], False
    for i, l in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", l):  # 程式碼區塊裡的 # 註解不是標題
            fence = not fence
        elif not fence and (m := re.match(r"^(#{1,6})\s+(.*)", l)):
            heads.append((i, len(m[1]), m[2].strip()))
    if not heads or heads[0][0] > 0:
        heads.insert(0, (0, 1, "（開頭）"))
    toc = []
    for k, (i, lvl, title) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i:end])
        if not body.strip():
            continue
        toc.append({"part": part, "level": lvl, "title": re.sub(r"[*_`]", "", title),
                    "start": i, "end": end, "tokens": est_tokens(body)})
    return toc


# ---------- fetch ----------

def cache_id_for(src: str, arxiv: str | None) -> str:
    if arxiv:
        return "arxiv-" + arxiv
    return hashlib.sha1(src.encode()).hexdigest()[:10]


def fetch(src: str, refresh: bool = False) -> Path:
    item = None
    if not re.match(r"^https?://", src) and not Path(os.path.expanduser(src)).exists():
        item = resolve(src)
        src = item["url"]
    path = Path(os.path.expanduser(src)) if not src.startswith("http") else None
    m = ARXIV_ID.search(src) if not path else None
    arxiv = m[1] if m and ("arxiv" in src or "dair.ai" in src or "huggingface.co/papers" in src
                           or "alphaxiv" in src) else None
    cid = cache_id_for(str(path.resolve()) if path else src, arxiv)
    d = CACHE / cid
    if d.exists() and (d / "meta.json").exists() and not refresh:
        meta = json.loads((d / "meta.json").read_text("utf-8"))
        if item and not meta.get("digest"):
            meta["digest"] = item
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
        return d
    if d.exists():
        shutil.rmtree(d)
    (d / "figures").mkdir(parents=True)
    title, main, appx, figs, kind, final_url = "", "", "", [], "", src

    if arxiv:
        r = None
        try:
            r = http_get(f"https://arxiv.org/html/{arxiv}")
        except Exception:
            r = None
        if r is not None and r.status_code == 200 and "ltx_" in r.text:
            kind, final_url = "arxiv-html", r.url
            title, main, appx, raw_figs = html_to_md_arxiv(r.text, r.url.rstrip("/"))  # 圖片 src 相對於 /html/ 解析
            for k, f in enumerate(raw_figs[:12], 1):
                try:
                    img = http_get(f["src"])
                    if img.status_code != 200 or "text/html" in img.headers.get("content-type", ""):
                        continue
                    ext = Path(urlparse(f["src"]).path).suffix.lower() or ".png"
                    data = img.content
                    if ext == ".svg":  # 轉成 PNG，模型與 Obsidian 都比較好看
                        import pymupdf
                        svg = pymupdf.open(stream=data, filetype="svg")
                        data, ext = svg[0].get_pixmap(dpi=200).tobytes("png"), ".png"
                    fn = f"fig{k}{ext}"
                    (d / "figures" / fn).write_bytes(data)
                    figs.append({"n": k, "caption": f["caption"][:400], "file": fn})
                except Exception:
                    pass
        else:
            src_pdf = f"https://arxiv.org/pdf/{arxiv}"
            r = http_get(src_pdf)
            if r.status_code != 200:
                die(f"arXiv {arxiv} 抓不到（HTTP {r.status_code}）。")
            (d / "source.pdf").write_bytes(r.content)
            path, kind, final_url = d / "source.pdf", "arxiv-pdf", f"https://arxiv.org/abs/{arxiv}"
    elif path is None:
        gh = re.match(r"^https://github\.com/([^/]+)/([^/#?]+)/?$", src)
        if gh:
            for name in ("README.md", "readme.md", "README.rst", "README"):
                r = http_get(f"https://raw.githubusercontent.com/{gh[1]}/{gh[2]}/HEAD/{name}")
                if r.status_code == 200:
                    kind, title, main = "github-readme", f"{gh[1]}/{gh[2]}", r.text
                    break
        if not kind:
            r = http_get(src)
            if r.status_code >= 400:
                die(f"網頁抓不到（HTTP {r.status_code}），可以改成上傳檔案。")
            if "pdf" in r.headers.get("content-type", "") or r.content[:4] == b"%PDF":
                (d / "source.pdf").write_bytes(r.content)
                path, kind = d / "source.pdf", "pdf"
            else:
                import trafilatura
                kind = "web"
                main = trafilatura.extract(r.text, url=src, output_format="markdown", include_tables=True,
                                           include_comments=False, include_links=False) or ""
                md = trafilatura.extract_metadata(r.text, default_url=src)
                title = (md.title if md else "") or ""
                if len(main) < 300:
                    print("注意：抓到的內文很短，可能有付費牆或需要登入。", file=sys.stderr)

    if path is not None and not kind.endswith("html") and kind not in ("web", "github-readme"):
        if path.suffix.lower() == ".pdf" or kind in ("pdf", "arxiv-pdf"):
            if not path.is_relative_to(d):
                shutil.copy(path, d / "source.pdf")
            kind = kind or "pdf-file"
            title = pdf_title(d / "source.pdf")
            main, appx = split_refs_md(pdf_to_md(d / "source.pdf"))
            figs = pdf_figures(d / "source.pdf", d / "figures")
        elif path.suffix.lower() in (".html", ".htm"):
            import trafilatura
            kind = "html-file"
            raw = path.read_text("utf-8", errors="ignore")
            main = trafilatura.extract(raw, output_format="markdown", include_tables=True) or ""
            md = trafilatura.extract_metadata(raw)
            title = (md.title if md else "") or path.stem
        else:
            kind, title = "text-file", path.stem
            main, appx = split_refs_md(path.read_text("utf-8", errors="ignore"))

    if kind == "github-readme":
        main, appx = split_refs_md(main)
    if not main.strip():
        die("沒有抓到任何內文。")
    (d / "main.md").write_text(main, "utf-8")
    (d / "appendix.md").write_text(appx, "utf-8")
    toc = build_toc(main, "main") + (build_toc(appx, "appendix") if appx.strip() else [])
    meta = {
        "id": cid, "title": title.strip(), "url": final_url if not path or kind.startswith("arxiv") else "",
        "file": str(Path(src).expanduser()) if path and not kind.startswith("arxiv") and kind != "pdf" else "",
        "arxiv": arxiv, "kind": kind, "fetched": dt.datetime.now(TW).isoformat(timespec="seconds"),
        "tokens_main": est_tokens(main), "tokens_appendix": est_tokens(appx),
        "toc": toc, "figures": figs, "digest": item, "note": None,
    }
    if kind == "pdf":
        meta["url"] = src
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return d


def load(cid: str):
    d = CACHE / cid
    if not (d / "meta.json").exists():
        die(f"找不到快取 {cid}，請先執行 fetch。")
    return d, json.loads((d / "meta.json").read_text("utf-8"))


def save_meta(d: Path, meta: dict):
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")


def print_overview(d: Path, meta: dict, budget: int, toc_only: bool):
    it = meta.get("digest") or {}
    print(f"快取ID：{meta['id']}")
    print(f"標題：{meta['title']}")
    if it:
        print(f"早報：{it['digest_date']} 第 {it['digest_no']} 則（{CATEGORY_ZH.get(it['category'], it['category'])}）｜{it['title']}")
    print(f"來源：{meta['url'] or meta['file']}（{meta['kind']}）")
    print(f"正文約 {meta['tokens_main']} tokens，附錄約 {meta['tokens_appendix']} tokens（參考文獻已移除）")
    if meta.get("note"):
        print(f"已有筆記：{meta['note']}")
    print("\n## 目錄（section 指令用左邊的編號）")
    for k, s in enumerate(meta["toc"], 1):
        tag = "［附錄］" if s["part"] == "appendix" else ""
        print(f"{k:>3}. {'  ' * (s['level'] - 1)}{tag}{s['title']}  (~{s['tokens']})")
    if meta["figures"]:
        print("\n## 圖片（note create --figures 用圖號；需要看圖時用 figure 指令取得路徑）")
        for f in meta["figures"]:
            print(f"  圖 {f['n']}：{f['caption'][:160]}")
    if toc_only:
        return
    main = (d / "main.md").read_text("utf-8")
    print("\n## 正文")
    if meta["tokens_main"] <= budget:
        print(main)
        return
    lines = main.splitlines()
    main_toc = [s for s in meta["toc"] if s["part"] == "main"]
    prio = re.compile(r"abstract|摘要|intro|導論|前言|conclu|結論|summary|discussion|method|approach|方法|overview|（開頭）", re.I)
    chosen, used = set(), 0
    for k, s in enumerate(main_toc):
        if prio.search(s["title"]) and used + s["tokens"] <= budget:
            chosen.add(k)
            used += s["tokens"]
    for k, s in enumerate(main_toc):
        if k not in chosen and used + s["tokens"] <= budget:
            chosen.add(k)
            used += s["tokens"]
    skipped = []
    for k, s in enumerate(main_toc):
        if k in chosen:
            print("\n".join(lines[s["start"]:s["end"]]))
        else:
            skipped.append(f"{meta['toc'].index(s) + 1}. {s['title']}")
    print(f"\n（為了省 token，以下章節沒有印出，需要時用 section 指令讀：{'；'.join(skipped)}）")


def get_section(d: Path, meta: dict, key: str) -> str:
    toc = meta["toc"]
    if key.isdigit() and 1 <= int(key) <= len(toc):
        hits = [toc[int(key) - 1]]
    else:
        hits = [s for s in toc if key.lower() in s["title"].lower()]
    if not hits:
        die(f"找不到章節「{key}」。")
    out = []
    for s in hits[:2]:
        text = (d / ("main.md" if s["part"] == "main" else "appendix.md")).read_text("utf-8").splitlines()
        out.append("\n".join(text[s["start"]:s["end"]]))
    return "\n\n".join(out)


def search(d: Path, meta: dict, terms: list[str], k: int = 5) -> str:
    terms = [t.lower() for t in terms if t.strip()]
    results = []
    for part in ("main", "appendix"):
        text = (d / f"{part}.md").read_text("utf-8")
        lines = text.splitlines()
        secs = [s for s in meta["toc"] if s["part"] == part]
        paras, cur, start = [], [], 0
        for i, l in enumerate(lines + [""]):
            if l.strip():
                if not cur:
                    start = i
                cur.append(l)
            elif cur:
                paras.append((start, "\n".join(cur)))
                cur = []
        for start, p in paras:
            low = p.lower()
            score = sum(low.count(t) * (1 + len(t) / 6) for t in terms)
            if score:
                sec = next((s["title"] for s in reversed(secs) if s["start"] <= start), "")
                results.append((score, part, sec, p))
    results.sort(key=lambda r: -r[0])
    if not results:
        return "沒有找到相關段落，可以換個關鍵字（英文論文請用英文關鍵字）。"
    return "\n\n---\n\n".join(f"［{'附錄' if p == 'appendix' else '正文'}｜{s}］\n{t}" for _, p, s, t in results[:k])


# ---------- Obsidian 筆記 ----------

def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", s)
    return re.sub(r"\s+", " ", s).strip()[:80]


def yaml_str(s) -> str:
    return json.dumps(str(s), ensure_ascii=False)


def note_create(cid: str, intro: str, title: str | None, category: str | None, tags: list[str],
                fig_nos: list[int], force: bool) -> Path:
    d, meta = load(cid)
    vault = Path(config()["vault"])
    if not vault.exists():
        die(f"找不到 Obsidian vault：{vault}")
    if meta.get("note") and Path(meta["note"]).exists() and not force:
        print(f"這篇已經有筆記，直接沿用：{meta['note']}")
        return Path(meta["note"])
    it = meta.get("digest") or {}
    title = title or it.get("title") or meta["title"] or cid
    cat = category or CATEGORY_ZH.get(it.get("category", ""), "")
    date = today().isoformat()
    ndir, adir = vault / NOTE_DIR, vault / ATTACH_DIR
    ndir.mkdir(parents=True, exist_ok=True)
    adir.mkdir(parents=True, exist_ok=True)

    figmap = {f["n"]: f for f in meta["figures"]}
    embeds = {}
    for n in fig_nos:
        f = figmap.get(n)
        if not f:
            print(f"注意：沒有圖 {n}，略過。", file=sys.stderr)
            continue
        dst = f"{cid}-{f['file']}"
        shutil.copy(d / "figures" / f["file"], adir / dst)
        cap = " ".join(f["caption"].split())[:200]  # 圖說裡的換行會讓斜體斷掉
        embeds[n] = f"![[{dst}|640]]\n*圖 {n}：{cap}*"
    used = set()

    def repl(m):
        n = int(m[1])
        used.add(n)
        return embeds.get(n, "")
    body = re.sub(r"\{\{\s*fig:(\d+)\s*\}\}", repl, intro.strip())
    rest = [embeds[n] for n in embeds if n not in used]
    if rest:
        body += "\n\n## 關鍵圖\n\n" + "\n\n".join(rest)

    tagset = ["AI早報/文章筆記"] + ([f"AI早報/{cat}"] if cat else []) + [t.strip().lstrip("#") for t in tags if t.strip()]
    fm = ["---", f"title: {yaml_str(title)}",
          f"原文標題: {yaml_str(meta['title'])}" if meta["title"] and meta["title"] != title else None,
          f"來源: {yaml_str(meta['url'])}" if meta["url"] else None,
          f"檔案: {yaml_str(meta['file'])}" if meta.get("file") else None,
          f"arxiv: {yaml_str(meta['arxiv'])}" if meta.get("arxiv") else None,
          f"日期: {date}",
          f"分類: {cat}" if cat else None,
          f"早報: {'內' if it else '外'}",
          f"早報日期: {it['digest_date']}" if it else None,
          f"早報編號: {it['digest_no']}" if it else None,
          "tags:"] + [f"  - {yaml_str(t)}" for t in tagset] + ["---"]
    link = meta["url"] or meta.get("file", "")
    text = "\n".join(x for x in fm if x is not None) + f"\n\n# {title}\n\n"
    if link:
        text += f"> 原文：[{meta['title'] or title}]({link})\n\n" if link.startswith("http") else f"> 原文檔案：`{link}`\n\n"
    text += body + "\n\n## 問答紀錄\n"
    fn = ndir / f"{date} {safe_name(title)}.md"
    k = 2
    while fn.exists() and not force:
        fn = ndir / f"{date} {safe_name(title)} ({k}).md"
        k += 1
    fn.write_text(text, "utf-8")
    meta["note"] = str(fn)
    save_meta(d, meta)
    return fn


def note_qa(cid: str, question: str, answer: str) -> Path:
    d, meta = load(cid)
    if not meta.get("note") or not Path(meta["note"]).exists():
        die("這篇還沒有筆記，請先執行 note create。")
    fn = Path(meta["note"])
    text = fn.read_text("utf-8").rstrip() + "\n"
    if "## 問答紀錄" not in text:
        text += "\n## 問答紀錄\n"
    n = len(re.findall(r"^> \[!question\]", text, re.M)) + 1
    q = " ".join(question.split())
    block = [f"\n> [!question]- Q{n}：{q}"] + [f"> {l}" if l.strip() else ">" for l in answer.strip().splitlines()]
    fn.write_text(text + "\n".join(block) + "\n", "utf-8")
    return fn


# ---------- CLI ----------

def main(argv=None):
    p = argparse.ArgumentParser(prog="aqa", description="文章問答 bot 讀文工具")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("resolve"); s.add_argument("ref", nargs="+")
    s = sub.add_parser("fetch"); s.add_argument("src", nargs="+")
    s.add_argument("--budget", type=int, default=12000, help="正文最多印出多少 tokens")
    s.add_argument("--toc-only", action="store_true"); s.add_argument("--refresh", action="store_true")
    s = sub.add_parser("section"); s.add_argument("id"); s.add_argument("key", nargs="+")
    s = sub.add_parser("search"); s.add_argument("id"); s.add_argument("terms", nargs="+")
    s.add_argument("-k", type=int, default=5)
    s = sub.add_parser("figure"); s.add_argument("id"); s.add_argument("n", type=int)
    s = sub.add_parser("note"); ns = s.add_subparsers(dest="ncmd", required=True)
    c = ns.add_parser("create"); c.add_argument("id"); c.add_argument("--title"); c.add_argument("--category")
    c.add_argument("--tags", default=""); c.add_argument("--figures", default="")
    c.add_argument("--force", action="store_true")
    q = ns.add_parser("qa"); q.add_argument("id"); q.add_argument("-q", "--question", required=True)
    sub.add_parser("list")
    a = p.parse_args(argv)

    if a.cmd == "resolve":
        print(json.dumps(resolve(" ".join(a.ref)), ensure_ascii=False, indent=2))
    elif a.cmd == "fetch":
        d = fetch(" ".join(a.src), a.refresh)
        _, meta = load(d.name)
        print_overview(d, meta, a.budget, a.toc_only)
    elif a.cmd == "section":
        d, meta = load(a.id); print(get_section(d, meta, " ".join(a.key)))
    elif a.cmd == "search":
        d, meta = load(a.id); print(search(d, meta, a.terms, a.k))
    elif a.cmd == "figure":
        d, meta = load(a.id)
        f = next((f for f in meta["figures"] if f["n"] == a.n), None)
        if not f:
            die(f"沒有圖 {a.n}。")
        print(d / "figures" / f["file"]); print(f["caption"])
    elif a.cmd == "note":
        if a.ncmd == "create":
            intro = sys.stdin.read()
            if not intro.strip():
                die("請從 stdin 提供介紹內容。")
            figs = [int(x) for x in re.findall(r"\d+", a.figures)]
            print(note_create(a.id, intro, a.title, a.category, a.tags.split(","), figs, a.force))
        else:
            ans = sys.stdin.read()
            if not ans.strip():
                die("請從 stdin 提供回答內容。")
            print(note_qa(a.id, a.question, ans))
    elif a.cmd == "list":
        metas = sorted(CACHE.glob("*/meta.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:15]
        for f in metas:
            m = json.loads(f.read_text("utf-8"))
            print(f"{m['id']}\t{m['fetched'][:10]}\t{(m.get('digest') or {}).get('title') or m['title']}")


if __name__ == "__main__":
    main()
