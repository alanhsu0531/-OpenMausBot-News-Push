"""第 2 步：AI 挑選 5 到 10 則新聞、寫繁體中文摘要，產出完整版與 Email 精簡版。

用法：
    python -m news_push.summarize                 # 讀今天的 candidates.json，寫 digest，寄 Email
    python -m news_push.summarize --no-email      # 不寄信（測試用）

產出：
    data/YYYY-MM-DD/digest.md    完整版（OpenMausBot 讀這份）
    data/YYYY-MM-DD/digest.json  結構化資料
    data/latest.md               永遠是最新一天的完整版
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from . import sources as S
from .fetch import DATA_DIR, TW, mark_seen, log
from .llm import chat
from .mailer import send_digest_email
from .notion_sync import sync_to_notion

MIN_ITEMS, MAX_ITEMS = 5, 10
WEEKDAYS = "一二三四五六日"
CATEGORY_ICONS = {S.COMPANY: "🏢", S.TOOLS: "🛠️", S.RESEARCH: "🔬"}

SYSTEM_PROMPT = """你是一位專業的科技新聞編輯，替台灣讀者整理每日 AI 科技早報。
一律使用台灣慣用的繁體中文（例如：軟體、模型、程式、晶片、輝達），專有名詞與產品名可保留英文。
只根據提供的資料撰寫，不可捏造事實、數字或功能；資料不足時就寫得保守一點。
只輸出一個 JSON 物件，不要有任何其他文字或 Markdown 程式碼框。"""

USER_PROMPT = """以下是今天的候選新聞，分成三類：
- company：AI 科技公司新聞（人事異動、產品決策、商業與政策動態）
- tools：AI 新工具
- research：ML / DL / NLP 新技術與論文

請挑出最重要、最有新意的 {min_items} 到 {max_items} 則：
- 三類都要有，每類 2 到 4 則（某類候選不足時例外）
- 優先選影響大、讀者會想點開的；避免同一事件重複
- tools 優先選真的能用的產品或開源專案，略過純行銷文

每則除了摘要，還要依分類填寫四個固定面向（每個面向 1 到 2 句，具體、不空泛）：
{facet_guide}

輸出 JSON 格式：
{{
  "headline": "一句話總結今天最值得注意的趨勢（30 字內）",
  "items": [
    {{
      "id": 候選編號（整數）,
      "title": "繁體中文標題（25 字內）",
      "brief": "一句話重點（40 字內，用於 Email）",
      "summary": "2 到 3 句繁體中文摘要，說明發生什麼事、為什麼重要",
      "facets": {{"面向欄位": "內容", ...}}
    }}
  ]
}}

最近幾天已經報導過的事件（不要再選同一事件，除非有重大新進展）：
{recent}

