import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [123456789]
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
