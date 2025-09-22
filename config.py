import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RSS_FEEDS = os.getenv("RSS_FEEDS")
PREVIEW_NEWS_CHANNEL_ID = os.getenv("PREVIEW_NEWS_CHANNEL_ID")
PUBLISH_NEWS_CHANNEL_ID = os.getenv("PUBLISH_NEWS_CHANNEL_ID")
TELEGRAPH_ACCESS_TOKEN = os.getenv("TELEGRAPH_ACCESS_TOKEN")
RSS_ARTICLES_COUNT = int(os.getenv("RSS_ARTICLES_COUNT", "5"))  # Default to 5 if not set
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60")) # Default to 60 seconds
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")


# Basic validation to ensure all variables are set
if not all([
    TELEGRAM_BOT_TOKEN,
    OPENAI_API_KEY,
    RSS_FEEDS,
    PREVIEW_NEWS_CHANNEL_ID,
    PUBLISH_NEWS_CHANNEL_ID,
    TELEGRAPH_ACCESS_TOKEN
]):
    raise ValueError("One or more required environment variables are not set. Please check your .env file.")

# Validate RSS_ARTICLES_COUNT
if RSS_ARTICLES_COUNT < 1 or RSS_ARTICLES_COUNT > 10:
    raise ValueError("RSS_ARTICLES_COUNT must be between 1 and 10.")

# Validate CHECK_INTERVAL_SECONDS
if CHECK_INTERVAL_SECONDS < 10 or CHECK_INTERVAL_SECONDS > 3600: # From 10 seconds to 1 hour
    raise ValueError("CHECK_INTERVAL_SECONDS must be between 10 and 3600.")

