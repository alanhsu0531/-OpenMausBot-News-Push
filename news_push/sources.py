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
    # --- AI 新工具 ---
    {"name": "Product Hunt", "category": TOOLS,
     "url": "https://www.producthunt.com/feed", "keyword_filter": True},
    {"name": "Hacker News Show HN", "category": TOOLS,
     "url": "https://hnrss.org/show?points=50", "keyword_filter": True},
    # --- ML / DL / NLP 新技術 ---
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
