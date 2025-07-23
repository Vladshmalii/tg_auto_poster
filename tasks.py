import asyncio
import logging
import os
import json
from datetime import datetime, timedelta, date, timezone

from celery_app import celery_app
from aiogram import Bot
from database.database import async_session
from services.autopost_service import AutopostService
from config.settings import settings
from database.models import TestPostLimit
from sqlalchemy import delete

logger = logging.getLogger(__name__)

MOSCOW_TZ = timezone(timedelta(hours=3))


def get_category_emoji_name(category):
    category_map = {
        'it': '💻 IT & Tech',
        'crypto': '₿ Cryptocurrency',
        'business': '💼 Business',
        'general': '🌍 General News',
        'esports': '🎮 Esports',
        'tech': '📱 Technology',
        'politics': '🏛️ Politics',
        'science': '🔬 Science',
        'auto': '🚗 Auto',
        'health': '💊 Health',
        'entertainment': '🎭 Entertainment',
        'sport': '⚽ Sport'
    }
    return category_map.get(category, f"📄 {category}")


def get_style_emoji_name(style):
    style_map = {
        'formal': '🎩 Formal',
        'casual': '😎 Casual',
        'meme': '🤪 Meme'
    }
    return style_map.get(style, f"✏️ {style}")


@celery_app.task
def process_autoposts():
    try:
        return asyncio.run(_process_autoposts_async())
    except Exception as e:
        logger.error(f"Error in process_autoposts: {e}", exc_info=True)
        raise


async def _process_autoposts_async():
    bot = None
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        autopost_service = AutopostService(bot)

        async with async_session() as db:
            await autopost_service.process_autoposts(db)
    finally:
        if bot:
            await bot.session.close()


@celery_app.task
def cleanup_old_test_post_limits():
    try:
        return asyncio.run(_cleanup_old_test_post_limits_async())
    except Exception as e:
        logger.error(f"Error in cleanup_old_test_post_limits: {e}", exc_info=True)
        raise


async def _cleanup_old_test_post_limits_async():
    try:
        async with async_session() as db:
            cutoff_date = date.today() - timedelta(days=30)

            result = await db.execute(
                delete(TestPostLimit).where(TestPostLimit.test_date < cutoff_date)
            )

            await db.commit()
            logging.info(f"Deleted {result.rowcount} old test post records")

    except Exception as e:
        logging.error(f"Error cleaning old records: {e}")
        raise


@celery_app.task
def send_manual_post(user_id: int, channel_id: str, category: str, style: str):
    try:
        return asyncio.run(_send_manual_post_async(user_id, channel_id, category, style))
    except Exception as e:
        logger.error(f"Error in send_manual_post: {e}", exc_info=True)
        raise


@celery_app.task
def schedule_post_at_time(user_id: int, channel_id: str, category: str, style: str, target_time: str):
    try:
        return asyncio.run(_schedule_post_async(user_id, channel_id, category, style, target_time))
    except Exception as e:
        logger.error(f"Error in schedule_post_at_time: {e}", exc_info=True)
        raise


