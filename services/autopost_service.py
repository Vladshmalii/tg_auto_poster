from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import User, Subscription, AutopostSettings
from services.news_service import NewsService, NewsItem
from services.content_generator import ContentGenerator
from aiogram import Bot
import asyncio
import logging


class AutopostService:
    """Сервис автоматического постинга"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.news_service = NewsService()
        self.content_generator = ContentGenerator()

    async def process_autoposts(self, db: AsyncSession):
        """Обработка всех автопостов"""
        try:
            # Получаем активные подписки
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                )
            )
            active_subscriptions = result.scalars().all()

            for subscription in active_subscriptions:
                await self.process_user_autoposts(db, subscription.user_id)

        except Exception as e:
            logging.error(f"Ошибка обработки автопостов: {e}")

    async def process_user_autoposts(self, db: AsyncSession, user_id: int):
        """Обработка автопостов для конкретного пользователя"""
        try:
            # Получаем настройки автопостинга пользователя
            result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user_id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            settings = result.scalars().all()

            for setting in settings:
                await self.create_scheduled_posts(db, setting)

        except Exception as e:
            logging.error(f"Ошибка обработки автопостов пользователя {user_id}: {e}")

    async def create_scheduled_posts(self, db: AsyncSession, settings: AutopostSettings):
        """Создание запланированных постов"""
        try:
            # Проверяем, не выходные ли сегодня (если включен флаг weekdays_only)
            if settings.weekdays_only and datetime.now().weekday() >= 5:
                return

            # Получаем новости по категории
            news_list = await self.news_service.get_news_by_category(
                settings.category,
                limit=settings.posts_per_day
            )

            for news_item in news_list:
                # Генерируем контент
                content = await self.content_generator.generate_post(
                    news_item,
                    settings.style
                )

                # Отправляем в канал
                await self.send_to_channel(settings.channel_id, content)

                # Добавляем задержку между постами
                await asyncio.sleep(300)  # 5 минут между постами

        except Exception as e:
            logging.error(f"Ошибка создания постов для настройки {settings.id}: {e}")

    async def send_to_channel(self, channel_id: str, content: str):
        """Отправка поста в канал"""
        try:
            await self.bot.send_message(
                chat_id=channel_id,
                text=content,
                parse_mode='HTML',
                disable_web_page_preview=False
            )

            logging.info(f"Пост отправлен в канал {channel_id}")

        except Exception as e:
            logging.error(f"Ошибка отправки в канал {channel_id}: {e}")
