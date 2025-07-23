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
            logging.error(f"Error processing autoposts: {e}")

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
            logging.error(f"Error processing user autoposts {user_id}: {e}")

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
                logging.warning(f"No news for category {settings.category}")
                return

            news_item = news_list[0]
            content = await self.content_generator.generate_post(
                news_item,
                settings.style
            )

            await self.send_to_channel(settings.channel_id, content)

        except Exception as e:
            logging.error(f"Error creating posts for setting {settings.id}: {e}")

    async def send_to_channel(self, channel_id: str, content: str):
        try:
            await self.bot.send_message(
                chat_id=channel_id,
                text=content,
                parse_mode='HTML',
                disable_web_page_preview=False
            )

            logging.info(f"Post sent to channel {channel_id}")

        except Exception as e:
            logging.error(f"Error sending to channel {channel_id}: {e}")

    async def send_single_post(self, db: AsyncSession, user_id: int, channel_id: str, category: str, style: str):
        try:
            news_list = await self.news_service.get_news_by_category(category, limit=1)

            if not news_list:
                logging.warning(f"No news for category {category}")
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ No available news for category {category}"
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
                    text=f"✅ Post successfully sent to channel {channel_id}"
                )
            except:
                pass

            logging.info(f"Manual post sent to {channel_id} for user {user_id}")

        except Exception as e:
            logging.error(f"Error sending manual post: {e}")

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Error sending post to channel {channel_id}\n\nCheck bot permissions in the channel."
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
            logging.error(f"Error processing custom time posts: {e}")

    async def send_test_post(self, channel_id: str, category: str, style: str) -> bool:
        try:
            news_list = await self.news_service.get_news_by_category(category, limit=1)

            if not news_list:
                return False

            news_item = news_list[0]
            content = await self.content_generator.generate_post(news_item, style)

            test_content = f"🧪 <b>TEST POST</b>\n\n{content}\n\n<i>This is a test message to verify settings</i>"

            await self.send_to_channel(channel_id, test_content)
            return True

        except Exception as e:
            logging.error(f"Error sending test post: {e}")
            return False

    async def get_news_for_category(self, category: str, limit: int = 1) -> List[NewsItem]:
        try:
            return await self.news_service.get_news_by_category(category, limit)
        except Exception as e:
            logging.error(f"Error getting news for category {category}: {e}")
            return []

    async def format_post(self, news_item: NewsItem, style: str) -> str:
        try:
            return await self.content_generator.generate_post(news_item, style)
        except Exception as e:
            logging.error(f"Error formatting post: {e}")
            return "Post formatting error"

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
                    logging.error(f"Error in bulk post sending: {e}")

            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"📊 Bulk sending completed\n\n✅ Successful: {successful}\n❌ Errors: {failed}"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Error in bulk post sending: {e}")

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
                    text=f"⏰ Post scheduled for {delay_minutes} minutes"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Error scheduling delayed post: {e}")

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
            logging.error(f"Error getting autopost statistics: {e}")
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
                    text=f"⏸️ Autoposting paused for {pause_hours} hours"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Error pausing autoposting: {e}")

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
                    text="▶️ Autoposting resumed"
                )
            except:
                pass

        except Exception as e:
            logging.error(f"Error resuming autoposting: {e}")

    async def cleanup_failed_posts(self, db: AsyncSession, hours_old: int = 24):
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)

            logging.info(f"Cleaning up failed posts older than {hours_old} hours")

        except Exception as e:
            logging.error(f"Error cleaning up failed posts: {e}")

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
            logging.error(f"Error getting posting analytics: {e}")
            return {
                'error': str(e),
                'period_days': days,
                'total_active_settings': 0
            }