async def _send_manual_post_async(user_id: int, channel_id: str, category: str, style: str):
    bot = None
    try:
        logger.info(
            f"Starting post send: user_id={user_id}, channel_id={channel_id}, category={category}, style={style}")

        bot = Bot(token=settings.BOT_TOKEN)
        autopost_service = AutopostService(bot)

        async with async_session() as db:
            from database.models import User, PostLog
            from sqlalchemy import select, func, and_
            from datetime import date

            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.error(f"User with ID {user_id} not found")
                return

            today = date.today()
            posts_today_result = await db.execute(
                select(func.count(PostLog.id)).where(
                    and_(
                        PostLog.user_id == user_id,
                        PostLog.channel_id == channel_id,
                        PostLog.created_at >= today
                    )
                )
            )
            posts_today = posts_today_result.scalar() or 0

            if posts_today >= 3:
                logger.warning(f"User {user_id} reached daily post limit: {posts_today}/3")

                telegram_id = user.telegram_id
                if telegram_id:
                    limit_message = (
                        f"❌ <b>Post limit exceeded</b>\n\n"
                        f"📊 Today sent: {posts_today}/3 posts\n"
                        f"📢 Channel: {channel_id}\n"
                        f"⏰ Try tomorrow or wait for autoposting\n\n"
                        f"💡 Limit resets every day at 00:00"
                    )

                    try:
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=limit_message,
                            parse_mode='HTML'
                        )
                        logger.info(f"Limit notification sent to user {telegram_id}")
                    except Exception as notify_error:
                        logger.warning(f"Failed to send limit notification to user {telegram_id}: {notify_error}")

                return

            await autopost_service.send_single_post(
                db=db,
                user_id=user_id,
                channel_id=channel_id,
                category=category,
                style=style
            )

        logger.info("Post sent successfully")

        async with async_session() as db:
            from database.models import User
            from sqlalchemy import select

            user_result = await db.execute(
                select(User.telegram_id).where(User.id == user_id)
            )
            telegram_id = user_result.scalar()

            if telegram_id:
                posts_today_result = await db.execute(
                    select(func.count(PostLog.id)).where(
                        and_(
                            PostLog.user_id == user_id,
                            PostLog.channel_id == channel_id,
                            PostLog.created_at >= today
                        )
                    )
                )
                posts_after = posts_today_result.scalar() or 0

                try:
                    success_message = (
                        f"✅ <b>Post sent successfully!</b>\n\n"
                        f"📢 Channel: {channel_id}\n"
                        f"📂 Category: {get_category_emoji_name(category)}\n"
                        f"🎨 Style: {get_style_emoji_name(style)}\n"
                        f"⏰ Time: {datetime.now(MOSCOW_TZ).strftime('%H:%M:%S')}\n"
                        f"📊 Posts today: {posts_after}/3"
                    )

                    await bot.send_message(
                        chat_id=telegram_id,
                        text=success_message,
                        parse_mode='HTML'
                    )
                    logger.info(f"Success notification sent to user {telegram_id}")

                except Exception as notify_error:
                    logger.warning(f"Failed to send success notification to user {telegram_id}: {notify_error}")
            else:
                logger.warning(f"Telegram ID not found for user with ID {user_id}")

    except Exception as e:
        logger.error(f"Error sending post: {e}", exc_info=True)

        try:
            if bot:
                async with async_session() as db:
                    from database.models import User
                    from sqlalchemy import select

                    user_result = await db.execute(
                        select(User.telegram_id).where(User.id == user_id)
                    )
                    telegram_id = user_result.scalar()

                    if telegram_id:
                        error_message = (
                            f"❌ <b>Error sending post</b>\n\n"
                            f"📢 Channel: {channel_id}\n"
                            f"📂 Category: {get_category_emoji_name(category)}\n"
                            f"🎨 Style: {get_style_emoji_name(style)}\n"
                            f"⚠️ Error: {str(e)[:200]}..."
                        )

                        await bot.send_message(
                            chat_id=telegram_id,
                            text=error_message,
                            parse_mode='HTML'
                        )
                        logger.info(f"Error notification sent to user {telegram_id}")

        except Exception as notify_error:
            logger.warning(f"Failed to send error notification: {notify_error}")

    finally:
        if bot:
            await bot.session.close()


async def _schedule_post_async(user_id: int, channel_id: str, category: str, style: str, target_time: str):
    try:
        now = datetime.now(MOSCOW_TZ)
        target_hour, target_minute = map(int, target_time.split(':'))

        target_datetime = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        if target_datetime <= now:
            target_datetime += timedelta(days=1)

        countdown_seconds = int((target_datetime - now).total_seconds())

        logging.info(f"Scheduling send at {target_datetime} (MSK), current time: {now} (MSK)")
        logging.info(f"Task will execute in {countdown_seconds} seconds")

        result = send_manual_post.apply_async(
            args=[user_id, channel_id, category, style],
            countdown=countdown_seconds
        )

        logging.info(f"Task scheduled with ID: {result.id}, countdown: {countdown_seconds} sec")

    except Exception as e:
        logging.error(f"Error scheduling task: {e}")
        send_manual_post.apply_async(
            args=[user_id, channel_id, category, style],
            countdown=300
        )


@celery_app.task
def send_scheduled_posts():
    try:
        return asyncio.run(_send_scheduled_posts_async())
    except Exception as e:
        logger.error(f"Error in send_scheduled_posts: {e}", exc_info=True)
        raise


