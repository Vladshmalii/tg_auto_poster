# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from config.settings import settings
from bot.handlers import start, test_posting, subscription, faq, admin
from database.database import engine
from database.models import Base
from dotenv import load_dotenv
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Загрузите .env файл явно
load_dotenv()

# Проверьте что переменная загрузилась
print(f"ADMIN_IDS from env: {os.getenv('ADMIN_IDS')}")

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await create_tables()

    bot = Bot(token=settings.BOT_TOKEN)

    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    dp.include_router(start.router)
    dp.include_router(test_posting.router)
    dp.include_router(subscription.router)
    dp.include_router(faq.router)
    dp.include_router(admin.router)

    logger.info("🤖 Бот запущен!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())