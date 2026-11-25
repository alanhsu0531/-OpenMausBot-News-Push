"""新聞來源設定。

三個分類：
- company：AI 科技公司新聞（人事異動、產品決策、商業動態）
- tools：AI 新工具
- research：ML / DL / NLP 新技術與論文

要增減來源，只要改這個檔案。
"""

COMPANY = "company"
TOOLS = "tools"
RESEARCH = "research"

CATEGORY_NAMES = {
    COMPANY: "AI 科技公司新聞",
    TOOLS: "AI 新工具",
    RESEARCH: "ML / DL / NLP 新技術",
}

# 一般 RSS 來源。
# keyword_filter=True 表示來源是綜合科技新聞，只保留標題或摘要含 AI 關鍵字的文章。
RSS_SOURCES = [
    # --- AI 科技公司新聞 ---
    {"name": "TechCrunch AI", "category": COMPANY,
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI", "category": COMPANY,
     "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "VentureBeat AI", "category": COMPANY,
     "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "iThome", "category": COMPANY,
     "url": "https://www.ithome.com.tw/rss", "keyword_filter": True},
    {"name": "科技新報", "category": COMPANY,
     "url": "https://technews.tw/feed/", "keyword_filter": True},
    {"name": "數位時代", "category": COMPANY, "keyword_filter": True,
     # 官方 RSS 位置不固定，依序嘗試
     "url": "https://www.bnext.com.tw/rss/articles",
     "fallback_urls": ["https://www.bnext.com.tw/feed", "https://www.bnext.com.tw/rss/all",
                       "https://feeds.feedburner.com/bnext"]},
    {"name": "INSIDE", "category": COMPANY,
     "url": "https://www.inside.com.tw/feed/rss", "keyword_filter": True},
    # 官方部落格（第一手消息）。Anthropic 沒有官方 RSS，用社群每小時轉製的版本。
    {"name": "OpenAI 官方部落格", "category": COMPANY,
     "url": "https://openai.com/news/rss.xml"},
    {"name": "Anthropic 官方新聞", "category": COMPANY,
     "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"},
    {"name": "Google AI 官方部落格", "category": COMPANY,
     "url": "https://blog.google/technology/ai/rss/"},
    # --- AI 新工具 ---
    {"name": "Product Hunt", "category": TOOLS,
     "url": "https://www.producthunt.com/feed", "keyword_filter": True},
    {"name": "Hacker News Show HN", "category": TOOLS,
     "url": "https://hnrss.org/show?points=50", "keyword_filter": True},
    # --- ML / DL / NLP 新技術 ---
    {"name": "Google DeepMind 部落格", "category": RESEARCH,
     "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Hacker News 熱門 AI 討論", "category": RESEARCH,
     "url": "https://hnrss.org/newest?points=150&q=LLM+OR+transformer+OR+diffusion+OR+%22reinforcement+learning%22"},
]

# Hugging Face 每日精選論文
HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"

# dair-ai 每週精選論文（取最新一週）
DAIR_AI_YEAR_URL = (
    "https://raw.githubusercontent.com/dair-ai/AI-Papers-of-the-Week/main/years/{year}.md"
)

# GitHub 近一週新建且星數成長快的 AI 專案，視為「AI 新工具」
GITHUB_TOPICS = ["llm", "ai-agents", "generative-ai", "mcp"]
GITHUB_MIN_STARS = 100

# 綜合科技來源的 AI 關鍵字（不分大小寫）
AI_KEYWORDS = [
    "ai", "a.i.", "人工智慧", "llm", "gpt", "openai", "anthropic", "claude",
    "gemini", "deepmind", "nvidia", "輝達", "黃仁勳", "copilot", "agent",
    "代理", "模型", "生成式", "machine learning", "機器學習", "深度學習",
    "neural", "transformer", "diffusion", "xai", "grok", "llama", "mistral",
    "deepseek", "qwen", "hugging face", "chatbot", "聊天機器人",
]

# 每類新聞固定的四個面向：(JSON 欄位, emoji, 短標籤, Notion 欄位名, 撰寫說明, Notion 區塊底色)
FACETS = {
    COMPANY: [
        ("event", "📌", "事件", "事件", "誰、做了什麼、什麼時候", "blue_background"),
        ("background", "🧭", "背景", "背景", "為什麼會發生、之前的脈絡", "gray_background"),
        ("impact", "🌊", "影響", "影響", "對產業、競爭對手、使用者的影響", "orange_background"),
        ("outlook", "🔭", "後續觀察", "後續觀察", "接下來值得注意什麼", "purple_background"),
    ],
    TOOLS: [
        ("problem", "🎯", "問題", "解決什麼問題", "這個工具想解決什麼問題", "red_background"),
        ("method", "⚙️", "方法", "用什麼方法", "透過什麼方法或技術解決", "blue_background"),
        ("usage", "🚀", "用法", "如何使用", "如何開始使用", "green_background"),
        ("advantage", "✨", "優勢", "使用後的優勢", "使用後的優勢", "yellow_background"),
    ],
    RESEARCH: [
        ("research_problem", "🧩", "問題", "研究問題", "現有方法卡在哪裡", "red_background"),
        ("core_method", "💡", "核心方法", "核心方法", "新做法的關鍵點子，一兩句講完", "yellow_background"),
        ("results", "📊", "成果", "成果", "實驗數據、跟誰比、贏多少（資料沒提就寫「原文未提供具體數據」）", "green_background"),
        ("implication", "🛠️", "實務意義", "實務意義", "對開發者或產業能怎麼用、有什麼限制", "blue_background"),
    ],
}