async def _send_scheduled_posts_async():
    bot = None
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        autopost_service = AutopostService(bot)

        current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M')

        async with async_session() as db:
            await autopost_service.process_custom_time_posts(db, current_time)

    except Exception as e:
        logging.error(f"Error processing scheduled posts: {e}")
        raise
    finally:
        if bot:
            await bot.session.close()


@celery_app.task
def send_broadcast_message(user_ids: list, message_text: str):
    try:
        return asyncio.run(_send_broadcast_async(user_ids, message_text))
    except Exception as e:
        logger.error(f"Error in send_broadcast_message: {e}", exc_info=True)
        raise


async def _send_broadcast_async(user_ids: list, message_text: str):
    bot = None
    try:
        bot = Bot(token=settings.BOT_TOKEN)

        successful = 0
        failed = 0

        for user_id in user_ids:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode='HTML'
                )
                successful += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed += 1
                logging.warning(f"Failed to send message to user {user_id}: {e}")

        logging.info(f"Broadcast completed: {successful} successful, {failed} errors")
    finally:
        if bot:
            await bot.session.close()


@celery_app.task
def generate_analytics_report(period_days: int = 7):
    try:
        return asyncio.run(_generate_analytics_async(period_days))
    except Exception as e:
        logger.error(f"Error in generate_analytics_report: {e}", exc_info=True)
        raise


async def _generate_analytics_async(period_days: int):
    try:
        async with async_session() as db:
            from datetime import datetime, timedelta
            from sqlalchemy import select, func, and_
            from database.models import User, Subscription, Transaction, AutopostSettings

            start_date = datetime.now(MOSCOW_TZ) - timedelta(days=period_days)

            new_users_result = await db.execute(
                select(func.count(User.id)).where(User.created_at >= start_date)
            )
            new_users = new_users_result.scalar() or 0

            active_subs_result = await db.execute(
                select(func.count(Subscription.id)).where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.now(MOSCOW_TZ)
                    )
                )
            )
            active_subs = active_subs_result.scalar() or 0

            total_revenue_result = await db.execute(
                select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.status == 'completed',
                        Transaction.created_at >= start_date
                    )
                )
            )
            total_revenue = total_revenue_result.scalar() or 0

            active_autoposts_result = await db.execute(
                select(func.count(AutopostSettings.id.distinct())).where(
                    AutopostSettings.is_active == True
                )
            )
            active_autoposts = active_autoposts_result.scalar() or 0

            logging.info(
                f"Analytics for {period_days} days: "
                f"New users: {new_users}, "
                f"Active subscriptions: {active_subs}, "
                f"Revenue: {total_revenue} stars, "
                f"Active autoposts: {active_autoposts}"
            )

    except Exception as e:
        logging.error(f"Error generating analytics: {e}")
        raise


@celery_app.task
def check_subscription_expiry():
    try:
        return asyncio.run(_check_subscription_expiry_async())
    except Exception as e:
        logger.error(f"Error in check_subscription_expiry: {e}", exc_info=True)
        raise


async def _check_subscription_expiry_async():
    bot = None
    try:
        bot = Bot(token=settings.BOT_TOKEN)

        async with async_session() as db:
            from database.models import User, Subscription
            from sqlalchemy import select, and_

            now = datetime.now(MOSCOW_TZ)
            tomorrow = now + timedelta(days=1)

            expiring_subs_result = await db.execute(
                select(Subscription, User).join(User).where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.expires_at <= tomorrow,
                        Subscription.expires_at > now
                    )
                )
            )
            expiring_subs = expiring_subs_result.all()

            for subscription, user in expiring_subs:
                try:
                    hours_left = int((subscription.expires_at - now).total_seconds() / 3600)

                    if hours_left <= 24:
                        message = (
                            f"⏰ <b>Subscription expiring!</b>\n\n"
                            f"Time left: {hours_left} hours\n"
                            f"Renew your subscription to keep access to autoposting\n\n"
                            f"💎 /buy - renew subscription"
                        )

                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message,
                            parse_mode='HTML'
                        )

                except Exception as e:
                    logging.warning(f"Failed to notify user {user.telegram_id}: {e}")

    except Exception as e:
        logging.error(f"Error checking subscription expiry: {e}")
        raise
    finally:
        if bot:
            await bot.session.close()


