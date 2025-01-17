import os
from dotenv import load_dotenv

# load .env file to environment
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_SESSION = os.getenv("PROFILE")

