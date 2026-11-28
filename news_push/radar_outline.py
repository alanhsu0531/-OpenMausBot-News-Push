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
for m in re.finditer(pat, page, re.S):
    print(re.sub(r"\s+", " ", m.group(0))[:180])
