import os

# BotFather'dan olgan tokeningizni shu yerga qo'ying
# Yaxshiroq usul: muhit o'zgaruvchisi (environment variable) orqali saqlash
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_TOKENINGIZ_BU_YERGA")

# Admin(lar) Telegram user ID raqami (bir nechta bo'lishi mumkin)
# O'z ID raqamingizni bilish uchun @userinfobot ga yozing
ADMIN_IDS = [
    123456789,  # <-- shu yerga o'z Telegram ID raqamingizni yozing
]

# PostgreSQL bazasiga ulanish manzili.
# Railway'da Postgres service qo'shilgach, u avtomatik DATABASE_URL o'zgaruvchisini beradi.
# Bu botning Variables bo'limida DATABASE_URL ni Postgres service'ga bog'lash kerak
# (Railway'da: ${{Postgres.DATABASE_URL}} kabi reference orqali).
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres://"):
    # asyncpg "postgresql://" prefiksini talab qiladi
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
