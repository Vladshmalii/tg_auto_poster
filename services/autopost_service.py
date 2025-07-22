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

    def __init__(self, bot: Bot):
        self.bot = bot
        self.news_service = NewsService()
        self.content_generator = ContentGenerator()

    async def process_autoposts(self, db: AsyncSession):
        try:
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
        try:
            result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user_id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            settings = result.scalars().all()

            current_time = datetime.now().strftime('%H:%M')

            for setting in settings:
                if self.should_post_now(setting, current_time):
                    await self.create_scheduled_posts(db, setting)

        except Exception as e:
            logging.error(f"Ошибка обработки автопостов пользователя {user_id}: {e}")

    def should_post_now(self, settings: AutopostSettings, current_time: str) -> bool:
        if not settings.specific_times:
            return False

        post_times = settings.specific_times.split(',')
        return current_time in [time.strip() for time in post_times]

    async def create_scheduled_posts(self, db: AsyncSession, settings: AutopostSettings):
        try:
            if hasattr(settings, 'weekdays_only') and settings.weekdays_only and datetime.now().weekday() >= 5:
                return

            news_list = await self.news_service.get_news_by_category(
                settings.category,
                limit=1
            )

            if not news_list:
                logging.warning(f"Нет новостей для категории {settings.category}")
                return

            news_item = news_list[0]
            content = await self.content_generator.generate_post(
                news_item,
                settings.style
            )

            await self.send_to_channel(settings.channel_id, content)

        except Exception as e:
            logging.error(f"Ошибка создания постов для настройки {settings.id}: {e}")

    async def send_to_channel(self, channel_id: str, content: str):
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

    async def send_single_post(self, db: AsyncSession, user_id: int, channel_id: str, category: str, style: str):
        try:
            news_list = await self.news_service.get_news_by_category(category, limit=1)

            if not news_list:
                logging.warning(f"Нет новостей для категории {category}")
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Нет доступных новостей для категории {category}"
                    )
                except:
                    pass
                return

            news_item = news_list[0]
            content = await self.content_generator.generate_post(news_item, style)

            await self.send_to_channel(channel_id, content)

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Пост успешно отправлен в канал {channel_id}"
                )
            except:
                pass

            logging.info(f"Ручной пост отправлен в {channel_id} для пользователя {user_id}")

        except Exception as e:
            logging.error(f"Ошибка отправки ручного поста: {e}")

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Ошибка отправки поста в канал {channel_id}\n\nПроверьте права бота в канале."
                )
            except:
                pass

    async def process_custom_time_posts(self, db: AsyncSession, current_time: str):
        try:
            result = await db.execute(
                select(AutopostSettings, User).join(User).where(
                    and_(
                        AutopostSettings.is_active == True,
                        AutopostSettings.specific_times.like(f'%{current_time}%')
                    )
                )
            )

            settings_with_users = result.all()

            for setting, user in settings_with_users:
                subscription_result = await db.execute(
                    select(Subscription).where(
                        and_(
                            Subscription.user_id == user.id,
                            Subscription.is_active == True,
                            Subscription.expires_at > datetime.utcnow()
                        )
                    )
                )

                if subscription_result.scalar_one_or_none():
                    if self.should_post_now(setting, current_time):
                        await self.create_scheduled_posts(db, setting)

        except Exception as e:
            logging.error(f"Ошибка обработки кастомных постов: {e}")

    async def send_test_post(self, channel_id: str, category: str, style: str) -> bool:
        try:
            news_list = await self.news_service.get_news_by_category(category, limit=1)

            if not news_list:
                return False

            news_item = news_list[0]
            content = await self.content_generator.generate_post(news_item, style)

            test_content = f"🧪 <b>ТЕСТОВЫЙ ПОСТ</b>\n\n{content}\n\n<i>Это тестовое сообщение для проверки настроек</i>"

            await self.send_to_channel(channel_id, test_content)
            return True

        except Exception as e:
            logging.error(f"Ошибка отправки тестового поста: {e}")
            return False

    async def get_news_for_category(self, category: str, limit: int = 1) -> List[NewsItem]:
        try:
            return await self.news_service.get_news_by_category(category, limit)
        except Exception as e:
            logging.error(f"Ошибка получения новостей для категории {category}: {e}")
            return []

    async def format_post(self, news_item: NewsItem, style: str) -> str:
        try:
            return await self.content_generator.generate_post(news_item, style)
        except Exception as e:
            logging.error(f"Ошибка форматирования поста: {e}")
            return "Ошибка форматирования контента"

    async def validate_channel_access(self, channel_id: str) -> dict:
        try:
            chat = await self.bot.get_chat(channel_id)
            chat_member = await self.bot.get_chat_member(channel_id, self.bot.id)

            return {
                'success': True,
                'is_admin': chat_member.status == 'administrator',
                'can_post': getattr(chat_member, 'can_post_messages', False),
                'chat_title': chat.title,
                'chat_type': chat.type
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def get_channel_stats(self, channel_id: str) -> dict:
        try:
            chat = await self.bot.get_chat(channel_id)
            member_count = await self.bot.get_chat_member_count(channel_id)

            return {
                'success': True,
                'title': chat.title,
                'member_count': member_count,
                'type': chat.type,
                'username': getattr(chat, 'username', None)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def send_bulk_posts(self, db: AsyncSession, user_id: int, posts_data: List[dict]):
        try:
            successful = 0
            failed = 0

            for post_data in posts_data:
                try:
                    await self.send_single_post(
                        db=db,
                        user_id=user_id,
                        channel_id=post_data['channel_id'],
                        category=post_data['category'],
                        style=post_data['style']
                    )
                    successful += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    failed += 1
                    logging.error(f"Ошибка массовой отправки поста: {e}")

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"📊 Массовая отправка завершена\n\n✅ Успешно: {successful}\n❌ Ошибок: {failed}"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Ошибка массовой отправки постов: {e}")

    async def schedule_delayed_post(self, user_id: int, channel_id: str, category: str, style: str, delay_minutes: int):
        try:
            from tasks import send_manual_post

            delay_seconds = delay_minutes * 60
            send_manual_post.apply_async(
                args=[user_id, channel_id, category, style],
                countdown=delay_seconds
            )

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ Пост запланирован на отправку через {delay_minutes} минут"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Ошибка планирования отложенного поста: {e}")

    async def get_user_autopost_stats(self, db: AsyncSession, user_id: int) -> dict:
        try:
            result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user_id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            settings = result.scalars().all()

            channels = list(set(setting.channel_id for setting in settings))
            categories = list(set(setting.category for setting in settings))
            total_posts_per_day = sum(setting.posts_per_day for setting in settings)

            return {
                'total_settings': len(settings),
                'unique_channels': len(channels),
                'unique_categories': len(categories),
                'total_posts_per_day': total_posts_per_day,
                'channels': channels,
                'categories': categories
            }

        except Exception as e:
            logging.error(f"Ошибка получения статистики автопостинга: {e}")
            return {
                'total_settings': 0,
                'unique_channels': 0,
                'unique_categories': 0,
                'total_posts_per_day': 0,
                'channels': [],
                'categories': []
            }

    async def pause_user_autoposts(self, db: AsyncSession, user_id: int, pause_hours: int = 24):
        try:
            from sqlalchemy import update

            pause_until = datetime.utcnow() + timedelta(hours=pause_hours)

            await db.execute(
                update(AutopostSettings).where(
                    AutopostSettings.user_id == user_id
                ).values(
                    is_paused=True,
                    pause_until=pause_until
                )
            )

            await db.commit()

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"⏸️ Автопостинг приостановлен на {pause_hours} часов"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Ошибка приостановки автопостинга: {e}")

    async def resume_user_autoposts(self, db: AsyncSession, user_id: int):
        try:
            from sqlalchemy import update

            await db.execute(
                update(AutopostSettings).where(
                    AutopostSettings.user_id == user_id
                ).values(
                    is_paused=False,
                    pause_until=None
                )
            )

            await db.commit()

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="▶️ Автопостинг возобновлен"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Ошибка возобновления автопостинга: {e}")

    async def cleanup_failed_posts(self, db: AsyncSession, hours_old: int = 24):
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)

            logging.info(f"Очистка неудачных постов старше {hours_old} часов")

        except Exception as e:
            logging.error(f"Ошибка очистки неудачных постов: {e}")

    async def get_posting_analytics(self, db: AsyncSession, days: int = 7) -> dict:
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.is_active == True,
                        AutopostSettings.created_at >= start_date
                    )
                )
            )

            settings = result.scalars().all()

            analytics = {
                'period_days': days,
                'total_active_settings': len(settings),
                'channels_count': len(set(s.channel_id for s in settings)),
                'categories_breakdown': {},
                'styles_breakdown': {},
                'posts_per_day_breakdown': {}
            }

            for setting in settings:
                category = setting.category
                style = setting.style
                posts_per_day = setting.posts_per_day

                analytics['categories_breakdown'][category] = analytics['categories_breakdown'].get(category, 0) + 1
                analytics['styles_breakdown'][style] = analytics['styles_breakdown'].get(style, 0) + 1
                analytics['posts_per_day_breakdown'][posts_per_day] = analytics['posts_per_day_breakdown'].get(
                    posts_per_day, 0) + 1

            return analytics

        except Exception as e:
            logging.error(f"Ошибка получения аналитики постинга: {e}")
            return {
                'error': str(e),
                'period_days': days,
                'total_active_settings': 0
            }