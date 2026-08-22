import os

BOT_TOKEN = os.getenv("8713448922:AAGk036UO2TUnbKHsPZ9NOLb68Ezkr1ZM30")
ADMIN_IDS = [123456789]
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
