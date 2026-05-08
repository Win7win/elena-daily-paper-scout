from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("ELENA_DATA_DIR", str(PROJECT_ROOT / "data"))).expanduser()
CACHE_DIR = DATA_DIR / "cache"
MEMORY_PATH = DATA_DIR / "memory.json"
STATE_PATH = DATA_DIR / "state.json"
ARCHIVE_PATH = DATA_DIR / "paper_archive.json"
TMP_DIR = DATA_DIR / "tmp"

ARXIV_CATEGORIES = ["cs.CL", "cs.AI", "cs.LG", "cs.IR"]
ARXIV_DAYS_BACK = 2
ARXIV_MAX_RESULTS = 60
GITHUB_TRENDING_URL = "https://github.com/trending"
HUGGINGFACE_PAPERS_URL = "https://huggingface.co/papers"
MAX_CANDIDATES_AFTER_FILTER = 12
MAX_FINAL_SEND_COUNT = 3
RECENTLY_SENT_WINDOW = 30
DAILY_PAPER_FETCH_LIMIT = 30
DAILY_PAPER_TOP_K = 5

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
MINERU_TIMEOUT_SECONDS = int(os.getenv("MINERU_TIMEOUT_SECONDS", "900"))
MINERU_CUDA_VISIBLE_DEVICES = os.getenv("MINERU_CUDA_VISIBLE_DEVICES")

# Optional: classic Feishu webhook for plain-text fallback push.
FEISHU_BOT_WEBHOOK = os.getenv("FEISHU_BOT_WEBHOOK")
FEISHU_BOT_SECRET = os.getenv("FEISHU_BOT_SECRET")
FEISHU_BOT_KEYWORD = os.getenv("FEISHU_BOT_KEYWORD", "elena")

# Required for interactive cards + card.action.trigger callbacks.
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_DAILY_CHAT_ID = os.getenv("FEISHU_DAILY_CHAT_ID")

# Card template ID + version for each card. Fill in after importing the
# templates in feishu_cards/ into your own Feishu card builder.
FEISHU_TEMPLATE_DAILY_SUMMARY = (
    os.getenv("FEISHU_TEMPLATE_DAILY_SUMMARY_ID", ""),
    os.getenv("FEISHU_TEMPLATE_DAILY_SUMMARY_VERSION", ""),
)
FEISHU_TEMPLATE_ARXIV_PAPER = (
    os.getenv("FEISHU_TEMPLATE_ARXIV_PAPER_ID", ""),
    os.getenv("FEISHU_TEMPLATE_ARXIV_PAPER_VERSION", ""),
)
FEISHU_TEMPLATE_HF_PAPERS = (
    os.getenv("FEISHU_TEMPLATE_HF_PAPERS_ID", ""),
    os.getenv("FEISHU_TEMPLATE_HF_PAPERS_VERSION", ""),
)
FEISHU_TEMPLATE_GH_TRENDING = (
    os.getenv("FEISHU_TEMPLATE_GH_TRENDING_ID", ""),
    os.getenv("FEISHU_TEMPLATE_GH_TRENDING_VERSION", ""),
)

HTTP_RETRY_ATTEMPTS = int(os.getenv("HTTP_RETRY_ATTEMPTS", "4"))
HTTP_RETRY_MIN_WAIT_SECONDS = int(os.getenv("HTTP_RETRY_MIN_WAIT_SECONDS", "2"))
HTTP_RETRY_MAX_WAIT_SECONDS = int(os.getenv("HTTP_RETRY_MAX_WAIT_SECONDS", "20"))
DAILY_SCHEDULE_UTC = os.getenv("DAILY_SCHEDULE_UTC", "02:30")
SERVER_POLL_SECONDS = int(os.getenv("SERVER_POLL_SECONDS", "30"))
