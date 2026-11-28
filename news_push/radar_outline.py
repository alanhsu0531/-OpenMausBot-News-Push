"""除錯用：列出 AI 日報平台某天頁面的標題與連結結構。python -m news_push.radar_outline 2026-11-01"""
import re
import sys

import requests

from . import sources as S
from .fetch import HEADERS

url = S.RADAR_ISSUE_URL.format(date=sys.argv[1])
page = requests.get(url, headers=HEADERS, timeout=20).text
print(url, len(page))
pat = r'<(h[1-4]|article|section|li)\b[^>]*>.{0,120}|<a\b[^>]*href="[^"]+"[^>]*>[^<]{0,40}'
page = re.split(r'class="past-feed"', page)[0]
for art in re.findall(r"<article\b.*?</article>", page, re.S):
    print("ARTICLE:", re.sub(r"\s+", " ", art)[:1500])
