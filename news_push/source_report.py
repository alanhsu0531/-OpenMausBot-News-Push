"""統計最近幾天各來源的表現，用來決定要不要刪掉產出很少的來源。

用法：
    python -m news_push.source_report            # 最近 7 天
    python -m news_push.source_report --days 14
欄位：成功天數／總天數、平均每天候選數、被 AI 選進早報的總則數。
"""

from __future__ import annotations

import argparse
import json
import sys

from .fetch import DATA_DIR


def main() -> int:
    p = argparse.ArgumentParser(description="來源表現統計")
    p.add_argument("--days", type=int, default=7)
    args = p.parse_args()
    days = sorted(d.name for d in DATA_DIR.iterdir() if d.is_dir() and (d / "candidates.json").exists())[-args.days:]
    stats: dict[str, dict] = {}
    for d in days:
        cands = json.loads((DATA_DIR / d / "candidates.json").read_text(encoding="utf-8"))
        for s in cands.get("sources", []):
            st = stats.setdefault(s["source"], {"runs": 0, "ok": 0, "count": 0, "picked": 0})
            st["runs"] += 1
            st["ok"] += bool(s.get("ok"))
            st["count"] += s.get("count", 0)
        f = DATA_DIR / d / "digest.json"
        if f.exists():
            for it in json.loads(f.read_text(encoding="utf-8")).get("items", []):
                key = "dair-ai AI Papers of the Week" if it["source"].startswith("dair-ai") else it["source"]
                stats.setdefault(key, {"runs": 0, "ok": 0, "count": 0, "picked": 0})["picked"] += 1
    print(f"統計 {days[0] if days else '-'} ~ {days[-1] if days else '-'}（{len(days)} 天）\n")
    print("| 來源 | 成功天數 | 平均候選數 | 入選則數 |\n| :-- | --: | --: | --: |")
    for name, st in sorted(stats.items(), key=lambda kv: (kv[1]["picked"], kv[1]["count"]), reverse=True):
        avg = st["count"] / st["runs"] if st["runs"] else 0
        print(f"| {name} | {st['ok']}/{st['runs']} | {avg:.1f} | {st['picked']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
