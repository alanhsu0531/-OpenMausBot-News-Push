"""寄出 Email 精簡版（Gmail SMTP + 應用程式密碼，免費）。

需要的環境變數（放在 GitHub Secrets）：
    GMAIL_ADDRESS       寄件的 Gmail 帳號
    GMAIL_APP_PASSWORD  Gmail 應用程式密碼
    MAIL_TO             收件人，多個用逗號分隔（未設定時寄給自己）
任一必要變數缺少時只記錄警告，不會讓流程失敗。
"""

from __future__ import annotations

import html
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import sources as S


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def build_email(day: str, digest: dict) -> tuple[str, str, str]:
    subject = f"AI 科技早報 {day}"
    text_lines, html_parts = [subject, ""], []
    if digest.get("headline"):
        text_lines += [digest["headline"], ""]
        html_parts.append(f'<p style="font-size:16px;color:#333"><b>{html.escape(digest["headline"])}</b></p>')
    for cat, name in S.CATEGORY_NAMES.items():
        items = [i for i in digest["items"] if i["category"] == cat]
        if not items:
            continue
        text_lines.append(f"【{name}】")
        html_parts.append(f'<h3 style="margin:18px 0 6px;color:#1a4d8f">{html.escape(name)}</h3><ul style="padding-left:20px">')
        for it in items:
            title = it.get("title") or it["original_title"]
            brief = it.get("brief") or ""
            text_lines.append(f"・{title}：{brief}\n  {it['url']}")
            html_parts.append(
                f'<li style="margin-bottom:8px"><a href="{html.escape(it["url"])}" style="color:#0b57d0">'
                f'{html.escape(title)}</a><br><span style="color:#555">{html.escape(brief)}</span></li>')
        html_parts.append("</ul>")
        text_lines.append("")
    text_lines.append("完整內容請看 OpenMausBot。")
    html_parts.append('<p style="color:#888;font-size:13px">完整內容請看 OpenMausBot。</p>')
    body_html = ('<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:640px">'
                 f'<h2 style="margin-bottom:4px">{html.escape(subject)}</h2>' + "".join(html_parts) + "</div>")
    return subject, "\n".join(text_lines), body_html


def send_digest_email(day: str, digest: dict) -> bool:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender or not password:
        log("[mail] 沒有設定 GMAIL_ADDRESS 或 GMAIL_APP_PASSWORD，略過寄信")
        return False
    recipients = [r.strip() for r in (os.environ.get("MAIL_TO") or sender).split(",") if r.strip()]
    subject, text, body_html = build_email(day, digest)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, ", ".join(recipients)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password.replace(" ", ""))
            smtp.sendmail(sender, recipients, msg.as_string())
        log(f"[mail] 已寄出給 {len(recipients)} 位收件人")
        return True
    except Exception as exc:
        log(f"[mail] 寄信失敗：{exc}")
        return False
