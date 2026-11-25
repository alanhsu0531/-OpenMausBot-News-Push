"""流程失敗時的提醒：寄一封警示 Email，並把 data/latest.md 換成失敗通知。

由 GitHub Actions 在任一步驟失敗時執行（if: failure()）。
latest.md 的第一行仍保留今天日期，OpenMausBot 讀到就會把通知貼出來。
如果今天的早報其實已經產生（例如只有存檔步驟失敗），就不覆蓋 latest.md。
"""

from __future__ import annotations

import html
import os
import sys
from datetime import date, datetime

from .fetch import DATA_DIR, TW, log
from .mailer import send_mail

WEEKDAYS = "一二三四五六日"


def main() -> int:
    now = datetime.now(TW)
    day = now.date().isoformat()
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")

    latest = DATA_DIR / "latest.md"
    already_done = (DATA_DIR / day / "digest.md").exists()
    if not already_done:
        weekday = WEEKDAYS[date.fromisoformat(day).weekday()]
        lines = [f"# ⚠️ AI 科技早報｜{day}（週{weekday}）", "",
                 "> ⚠️ **今天的早報產生失敗**　自動流程在整理新聞時出錯，今天暫時沒有內容。", "",
                 "可以到 GitHub Actions 手動重新執行（Run workflow），成功後這裡會換成正式早報。", ""]
        if run_url:
            lines += [f"🔧 [查看執行紀錄]({run_url})", ""]
        lines += [f"*產生於 {now:%Y-%m-%d %H:%M}（台灣時間）*", ""]
        latest.write_text("\n".join(lines), encoding="utf-8")
        log("[alert] 已把 latest.md 換成失敗通知")

    subject = f"⚠️ AI 科技早報 {day} 產生失敗"
    detail = ("早報已經產生，但後續步驟（例如存檔）失敗。" if already_done
              else "今天的早報沒有產生，OpenMausBot 會顯示失敗通知。")
    text = f"{subject}\n\n{detail}\n\n執行紀錄：{run_url or '（無）'}\n"
    body = (f'<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:640px">'
            f'<h2 style="color:#a50e0e">{html.escape(subject)}</h2><p>{html.escape(detail)}</p>'
            + (f'<p><a href="{html.escape(run_url)}">查看執行紀錄</a></p>' if run_url else "") + "</div>")
    send_mail(subject, text, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
