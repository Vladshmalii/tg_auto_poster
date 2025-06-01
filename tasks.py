from celery_app import celery_app
from aiogram import Bot
from database.database import async_session
from services.autopost_service import AutopostService
from config.settings import settings
import asyncio


@celery_app.task
def process_autoposts():
    """Задача обработки автопостов"""
    asyncio.run(_process_autoposts_async())


async def _process_autoposts_async():
    """Асинхронная обработка автопостов"""
    bot = Bot(token=settings.BOT_TOKEN)
    autopost_service = AutopostService(bot)

    async with async_session() as db:
        await autopost_service.process_autoposts(db)

    await bot.session.close()


@celery_app.task
def cleanup_old_test_post_limits():
    """Очистка старых записей тестовых постов (старше 30 дней)"""
    asyncio.run(_cleanup_old_test_post_limits_async())


async def _cleanup_old_test_post_limits_async():
    """Асинхронная очистка старых записей"""
    try:
        async with async_session() as db:
            # Удаляем записи старше 30 дней
            cutoff_date = date.today() - timedelta(days=30)

            result = await db.execute(
                delete(TestPostLimit).where(TestPostLimit.test_date < cutoff_date)
            )

            await db.commit()

            logging.info(f"Удалено {result.rowcount} старых записей тестовых постов")

    except Exception as e:
        logging.error(f"Ошибка очистки старых записей: {e}")