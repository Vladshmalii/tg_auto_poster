from celery_app import celery_app
from aiogram import Bot
from database.database import async_session
from services.autopost_service import AutopostService
from config.settings import settings
from database.models import TestPostLimit
from sqlalchemy import delete
from datetime import datetime, timedelta, date, timezone
import asyncio
import logging

logger = logging.getLogger(__name__)

MOSCOW_TZ = timezone(timedelta(hours=3))


def get_category_emoji_name(category):
    category_map = {
        'it': '💻 IT & Tech',
        'crypto': '₿ Криптовалюты',
        'business': '💼 Бизнес',
        'general': '🌍 Общие новости',
        'esports': '🎮 Киберспорт',
        'tech': '📱 Технологии',
        'politics': '🏛️ Политика',
        'science': '🔬 Наука',
        'auto': '🚗 Авто',
        'health': '💊 Здоровье',
        'entertainment': '🎭 Развлечения',
        'sport': '⚽ Спорт'
    }
    return category_map.get(category, f"📄 {category}")


def get_style_emoji_name(style):
    style_map = {
        'formal': '🎩 Формальный',
        'casual': '😎 Разговорный',
        'meme': '🤪 Мемный'
    }
    return style_map.get(style, f"✏️ {style}")


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
            cutoff_date = date.today() - timedelta(days=30)

            result = await db.execute(
                delete(TestPostLimit).where(TestPostLimit.test_date < cutoff_date)
            )

            await db.commit()

            logging.info(f"Удалено {result.rowcount} старых записей тестовых постов")

    except Exception as e:
        logging.error(f"Ошибка очистки старых записей: {e}")


@celery_app.task
def send_manual_post(user_id: int, channel_id: str, category: str, style: str):
    """Отправка поста вручную"""
    asyncio.run(_send_manual_post_async(user_id, channel_id, category, style))


@celery_app.task
def schedule_post_at_time(user_id: int, channel_id: str, category: str, style: str, target_time: str):
    """Запланировать пост на конкретное время (например: 15:23)"""
    asyncio.run(_schedule_post_async(user_id, channel_id, category, style, target_time))


async def _send_manual_post_async(user_id: int, channel_id: str, category: str, style: str):
    logger.info(
        f"Начинаем отправку поста: user_id={user_id}, channel_id={channel_id}, category={category}, style={style}")
    bot = Bot(token=settings.BOT_TOKEN)
    autopost_service = AutopostService(bot)

    try:
        async with async_session() as db:
            # Проверяем лимит постов пользователя перед отправкой
            from database.models import User, PostLog
            from sqlalchemy import select, func, and_
            from datetime import date

            # Получаем пользователя
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return

            # Проверяем количество постов за сегодня
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

            # Максимум 3 поста в день
            if posts_today >= 3:
                logger.warning(f"Пользователь {user_id} достиг лимита постов на сегодня: {posts_today}/3")

                # Уведомляем пользователя о превышении лимита
                telegram_id = user.telegram_id
                if telegram_id:
                    limit_message = (
                        f"❌ <b>Лимит постов исчерпан</b>\n\n"
                        f"📊 Сегодня отправлено: {posts_today}/3 постов\n"
                        f"📢 Канал: {channel_id}\n"
                        f"⏰ Попробуйте завтра или дождитесь автопостинга\n\n"
                        f"💡 Лимит обновляется каждый день в 00:00"
                    )

                    try:
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=limit_message,
                            parse_mode='HTML'
                        )
                        logger.info(f"Уведомление о лимите отправлено пользователю {telegram_id}")
                    except Exception as notify_error:
                        logger.warning(
                            f"Не удалось отправить уведомление о лимите пользователю {telegram_id}: {notify_error}")

                return

            # Если лимит не превышен, отправляем пост
            await autopost_service.send_single_post(
                db=db,
                user_id=user_id,
                channel_id=channel_id,
                category=category,
                style=style
            )
        logger.info("Пост успешно отправлен")

        # Получаем telegram_id пользователя из базы данных
        async with async_session() as db:
            from database.models import User
            from sqlalchemy import select

            user_result = await db.execute(
                select(User.telegram_id).where(User.id == user_id)
            )
            telegram_id = user_result.scalar()

            if telegram_id:
                # Получаем обновленное количество постов
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

                # Отправляем уведомление пользователю об успешной отправке
                try:
                    success_message = (
                        f"✅ <b>Пост успешно отправлен!</b>\n\n"
                        f"📢 Канал: {channel_id}\n"
                        f"📂 Категория: {get_category_emoji_name(category)}\n"
                        f"🎨 Стиль: {get_style_emoji_name(style)}\n"
                        f"⏰ Время: {datetime.now(MOSCOW_TZ).strftime('%H:%M:%S')}\n"
                        f"📊 Постов сегодня: {posts_after}/3"
                    )

                    await bot.send_message(
                        chat_id=telegram_id,
                        text=success_message,
                        parse_mode='HTML'
                    )
                    logger.info(f"Уведомление об успешной отправке отправлено пользователю {telegram_id}")

                except Exception as notify_error:
                    logger.warning(f"Не удалось отправить уведомление пользователю {telegram_id}: {notify_error}")
            else:
                logger.warning(f"Не найден telegram_id для пользователя с ID {user_id}")

    except Exception as e:
        logger.error(f"Ошибка при отправке поста: {e}", exc_info=True)

        # Получаем telegram_id для отправки уведомления об ошибке
        try:
            async with async_session() as db:
                from database.models import User
                from sqlalchemy import select

                user_result = await db.execute(
                    select(User.telegram_id).where(User.id == user_id)
                )
                telegram_id = user_result.scalar()

                if telegram_id:
                    error_message = (
                        f"❌ <b>Ошибка при отправке поста</b>\n\n"
                        f"📢 Канал: {channel_id}\n"
                        f"📂 Категория: {get_category_emoji_name(category)}\n"
                        f"🎨 Стиль: {get_style_emoji_name(style)}\n"
                        f"⚠️ Ошибка: {str(e)[:200]}..."
                    )

                    await bot.send_message(
                        chat_id=telegram_id,
                        text=error_message,
                        parse_mode='HTML'
                    )
                    logger.info(f"Уведомление об ошибке отправлено пользователю {telegram_id}")

        except Exception as notify_error:
            logger.warning(f"Не удалось отправить уведомление об ошибке: {notify_error}")

    finally:
        await bot.session.close()


