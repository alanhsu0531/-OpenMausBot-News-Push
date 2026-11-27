"""第 1 步：抓取、過濾、去重、分類。

用法：
    python -m news_push.fetch                 # 輸出到 data/YYYY-MM-DD/candidates.json
    python -m news_push.fetch --hours 48      # 調整回溯時間

輸出的 candidates.json 會交給第 2 步（AI 摘要）每類挑選 5 則。
任何單一來源失敗都只會記錄警告，不會讓整個流程中斷。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser
import requests

from . import sources as S

TW = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEEN_FILE = DATA_DIR / "seen_urls.json"
SEEN_KEEP_DAYS = 14
MAX_PER_CATEGORY = 25
SUMMARY_MAX_CHARS = 600
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; daily-ai-digest/1.0)"}
TIMEOUT = 20


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------- 小工具 ----------

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
             "utm_content", "ref", "fbclid", "gclid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in _TRACKING]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def clean_text(text: str | None, limit: int = SUMMARY_MAX_CHARS) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def has_ai_keyword(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t).lower()
    for kw in S.AI_KEYWORDS:
        if kw.isascii() and kw.replace(".", "").isalpha() and len(kw) <= 4:
            # 短英文關鍵字（ai、gpt…）用字邊界比對，避免誤中 "said"、"maid"
            if re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", blob):
                return True
        elif kw in blob:
            return True
    return False


def make_item(category, source, title, url, summary="", published=None, extra=None):
    item = {
        "category": category,
        "source": source,
        "title": clean_text(title, 300),
        "url": url,
        "summary": clean_text(summary),
        "published": published.astimezone(timezone.utc).isoformat() if published else None,
    }
    if extra:
        item.update(extra)
    return item


# ---------- 各類來源 ----------

def get(url: str, **kw) -> requests.Response:
    """GET，遇到 429 或 5xx 會等一下再重試一次。"""
    kw.setdefault("headers", HEADERS)
    kw.setdefault("timeout", TIMEOUT)
    resp = requests.get(url, **kw)
    if resp.status_code == 429 or resp.status_code >= 500:
        time.sleep(15)
        resp = requests.get(url, **kw)
    resp.raise_for_status()
    return resp


def fetch_rss(src: dict, since: datetime) -> list[dict]:
    urls = [src["url"], *src.get("fallback_urls", [])]
    for i, url in enumerate(urls):
        try:
            feed = feedparser.parse(get(url).content)
            if feed.entries or i == len(urls) - 1:
                if i:
                    log(f"[info] {src['name']} 改用 {url}")
                break
        except Exception:
            if i == len(urls) - 1:
                raise
    items = []
    for e in feed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime(*t[:6], tzinfo=timezone.utc) if t else None
        if published and published < since:
            continue
        title, link = e.get("title", ""), e.get("link", "")
        summary = e.get("summary", "") or e.get("description", "")
        if not title or not link:
            continue
        if src.get("keyword_filter") and not has_ai_keyword(title, summary):
            continue
        items.append(make_item(src["category"], src["name"], title, link, summary, published))
    return items


def fetch_hf_daily_papers(since: datetime) -> list[dict]:
    resp = requests.get(S.HF_DAILY_PAPERS_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    items = []
    for row in resp.json():
        paper = row.get("paper", row)
        pid = paper.get("id")
        if not pid:
            continue
        published = None
        ts = row.get("publishedAt") or paper.get("publishedAt")
        if ts:
            published = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if published < since - timedelta(days=1):  # 每日精選本身就有延遲，多放寬一天
                continue
        items.append(make_item(
            S.RESEARCH, "Hugging Face Daily Papers", paper.get("title", ""),
            f"https://huggingface.co/papers/{pid}", paper.get("summary", ""), published,
            {"upvotes": paper.get("upvotes", 0)},
        ))
    items.sort(key=lambda x: x.get("upvotes", 0), reverse=True)
    return items


def fetch_dair_ai_week(now: datetime) -> list[dict]:
    """抓 dair-ai 最新一週的精選論文。靠 seen_urls 避免每天重複推同一批。"""
    resp = requests.get(S.DAIR_AI_YEAR_URL.format(year=now.year), headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code == 404 and now.month == 1:
        resp = requests.get(S.DAIR_AI_YEAR_URL.format(year=now.year - 1), headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    text = resp.text
    m = re.search(r"^## (Top AI Papers of the Week.*?)$", text, re.M)
    if not m:
        return []
    week_title = m.group(1).strip()
    section = text[m.end():]
    nxt = re.search(r"^## ", section, re.M)
    section = section[: nxt.start()] if nxt else section
    items = []
    for line in section.splitlines():
        row = re.match(r"\|\s*\d+\)\s*\*\*(.+?)\*\*\s*-\s*(.*)\|\s*(.*?)\|\s*$", line)
        if not row:
            continue
        title, desc, links = row.groups()
        desc = desc.split("<br>")[0]
        link_m = re.search(r"\[Paper\]\((https?://[^)\s]+)\)", links) or re.search(r"\((https?://[^)\s]+)\)", links)
        if not link_m:
            continue
        items.append(make_item(S.RESEARCH, f"dair-ai {week_title}", title, link_m.group(1), desc))
    return items


def fetch_github_trending(now: datetime) -> list[dict]:
    since_date = (now - timedelta(days=7)).date().isoformat()
    headers = dict(HEADERS, Accept="application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    found: dict[str, dict] = {}
    for topic in S.GITHUB_TOPICS:
        q = f"topic:{topic} created:>={since_date} stars:>={S.GITHUB_MIN_STARS}"
        resp = requests.get("https://api.github.com/search/repositories",
                            params={"q": q, "sort": "stars", "order": "desc", "per_page": 10},
                            headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        for r in resp.json().get("items", []):
            found.setdefault(r["html_url"], r)
    repos = sorted(found.values(), key=lambda r: r["stargazers_count"], reverse=True)
    return [
        make_item(S.TOOLS, "GitHub 新興專案", r["full_name"], r["html_url"], r.get("description") or "",
                  datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                  {"stars": r["stargazers_count"], "language": r.get("language")})
        for r in repos
    ]


# ---------- 去重與狀態 ----------

def load_seen(now: datetime) -> dict[str, str]:
    if not SEEN_FILE.exists():
        return {}
    seen = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    cutoff = (now - timedelta(days=SEEN_KEEP_DAYS)).date().isoformat()
    return {u: d for u, d in seen.items() if d >= cutoff}


def title_key(title: str) -> str:
    return re.sub(r"[\W_]+", "", title.lower())[:80]


def dedupe(items: list[dict], seen: dict[str, str]) -> list[dict]:
    out, urls, titles = [], set(), set()
    for it in items:
        u, t = normalize_url(it["url"]), title_key(it["title"])
        if u in seen or u in urls or (t and t in titles):
            continue
        urls.add(u)
        titles.add(t)
        out.append(it)
    return out


def interleave(items: list[dict]) -> list[dict]:
    """各來源輪流取一則，避免單一來源佔滿名額。"""
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["source"], []).append(it)
    out, queues = [], list(groups.values())
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


# ---------- 主流程 ----------

def run(hours: int, out_path: Path | None) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    today = now.astimezone(TW).date().isoformat()

    jobs = [(src["name"], lambda src=src: fetch_rss(src, since)) for src in S.RSS_SOURCES]
    jobs += [
        ("Hugging Face Daily Papers", lambda: fetch_hf_daily_papers(since)),
        ("dair-ai AI Papers of the Week", lambda: fetch_dair_ai_week(now)),
        ("GitHub 新興專案", lambda: fetch_github_trending(now)),
    ]

    collected, report = [], []
    for name, job in jobs:
        try:
            got = job()
            report.append({"source": name, "ok": True, "count": len(got)})
            log(f"[ok]   {name}: {len(got)}")
            collected.extend(got)
        except Exception as exc:  # 單一來源失敗不影響其他來源
            report.append({"source": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})
            log(f"[fail] {name}: {exc}")

    seen = load_seen(now)
    unique = dedupe(collected, seen)

    by_cat = {c: interleave([it for it in unique if it["category"] == c])[:MAX_PER_CATEGORY]
              for c in S.CATEGORY_NAMES}

    result = {
        "date": today,
        "generated_at": now.isoformat(),
        "lookback_hours": hours,
        "categories": {c: {"name": S.CATEGORY_NAMES[c], "items": by_cat[c]} for c in by_cat},
        "sources": report,
    }

    out_path = out_path or DATA_DIR / today / "candidates.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"寫入 {out_path}：" + "、".join(f"{S.CATEGORY_NAMES[c]} {len(v)} 則" for c, v in by_cat.items()))

    return result


def mark_seen(urls: list[str], day: str | None = None) -> None:
    """記錄已推播的網址，14 天內不再出現。由第 2 步在選出當日新聞後呼叫。"""
    now = datetime.now(timezone.utc)
    day = day or now.astimezone(TW).date().isoformat()
    seen = load_seen(now)
    for u in urls:
        seen[normalize_url(u)] = day
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="抓取每日 AI 科技新聞候選清單")
    p.add_argument("--hours", type=int, default=26, help="回溯幾小時（預設 26）")
    p.add_argument("--out", type=Path, help="輸出檔路徑")
    args = p.parse_args()
    result = run(args.hours, args.out)
    ok = sum(1 for s in result["sources"] if s["ok"])
    total = sum(len(c["items"]) for c in result["categories"].values())
    if ok == 0 or total == 0:
        log("所有來源都失敗或沒有任何內容")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