候選新聞：
{candidates}
"""


def recent_titles(day: str, days: int = 3) -> str:
    """前幾天已推播的標題，讓 AI 避免跨來源重複報導同一事件。"""
    titles = []
    for d in sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir() and p.name < day)[-days:]:
        f = DATA_DIR / d / "digest.json"
        if f.exists():
            for it in json.loads(f.read_text(encoding="utf-8")).get("items", []):
                titles.append(f"- {it.get('title') or it.get('original_title')}")
    return "\n".join(titles) or "（無）"


def facet_guide() -> str:
    lines = []
    for cat, facets in S.FACETS.items():
        parts = "；".join(f'"{key}"（{label}：{desc}）' for key, _, label, _, desc, _ in facets)
        lines.append(f"- {cat}：{parts}")
    return "\n".join(lines)


def item_facets(it: dict) -> list[tuple[str, str, str, str]]:
    """回傳 [(emoji, 短標籤, Notion 欄位名, 內容)]，相容舊版直接放在 item 上的工具欄位。"""
    values = it.get("facets") or {}
    out = []
    for key, emoji, label, notion_name, _, _ in S.FACETS.get(it["category"], []):
        text = (values.get(key) or it.get(key) or "").strip()
        if text:
            out.append((emoji, label, notion_name, text))
    return out


def build_candidate_list(cands: dict) -> tuple[str, dict[int, dict]]:
    lines, index, n = [], {}, 0
    for cat, block in cands["categories"].items():
        for it in block["items"]:
            n += 1
            index[n] = it
            summary = it.get("summary", "")[:350]
            extra = f"（GitHub ⭐{it['stars']}）" if it.get("stars") else ""
            lines.append(f"[{n}] ({cat}) {it['source']}｜{it['title']}{extra}\n    {summary}")
    return "\n".join(lines), index


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("回應中找不到 JSON")
    return json.loads(text[start:end + 1])


def select_with_llm(cands: dict) -> dict:
    listing, index = build_candidate_list(cands)
    prompt = USER_PROMPT.format(min_items=MIN_ITEMS, max_items=MAX_ITEMS, candidates=listing,
                                facet_guide=facet_guide(), recent=recent_titles(cands["date"]))
    last_err = None
    for attempt in range(2):
        raw, model = chat(SYSTEM_PROMPT, prompt)
        try:
            data = parse_json(raw)
            items = []
            for sel in data.get("items", []):
                try:
                    src = index[int(sel["id"])]
                except (KeyError, ValueError, TypeError):
                    continue  # 模型給了不存在的編號就略過，確保網址都是真的
                if any(i["url"] == src["url"] for i in items):
                    continue
                items.append({**sel, "category": src["category"], "source": src["source"],
                              "url": src["url"], "original_title": src["title"]})
            if len(items) < 3:
                raise ValueError(f"有效項目只有 {len(items)} 則")
            return {"headline": data.get("headline", ""), "items": items[:MAX_ITEMS], "model": model}
        except Exception as exc:
            last_err = exc
            log(f"[summarize] 第 {attempt + 1} 次解析失敗：{exc}")
    raise RuntimeError(f"AI 回應無法使用：{last_err}")


def fallback_selection(cands: dict) -> dict:
    """AI 全部失敗時的備案：每類取前 3 則原文標題，至少讓早報照常出現。"""
    items = []
    for cat, block in cands["categories"].items():
        for it in block["items"][:3]:
            items.append({"category": cat, "source": it["source"], "url": it["url"],
                          "title": it["title"], "original_title": it["title"],
                          "brief": it["title"], "summary": it.get("summary", "")[:200]})
    return {"headline": "", "items": items, "model": "fallback"}


def build_warnings(cands: dict, digest: dict) -> None:
    """找出需要提醒的狀況，寫進 digest["warnings"]（會出現在早報開頭與 Email 標題）。"""
    warnings = []
    if digest.get("model") == "fallback":
        warnings.append("今天所有 AI 模型都無法使用，以下只列原文標題，沒有摘要。")
    empty = [S.CATEGORY_NAMES[c] for c, b in cands["categories"].items() if not b["items"]]
    if empty:
        warnings.append(f"「{'、'.join(empty)}」今天沒有抓到任何候選新聞。")
    report = cands.get("sources", [])
    failed = [s["source"] for s in report if not s.get("ok")]
    if report and len(failed) * 2 > len(report):
        warnings.append(f"{len(report)} 個來源中有 {len(failed)} 個抓取失敗，內容可能不完整。")
    digest["warnings"] = warnings
    digest["failed_sources"] = failed


CATEGORY_SHORT = {S.COMPANY: "公司動態", S.TOOLS: "新工具", S.RESEARCH: "新技術"}


def circled(n: int) -> str:
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else f"{n}."


def short_source(src: str) -> str:
    if src.startswith("dair-ai"):
        return "dair-ai 每週精選論文"
    return src


def cell(text: str) -> str:
    return (text or "").replace("|", "／").replace("\n", " ").strip()


def render_markdown(day: str, digest: dict) -> str:
    d = date.fromisoformat(day)
    groups = [(cat, [i for i in digest["items"] if i["category"] == cat]) for cat in S.CATEGORY_NAMES]
    groups = [(c, items) for c, items in groups if items]
    total = sum(len(items) for _, items in groups)
    chars = sum(len(i.get("summary", "")) + sum(len(f[3]) for f in item_facets(i))
                for _, items in groups for i in items)
    minutes = max(1, round(chars / 400))

    out = [f"# ☀️ AI 科技早報｜{day}（週{WEEKDAYS[d.weekday()]}）", "",
           f"**{total} 則精選**　·　閱讀約 {minutes} 分鐘", ""]
    for w in digest.get("warnings") or []:
        out += [f"> ⚠️ **系統提醒**　{w}", ""]
    if digest.get("headline"):
        out += [f"> 💡 **今日焦點**　{digest['headline']}", ""]

    # 今日導覽
    out += ["### 📋 今日導覽", ""]
    n = 0
    for cat, items in groups:
        titles = []
        for it in items:
            n += 1
            titles.append(f"{circled(n)} {it.get('title') or it['original_title']}")
        out.append(f"- {CATEGORY_ICONS[cat]} **{CATEGORY_SHORT[cat]}**　" + "　".join(titles))
    out += ["", "---", ""]

    n = 0
    for cat, items in groups:
        out += [f"## {CATEGORY_ICONS[cat]} {S.CATEGORY_NAMES[cat]}", ""]
        for it in items:
            n += 1
            out += [f"### {circled(n)} {it.get('title') or it['original_title']}", ""]
            if it.get("summary"):
                out += [it["summary"], ""]
            facets = item_facets(it)
            if facets:
                out += ["| 面向 | 說明 |", "| :-- | :-- |"]
                out += [f"| **{emoji} {label}** | {cell(text)} |" for emoji, label, _, text in facets]
                out.append("")
            out += [f"🔗 [閱讀原文]({it['url']})　·　`{short_source(it['source'])}`", ""]
        out += ["---", ""]

    if digest.get("failed_sources"):
        out += [f"*⚠️ 今日抓取失敗的來源：{'、'.join(digest['failed_sources'])}*", ""]
    out += [f"*🤖 由 {digest.get('model', '')} 整理　·　產生於 {datetime.now(TW):%Y-%m-%d %H:%M}（台灣時間）*", ""]
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="AI 挑選與摘要每日新聞")
    p.add_argument("--date", help="日期 YYYY-MM-DD（預設今天，台灣時間）")
    p.add_argument("--rerender", action="store_true", help="不呼叫 AI，只用既有 digest.json 重新產生排版")
    p.add_argument("--no-email", action="store_true", help="不寄 Email")
    p.add_argument("--no-notion", action="store_true", help="不同步 Notion")
    p.add_argument("--notion-only", action="store_true", help="只把既有 digest.json 同步到 Notion")
    args = p.parse_args()

    day = args.date or datetime.now(TW).date().isoformat()
    day_dir = DATA_DIR / day
    cands = json.loads((day_dir / "candidates.json").read_text(encoding="utf-8"))

    if args.notion_only:
        digest = json.loads((day_dir / "digest.json").read_text(encoding="utf-8"))
        sync_to_notion(day, digest)
        return 0

    if args.rerender:
        digest = json.loads((day_dir / "digest.json").read_text(encoding="utf-8"))
        md = render_markdown(day, digest)
        (day_dir / "digest.md").write_text(md, encoding="utf-8")
        (DATA_DIR / "latest.md").write_text(md, encoding="utf-8")
        log("[summarize] 已重新排版")
        return 0

    try:
        digest = select_with_llm(cands)
    except Exception as exc:
        log(f"[summarize] 改用備案：{exc}")
        digest = fallback_selection(cands)
    digest["date"] = day
    build_warnings(cands, digest)
    for w in digest["warnings"]:
        log(f"[summarize] ⚠️ {w}")

    md = render_markdown(day, digest)
    (day_dir / "digest.md").write_text(md, encoding="utf-8")
    (day_dir / "digest.json").write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "latest.md").write_text(md, encoding="utf-8")
    log(f"[summarize] 寫入 {day_dir / 'digest.md'}，共 {len(digest['items'])} 則，模型 {digest['model']}")

    if digest["model"] != "fallback":
        mark_seen([i["url"] for i in digest["items"]], day)

    if not args.no_email:
        send_digest_email(day, digest)
    if not args.no_notion and digest["model"] != "fallback":
        sync_to_notion(day, digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
