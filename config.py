import os 
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("bot_token")
ADMIN_ID = int(os.getenv("admin_id"))
SUPERUSER_ID = os.getenv("SUPERUSER_ID")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD")
NOTIFIER_BOT_TOKEN = os.getenv("notifier_bot_token")