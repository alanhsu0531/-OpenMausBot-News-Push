"""把每日早報寫進 Notion 資料庫（每則新聞一列）。

需要：
    NOTION_TOKEN        Notion internal integration 的 token（GitHub Secret）
    NOTION_DATABASE_ID  資料庫 ID（選填，預設為已建立的「AI 科技早報資料庫」）
沒有設定 NOTION_TOKEN 時只記錄警告並略過。同一個連結已存在就不重複寫入。
"""

from __future__ import annotations

import os
import sys
import time

import requests

from . import sources as S

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
DEFAULT_DATABASE_ID = "423cb9312555818b9ee8f72de377b072"
MAX_TEXT = 1900  # Notion 單段文字上限 2000 字


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _text(value: str | None) -> list[dict]:
    value = (value or "").strip()
    return [{"type": "text", "text": {"content": value[:MAX_TEXT]}}] if value else []


def _request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
               "Content-Type": "application/json"}
    for attempt in range(3):
        resp = requests.request(method, f"{API}{path}", headers=headers, json=body, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(float(resp.headers.get("Retry-After", 2 + attempt * 3)))
            continue
        if not resp.ok:
            raise RuntimeError(f"Notion HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise RuntimeError(f"Notion HTTP {resp.status_code}: {resp.text[:300]}")


def _exists(db: str, token: str, url: str) -> bool:
    res = _request("POST", f"/databases/{db}/query", token,
                   {"filter": {"property": "連結", "url": {"equals": url}}, "page_size": 1})
    return bool(res.get("results"))


CATEGORY_STYLE = {  # (icon, 主色, 背景色)
    "company": ("🏢", "blue", "blue_background"),
    "tools": ("🛠️", "green", "green_background"),
    "research": ("🔬", "purple", "purple_background"),
}
FACET_HEADINGS = {"company": "🧭 事件解析", "tools": "🧰 工具解析", "research": "🔬 技術解析"}


def _facets(it: dict) -> list[tuple]:
    """[(emoji, 短標籤, Notion 欄位名, 內容, 底色)]，相容舊版直接放在 item 上的欄位。"""
    values = it.get("facets") or {}
    out = []
    for key, emoji, label, notion_name, _, bg in S.FACETS.get(it["category"], []):
        text = (values.get(key) or it.get(key) or "").strip()
        if text:
            out.append((emoji, label, notion_name, text, bg))
    return out


def _short_source(src: str) -> str:
    if src.startswith("dair-ai"):
        return "dair-ai 每週精選論文"
    return src.replace(",", " ")[:100]


def _rt(content: str, bold=False, color="default", link=None) -> dict:
    text = {"content": content[:MAX_TEXT]}
    if link:
        text["link"] = {"url": link}
    return {"type": "text", "text": text, "annotations": {"bold": bold, "color": color}}


def _block(kind: str, **payload) -> dict:
    return {"object": "block", "type": kind, kind: payload}


def _callout(icon: str, color: str, rich: list[dict]) -> dict:
    return _block("callout", rich_text=rich, icon={"type": "emoji", "emoji": icon}, color=color)


def _page_body(it: dict, day: str, model: str) -> list[dict]:
    icon, color, bg = CATEGORY_STYLE[it["category"]]
    blocks = []
    if it.get("brief"):
        blocks.append(_callout("💡", bg, [_rt(it["brief"], bold=True)]))
    if it.get("summary"):
        blocks += [_block("heading_3", rich_text=[_rt("📝 重點摘要", color=color)]),
                   _block("paragraph", rich_text=_text(it["summary"]))]
    facets = _facets(it)
    if facets:
        blocks.append(_block("heading_3", rich_text=[_rt(FACET_HEADINGS[it["category"]], color=color)]))
        for emoji, label, _, text, fbg in facets:
            blocks.append(_callout(emoji, fbg, [_rt(f"{label}\n", bold=True), _rt(text)]))
    blocks += [_block("divider"),
               _block("heading_3", rich_text=[_rt("🔗 原文連結", color=color)]),
               _block("bookmark", url=it["url"]),
               _block("paragraph", rich_text=[
                   _rt(f"{icon} {S.CATEGORY_NAMES[it['category']]}　·　來源：{_short_source(it['source'])}　·　收錄於 {day}　·　由 {model} 整理",
                       color="gray")])]
    return blocks


def sync_to_notion(day: str, digest: dict) -> int:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        log("[notion] 沒有設定 NOTION_TOKEN，略過同步")
        return 0
    db = (os.environ.get("NOTION_DATABASE_ID") or DEFAULT_DATABASE_ID).replace("-", "")
    added = 0
    for it in digest["items"]:
        try:
            if _exists(db, token, it["url"]):
                continue
            props = {
                "標題": {"title": _text(it.get("title") or it["original_title"])},
                "日期": {"date": {"start": day}},
                "分類": {"select": {"name": S.CATEGORY_NAMES[it["category"]]}},
                "一句話重點": {"rich_text": _text(it.get("brief"))},
                "摘要": {"rich_text": _text(it.get("summary"))},
                "來源": {"select": {"name": _short_source(it["source"])}},
                "連結": {"url": it["url"]},
                "原文標題": {"rich_text": _text(it.get("original_title"))},
                "模型": {"rich_text": _text(digest.get("model"))},
            }
            for _, _, notion_name, text, _ in _facets(it):
                props[notion_name] = {"rich_text": _text(text)}
            _request("POST", "/pages", token, {
                "parent": {"database_id": db},
                "icon": {"type": "emoji", "emoji": CATEGORY_STYLE[it["category"]][0]},
                "properties": props,
                "children": _page_body(it, day, digest.get("model", "")),
            })
            added += 1
        except Exception as exc:
            log(f"[notion] 寫入失敗「{it.get('title')}」：{exc}")
    log(f"[notion] 新增 {added} 則")
    return added
