"""Configuration loaded from .env file."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Telegram
TG_API_ID = int(os.environ.get("TG_API_ID", "0"))
TG_API_HASH = os.environ.get("TG_API_HASH", "")
TG_SESSION = os.environ.get("TG_SESSION", "")
TG_CHAT_ID = int(os.environ.get("TG_CHAT_ID", "0"))

# OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# LLM model (via OpenRouter)
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemini-3.1-flash-lite-preview")

# Paths
DB_PATH = PROJECT_ROOT / "chat.db"
STREAMS_DIR = PROJECT_ROOT / "docs" / "streams"
STREAMS_CONFIG = PROJECT_ROOT / "streams.json"

# Batch size for classification
CLASSIFY_BATCH_SIZE = 30


def load_streams() -> dict:
    """Load stream definitions from streams.json."""
    if STREAMS_CONFIG.exists():
        with open(STREAMS_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    return {
        "general": {
            "display_name": "General",
            "description": "General discussion not fitting other streams",
        }
    }


STREAMS = load_streams()