async def _schedule_post_async(user_id: int, channel_id: str, category: str, style: str, target_time: str):
    """Запланированная отправка поста"""
    try:
        # Используем московское время
        now = datetime.now(MOSCOW_TZ)
        target_hour, target_minute = map(int, target_time.split(':'))

        # Создаем время в московской зоне
        target_datetime = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Если время уже прошло сегодня, планируем на завтра
        if target_datetime <= now:
            target_datetime += timedelta(days=1)

        # Вычисляем количество секунд до выполнения
        countdown_seconds = int((target_datetime - now).total_seconds())

        logging.info(f"Планируем отправку на {target_datetime} (МСК), текущее время: {now} (МСК)")
        logging.info(f"Задача будет выполнена через {countdown_seconds} секунд")

        # Используем countdown вместо eta для надежности
        result = send_manual_post.apply_async(
            args=[user_id, channel_id, category, style],
            countdown=countdown_seconds
        )

        logging.info(f"Задача запланирована с ID: {result.id}, countdown: {countdown_seconds} сек")

    except Exception as e:
        logging.error(f"Ошибка планирования задачи: {e}")
        # Fallback - отправить через 5 минут
        send_manual_post.apply_async(
            args=[user_id, channel_id, category, style],
            countdown=300
        )


@celery_app.task
def send_scheduled_posts():
    """Отправка запланированных постов (проверка каждые 5 минут)"""
    asyncio.run(_send_scheduled_posts_async())


async def _send_scheduled_posts_async():
    """Проверка и отправка постов по точному времени"""
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        autopost_service = AutopostService(bot)

        # Используем московское время
        current_time = datetime.now(MOSCOW_TZ).strftime('%H:%M')

        async with async_session() as db:
            await autopost_service.process_custom_time_posts(db, current_time)

        await bot.session.close()

    except Exception as e:
        logging.error(f"Ошибка обработки запланированных постов: {e}")


@celery_app.task
def send_broadcast_message(user_ids: list, message_text: str):
    """Массовая рассылка сообщений"""
    asyncio.run(_send_broadcast_async(user_ids, message_text))


async def _send_broadcast_async(user_ids: list, message_text: str):
    """Асинхронная массовая рассылка"""
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
            logging.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    logging.info(f"Рассылка завершена: {successful} успешно, {failed} ошибок")
    await bot.session.close()


