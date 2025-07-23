from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import User, TestPostLimit, Subscription
from typing import Optional, Tuple
import logging


class TestPostService:

    @staticmethod
    async def can_create_test_post(db: AsyncSession, user_telegram_id: int) -> Tuple[bool, str]:
        try:
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False, "User not found"

            subscription_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                )
            )
            active_subscription = subscription_result.scalar_one_or_none()

            if active_subscription:
                return True, ""

            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

            test_post_result = await db.execute(
                select(TestPostLimit).where(
                    and_(
                        TestPostLimit.user_id == user.id,
                        TestPostLimit.created_at > twenty_four_hours_ago
                    )
                ).order_by(TestPostLimit.created_at.desc())
            )
            last_test_post = test_post_result.scalar_one_or_none()

            if last_test_post:
                next_available = last_test_post.created_at + timedelta(hours=24)
                time_left = next_available - datetime.utcnow()

                if time_left.total_seconds() > 0:
                    hours = int(time_left.total_seconds() // 3600)
                    minutes = int((time_left.total_seconds() % 3600) // 60)

                    return False, f"⏰ You have already used your test post!\n\nNext test will be available in {hours}h {minutes}m.\n\n💎 Want more posts? Purchase a subscription!"

            return True, ""

        except Exception as e:
            logging.error(f"Error checking test post limit: {e}")
            return False, "Error checking limit"

    @staticmethod
    async def record_test_post(db: AsyncSession, user_telegram_id: int,
                               channel_username: str, category: str, style: str):
        try:
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if user:
                test_post_limit = TestPostLimit(
                    user_id=user.id,
                    test_date=date.today(),
                    channel_username=channel_username,
                    category=category,
                    style=style,
                    created_at=datetime.utcnow()
                )

                db.add(test_post_limit)
                await db.commit()

                logging.info(f"Test post recorded for user {user_telegram_id}")

        except Exception as e:
            logging.error(f"Error recording test post: {e}")
            await db.rollback()

    @staticmethod
    async def get_last_test_post_info(db: AsyncSession, user_telegram_id: int) -> Optional[dict]:
        try:
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return None

            test_post_result = await db.execute(
                select(TestPostLimit).where(
                    TestPostLimit.user_id == user.id
                ).order_by(TestPostLimit.created_at.desc())
            )
            last_test_post = test_post_result.scalar_one_or_none()

            if last_test_post:
                return {
                    'created_at': last_test_post.created_at,
                    'channel_username': last_test_post.channel_username,
                    'category': last_test_post.category,
                    'style': last_test_post.style,
                    'test_date': last_test_post.test_date
                }

            return None

        except Exception as e:
            logging.error(f"Error getting test post information: {e}")
            return None