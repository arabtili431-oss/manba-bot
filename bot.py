import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, get_user_count, get_new_users_today, get_total_downloads
from handlers import user, admin


async def daily_stats_scheduler(bot: Bot):
    """Har kuni soat 00:00 da adminga statistika yuboruvchi background task."""
    while True:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        next_run = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        sleep_seconds = (next_run - now).total_seconds()

        await asyncio.sleep(sleep_seconds)

        user_count = await get_user_count()
        new_today = await get_new_users_today()
        downloads = await get_total_downloads()

        text = (
            f"📊 **Kunlik avtomatik statistika (00:00)**\n\n"
            f"👥 Jami foydalanuvchilar: {user_count}\n"
            f"➕ Bugun qo'shilganlar: {new_today}\n"
            f"📥 Jami yuklab olishlar: {downloads}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Statistika yuborishda xatolik: {e}")


async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Background taskni ishga tushirish
    asyncio.create_task(daily_stats_scheduler(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