@celery_app.task
def generate_analytics_report(period_days: int = 7):
    """Генерация аналитического отчета"""
    asyncio.run(_generate_analytics_async(period_days))


async def _generate_analytics_async(period_days: int):
    """Асинхронная генерация аналитики"""
    try:
        async with async_session() as db:
            from datetime import datetime, timedelta
            from sqlalchemy import select, func, and_
            from database.models import User, Subscription, Transaction, AutopostSettings

            # Используем московское время
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
                f"Аналитика за {period_days} дней: "
                f"Новых пользователей: {new_users}, "
                f"Активных подписок: {active_subs}, "
                f"Доход: {total_revenue} звезд, "
                f"Активных автопостов: {active_autoposts}"
            )

    except Exception as e:
        logging.error(f"Ошибка генерации аналитики: {e}")


@celery_app.task
def check_subscription_expiry():
    """Проверка истекающих подписок и уведомления"""
    asyncio.run(_check_subscription_expiry_async())


async def _check_subscription_expiry_async():
    """Проверка и уведомление об истекающих подписках"""
    try:
        bot = Bot(token=settings.BOT_TOKEN)

        async with async_session() as db:
            from database.models import User, Subscription
            from sqlalchemy import select, and_

            # Используем московское время
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
                            f"⏰ <b>Подписка истекает!</b>\n\n"
                            f"У вас осталось: {hours_left} часов\n"
                            f"Продлите подписку, чтобы не потерять доступ к автопостингу\n\n"
                            f"💎 /buy - продлить подписку"
                        )

                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message,
                            parse_mode='HTML'
                        )

                except Exception as e:
                    logging.warning(f"Не удалось уведомить пользователя {user.telegram_id}: {e}")

        await bot.session.close()

    except Exception as e:
        logging.error(f"Ошибка проверки истекающих подписок: {e}")


@celery_app.task
def cleanup_expired_subscriptions():
    """Деактивация истекших подписок"""
    asyncio.run(_cleanup_expired_subscriptions_async())


async def _cleanup_expired_subscriptions_async():
    """Деактивация истекших подписок"""
    try:
        async with async_session() as db:
            from database.models import Subscription, AutopostSettings
            from sqlalchemy import select, and_, update

            # Используем московское время
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
                logging.info(f"Деактивировано {deactivated_count} истекших подписок")

    except Exception as e:
        logging.error(f"Ошибка деактивации подписок: {e}")


@celery_app.task
def backup_database():
    """Создание резервной копии важных данных"""
    asyncio.run(_backup_database_async())


async def _backup_database_async():
    """Создание бэкапа базы данных"""
    try:
        async with async_session() as db:
            from database.models import User, Subscription, Transaction
            from sqlalchemy import select
            import json
            import os

            # Используем московское время
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

            # Удаляем старые бэкапы (старше 30 дней)
            cutoff_time = now - timedelta(days=30)
            for filename in os.listdir(backup_dir):
                if filename.startswith('backup_') and filename.endswith('.json'):
                    file_path = os.path.join(backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    file_time = MOSCOW_TZ.localize(file_time)
                    if file_time < cutoff_time:
                        os.remove(file_path)

            logging.info(f"Бэкап создан: {backup_path}")

    except Exception as e:
        logging.error(f"Ошибка создания бэкапа: {e}")


@celery_app.task
def health_check():
    """Проверка работоспособности системы"""
    asyncio.run(_health_check_async())


async def _health_check_async():
    """Проверка состояния системы"""
    try:
        bot = Bot(token=settings.BOT_TOKEN)

        # Проверка подключения к базе данных
        async with async_session() as db:
            from sqlalchemy import text
            result = await db.execute(text("SELECT 1"))
            db_status = "OK" if result.scalar() == 1 else "ERROR"

        # Проверка Telegram API
        try:
            me = await bot.get_me()
            bot_status = "OK" if me else "ERROR"
        except Exception:
            bot_status = "ERROR"

        await bot.session.close()

        logging.info(f"Health check: DB={db_status}, Bot={bot_status}")

        return {
            'database': db_status,
            'telegram_bot': bot_status,
            'timestamp': datetime.now(MOSCOW_TZ).isoformat()
        }

    except Exception as e:
        logging.error(f"Ошибка health check: {e}")
        return {
            'status': 'ERROR',
            'error': str(e),
            'timestamp': datetime.now(MOSCOW_TZ).isoformat()
        }