@celery_app.task
def cleanup_expired_subscriptions():
    try:
        return asyncio.run(_cleanup_expired_subscriptions_async())
    except Exception as e:
        logger.error(f"Error in cleanup_expired_subscriptions: {e}", exc_info=True)
        raise


async def _cleanup_expired_subscriptions_async():
    try:
        async with async_session() as db:
            from database.models import Subscription, AutopostSettings
            from sqlalchemy import select, and_, update

            now = datetime.now(MOSCOW_TZ)

            expired_subs_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.expires_at <= now
                    )
                )
            )
            expired_subs = expired_subs_result.scalars().all()

            deactivated_count = 0

            for subscription in expired_subs:
                subscription.is_active = False

                await db.execute(
                    update(AutopostSettings).where(
                        AutopostSettings.user_id == subscription.user_id
                    ).values(is_active=False)
                )

                deactivated_count += 1

            await db.commit()

            if deactivated_count > 0:
                logging.info(f"Deactivated {deactivated_count} expired subscriptions")

    except Exception as e:
        logging.error(f"Error deactivating subscriptions: {e}")
        raise


@celery_app.task
def backup_database():
    try:
        return asyncio.run(_backup_database_async())
    except Exception as e:
        logger.error(f"Error in backup_database: {e}", exc_info=True)
        raise


async def _backup_database_async():
    try:
        async with async_session() as db:
            from database.models import User, Subscription, Transaction
            from sqlalchemy import select

            now = datetime.now(MOSCOW_TZ)

            backup_data = {
                'timestamp': now.isoformat(),
                'users': [],
                'subscriptions': [],
                'transactions': []
            }

            users_result = await db.execute(select(User))
            users = users_result.scalars().all()

            for user in users:
                backup_data['users'].append({
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'language': user.language,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                })

            subs_result = await db.execute(select(Subscription))
            subscriptions = subs_result.scalars().all()

            for sub in subscriptions:
                backup_data['subscriptions'].append({
                    'user_id': sub.user_id,
                    'plan_type': sub.plan_type,
                    'is_active': sub.is_active,
                    'created_at': sub.created_at.isoformat() if sub.created_at else None,
                    'expires_at': sub.expires_at.isoformat() if sub.expires_at else None
                })

            trans_result = await db.execute(select(Transaction))
            transactions = trans_result.scalars().all()

            for trans in transactions:
                backup_data['transactions'].append({
                    'user_id': trans.user_id,
                    'amount': trans.amount,
                    'status': trans.status,
                    'external_id': trans.external_id,
                    'created_at': trans.created_at.isoformat() if trans.created_at else None
                })

            backup_dir = '/app/backups'
            os.makedirs(backup_dir, exist_ok=True)

            backup_filename = f"backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(backup_dir, backup_filename)

            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            cutoff_time = now - timedelta(days=30)
            for filename in os.listdir(backup_dir):
                if filename.startswith('backup_') and filename.endswith('.json'):
                    file_path = os.path.join(backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    file_time = MOSCOW_TZ.localize(file_time)
                    if file_time < cutoff_time:
                        os.remove(file_path)

            logging.info(f"Backup created: {backup_path}")

    except Exception as e:
        logging.error(f"Error creating backup: {e}")
        raise


@celery_app.task
def health_check():
    try:
        return asyncio.run(_health_check_async())
    except Exception as e:
        logger.error(f"Error in health_check: {e}", exc_info=True)
        raise


async def _health_check_async():
    bot = None
    try:
        bot = Bot(token=settings.BOT_TOKEN)

        async with async_session() as db:
            from sqlalchemy import text
            result = await db.execute(text("SELECT 1"))
            db_status = "OK" if result.scalar() == 1 else "ERROR"

        try:
            me = await bot.get_me()
            bot_status = "OK" if me else "ERROR"
        except Exception:
            bot_status = "ERROR"

        logging.info(f"Health check: DB={db_status}, Bot={bot_status}")

        return {
            'database': db_status,
            'telegram_bot': bot_status,
            'timestamp': datetime.now(MOSCOW_TZ).isoformat()
        }

    except Exception as e:
        logging.error(f"Health check error: {e}")
        return {
            'status': 'ERROR',
            'error': str(e),
            'timestamp': datetime.now(MOSCOW_TZ).isoformat()
        }
    finally:
        if bot:
            await bot.session.close()