import os 
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("bot_token")
ADMIN_ID = int(os.getenv("admin_id"))