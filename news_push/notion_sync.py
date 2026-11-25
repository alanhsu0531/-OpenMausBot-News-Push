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


def _page_body(it: dict) -> list[dict]:
    blocks = []
    if it.get("summary"):
        blocks.append({"object": "block", "type": "paragraph",
                       "paragraph": {"rich_text": _text(it["summary"])}})
    for key, label in (("problem", "解決什麼問題"), ("method", "用什麼方法"),
                       ("usage", "如何使用"), ("advantage", "使用後的優勢")):
        if it.get(key):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": f"{label}："},
                               "annotations": {"bold": True}}] + _text(it[key])}})
    blocks.append({"object": "block", "type": "bookmark", "bookmark": {"url": it["url"]}})
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
                "解決什麼問題": {"rich_text": _text(it.get("problem"))},
                "用什麼方法": {"rich_text": _text(it.get("method"))},
                "如何使用": {"rich_text": _text(it.get("usage"))},
                "使用後的優勢": {"rich_text": _text(it.get("advantage"))},
                "來源": {"select": {"name": it["source"].replace(",", " ")[:100]}},
                "連結": {"url": it["url"]},
                "原文標題": {"rich_text": _text(it.get("original_title"))},
                "模型": {"rich_text": _text(digest.get("model"))},
            }
            _request("POST", "/pages", token, {
                "parent": {"database_id": db},
                "icon": {"type": "emoji", "emoji": {"company": "🏢", "tools": "🛠️", "research": "🔬"}[it["category"]]},
                "properties": props,
                "children": _page_body(it),
            })
            added += 1
        except Exception as exc:
            log(f"[notion] 寫入失敗「{it.get('title')}」：{exc}")
    log(f"[notion] 新增 {added} 則")
    return added
