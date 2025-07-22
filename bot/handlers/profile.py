from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from datetime import datetime, timedelta, date

from tasks import send_manual_post, schedule_post_at_time
from database.models import User, Subscription, Transaction, AutopostSettings, PostLog
from database.database import get_db
from bot.keyboards import get_profile_keyboard, get_main_menu_keyboard
from bot.states import UserStates

import json
import logging

router = Router()

async def send_text_only(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.delete()
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение: {e}")
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


def format_subscription_status(subscription):
    if not subscription:
        return "❌ Подписки нет"

    if not subscription.is_active:
        return "🔴 Подписка неактивна"

    expires_at = subscription.expires_at
    now = datetime.utcnow()

    if expires_at <= now:
        return "⏰ Подписка истекла"

    time_left = expires_at - now
    days_left = time_left.days
    hours_left = time_left.seconds // 3600

    if days_left > 0:
        return f"🟢 Активна ({days_left} дн.)"
    elif hours_left > 0:
        return f"🟡 Активна ({hours_left} ч.)"
    else:
        return "🔴 Истекает сегодня"


def get_subscription_emoji(plan_type):
    emoji_map = {
        7: "🥉",
        14: "🥈",
        30: "🥇"
    }
    return emoji_map.get(plan_type, "📦")


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


def get_schedule_times(frequency: int) -> str:
    schedule_map = {
        1: "09:00",
        2: "09:00,21:00",
        3: "09:00,15:00,21:00"
    }
    return schedule_map.get(frequency, "09:00")


def format_autopost_summary(data: dict) -> str:
    channels = data.get('channels', [])
    categories = data.get('categories', [])
    style = data.get('style', '')
    frequency = data.get('frequency', 1)

    channels_text = '\n'.join([f"• {ch}" for ch in channels]) if channels else "❌ Не выбраны"

    category_names = [get_category_emoji_name(cat) for cat in categories]
    categories_text = '\n'.join([f"• {name}" for name in category_names]) if categories else "❌ Не выбраны"

    style_text = get_style_emoji_name(style) if style else "❌ Не выбран"

    schedule_names = {
        1: "1 раз в день (09:00)",
        2: "2 раза в день (09:00, 21:00)",
        3: "3 раза в день (09:00, 15:00, 21:00)"
    }
    schedule_text = schedule_names.get(frequency, "❌ Не настроено")

    return f"""📋 <b>Сводка настроек автопостинга</b>

📺 <b>Каналы:</b>
{channels_text}

📂 <b>Категории:</b>
{categories_text}

🎨 <b>Стиль:</b> {style_text}

⏰ <b>Расписание:</b> {schedule_text}

💡 Проверьте настройки перед сохранением"""


async def get_user_post_stats(db: AsyncSession, user_id: int, channel_id: str = None):
    """Получить статистику постов пользователя за сегодня"""
    today = date.today()

    query = select(func.count(PostLog.id)).where(
        and_(
            PostLog.user_id == user_id,
            PostLog.created_at >= today
        )
    )

    if channel_id:
        query = query.where(PostLog.channel_id == channel_id)

    result = await db.execute(query)
    posts_today = result.scalar() or 0

    return posts_today


@router.callback_query(F.data == "my_profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.viewing_profile)

    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await send_text_only(
                    callback,
                    "❌ Пользователь не найден в системе",
                    get_main_menu_keyboard()
                )
                await callback.answer()
                return

            subscription_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True
                    )
                ).order_by(Subscription.expires_at.desc())
            )
            active_subscription = subscription_result.first()
            subscription = active_subscription[0] if active_subscription else None

            history_result = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id
                ).order_by(Subscription.created_at.desc()).limit(5)
            )
            subscription_history = history_result.scalars().all()

            payments_result = await db.execute(
                select(Transaction).where(
                    and_(
                        Transaction.user_id == user.id,
                        Transaction.status == 'completed'
                    )
                ).order_by(Transaction.created_at.desc())
            )
            payments = payments_result.scalars().all()

            # Получаем статистику постов за сегодня
            posts_today = await get_user_post_stats(db, user.id)

            total_spent = sum(payment.amount for payment in payments)
            total_payments = len(payments)
            last_payment = payments[0] if payments else None

            profile_text = (
                f"👤 <b>Мой профиль</b>\n\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Не указан'}\n"
                f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            )

            if subscription:
                emoji = get_subscription_emoji(subscription.plan_type)
                status = format_subscription_status(subscription)
                expires_date = subscription.expires_at.strftime('%d.%m.%Y %H:%M')

                profile_text += (
                    f"📦 <b>Текущая подписка</b>\n"
                    f"{emoji} План: {subscription.plan_type} дней\n"
                    f"📊 Статус: {status}\n"
                    f"⏰ Действует до: {expires_date}\n\n"
                )
            else:
                profile_text += (
                    f"📦 <b>Подписка</b>\n"
                    f"❌ Активной подписки нет\n"
                    f"💡 Приобретите подписку для доступа к функциям\n\n"
                )

            # Добавляем статистику постов
            profile_text += (
                f"📊 <b>Статистика постов</b>\n"
                f"📈 Сегодня отправлено: {posts_today}/3\n"
                f"⏰ Лимит обновляется в 00:00\n\n"
            )

            if payments:
                last_payment_date = last_payment.created_at.strftime('%d.%m.%Y')
                profile_text += (
                    f"💳 <b>Статистика платежей</b>\n"
                    f"💰 Всего потрачено: {total_spent} ⭐\n"
                    f"📊 Количество покупок: {total_payments}\n"
                    f"📅 Последний платеж: {last_payment_date}\n\n"
                )
            else:
                profile_text += (
                    f"🎁 <b>Подарочные подписки</b>\n"
                    f"💡 У вас есть возможность получить подарочную подписку!\n"
                    f"🎯 Участвуйте в розыгрышах и акциях\n"
                    f"🔔 Следите за новостями в нашем канале\n\n"
                )

            if subscription_history:
                profile_text += f"📜 <b>История подписок</b>\n"
                for i, sub in enumerate(subscription_history[:3], 1):
                    emoji = get_subscription_emoji(sub.plan_type)
                    status_emoji = "🟢" if sub.is_active else "🔴"
                    created_date = sub.created_at.strftime('%d.%m.%Y')
                    profile_text += f"{status_emoji} {emoji} {sub.plan_type}д - {created_date}\n"

                if len(subscription_history) > 3:
                    profile_text += f"... и еще {len(subscription_history) - 3}\n"

            await send_text_only(callback, profile_text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения профиля: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при загрузке профиля",
            get_main_menu_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "manual_post")
async def show_manual_post_menu(callback: CallbackQuery, state: FSMContext):
    """Меню ручной отправки постов"""
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            subscription_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                )
            )
            active_subscription = subscription_result.first()

            if not active_subscription:
                text = (
                    "📤 <b>Ручная отправка постов</b>\n\n"
                    "❌ <b>Требуется активная подписка</b>\n\n"
                    "Для ручной отправки постов необходима активная подписка.\n\n"
                    "💎 Приобретите подписку для доступа к функции"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            autopost_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = autopost_result.scalar_one_or_none()

            if not setting:
                text = (
                    "📤 <b>Ручная отправка постов</b>\n\n"
                    "❌ <b>Автопостинг не настроен</b>\n\n"
                    "Сначала настройте автопостинг в разделе 'Настройки постинга'.\n\n"
                    "💡 После настройки здесь появятся функции ручной отправки"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            # Получаем статистику постов за сегодня для этого канала
            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            text = (
                "📤 <b>Ручная отправка постов</b>\n\n"
                "Выберите действие:\n\n"
                "🚀 <b>Отправить сейчас</b> - немедленная отправка поста\n"
                "⏰ <b>Запланировать</b> - отправка в указанное время\n\n"
                f"📺 <b>Канал:</b> {setting.channel_id}\n"
                f"📂 <b>Категория:</b> {get_category_emoji_name(setting.category)}\n"
                f"🎨 <b>Стиль:</b> {get_style_emoji_name(setting.style)}\n\n"
                f"📊 <b>Лимит постов:</b> {posts_today}/3 сегодня\n"
            )

            if posts_today >= 3:
                text += "⚠️ <b>Лимит исчерпан!</b> Попробуйте завтра"

            from bot.keyboards import get_manual_post_keyboard
            await send_text_only(callback, text, get_manual_post_keyboard(posts_today >= 3))
            break

    except Exception as e:
        logging.error(f"Ошибка показа меню ручной отправки: {e}")
        await send_text_only(callback, "❌ Произошла ошибка", get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "manual_send_now")
async def manual_send_now(callback: CallbackQuery, state: FSMContext):
    """Отправка поста прямо сейчас"""
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = settings_result.scalar_one_or_none()

            if not setting:
                await callback.answer("❌ Настройки автопостинга не найдены", show_alert=True)
                return

            # Проверяем лимит постов
            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            if posts_today >= 3:
                await callback.answer(
                    f"❌ Лимит исчерпан! Сегодня отправлено {posts_today}/3 постов",
                    show_alert=True
                )
                return

            send_manual_post.delay(
                user_id=user.id,
                channel_id=setting.channel_id,
                category=setting.category,
                style=setting.style
            )

            text = (
                "🚀 <b>Пост отправляется!</b>\n\n"
                f"📺 Канал: {setting.channel_id}\n"
                f"📂 Категория: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Стиль: {get_style_emoji_name(setting.style)}\n"
                f"📊 Будет: {posts_today + 1}/3 постов сегодня\n\n"
                "⏳ Пост будет опубликован в течение минуты"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка ручной отправки: {e}")
        await callback.answer("❌ Ошибка при отправке поста", show_alert=True)


@router.callback_query(F.data == "manual_schedule")
async def manual_schedule_setup(callback: CallbackQuery, state: FSMContext):
    """Настройка запланированной отправки"""
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = settings_result.scalar_one_or_none()

            if not setting:
                await callback.answer("❌ Настройки автопостинга не найдены", show_alert=True)
                return

            # Проверяем текущий лимит
            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            await state.set_state(UserStates.scheduling_manual_post)

            text = (
                "⏰ <b>Запланировать отправку поста</b>\n\n"
                "Отправьте время в формате ЧЧ:ММ\n"
                "Например: <code>15:23</code> или <code>09:00</code>\n\n"
                "📅 Если время уже прошло сегодня, пост будет отправлен завтра\n"
                f"📊 Текущий лимит: {posts_today}/3 постов сегодня\n\n"
                "💡 Введите время:"
            )

            from bot.keyboards import get_manual_schedule_cancel_keyboard
            await send_text_only(callback, text, get_manual_schedule_cancel_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка настройки планирования: {e}")
        await callback.answer("❌ Ошибка при настройке планирования", show_alert=True)

    await callback.answer()


@router.message(UserStates.scheduling_manual_post)
async def process_schedule_time(message: Message, state: FSMContext):
    """Обработка времени для запланированной отправки"""
    time_input = message.text.strip()

    try:
        hour, minute = map(int, time_input.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Используйте формат ЧЧ:ММ (например: 15:23)",
            parse_mode='HTML'
        )
        return

    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = settings_result.scalar_one_or_none()

            if not setting:
                await message.answer("❌ Настройки автопостинга не найдены")
                return

            schedule_post_at_time.delay(
                user_id=user.id,
                channel_id=setting.channel_id,
                category=setting.category,
                style=setting.style,
                target_time=time_input
            )

            now = datetime.now()
            target_hour, target_minute = hour, minute
            target_datetime = now.replace(hour=target_hour, minute=target_minute, second=0)

            if target_datetime <= now:
                target_datetime += timedelta(days=1)
                day_text = "завтра"
            else:
                day_text = "сегодня"

            text = (
                "✅ <b>Пост запланирован!</b>\n\n"
                f"⏰ Время отправки: {time_input} ({day_text})\n"
                f"📺 Канал: {setting.channel_id}\n"
                f"📂 Категория: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Стиль: {get_style_emoji_name(setting.style)}\n\n"
                "🔔 Пост будет автоматически отправлен в указанное время\n"
                "⚠️ Учитывается лимит 3 поста в день"
            )

            await message.answer(text, reply_markup=get_profile_keyboard(), parse_mode='HTML')
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Ошибка планирования поста: {e}")
        await message.answer("❌ Ошибка при планировании поста")


# Все остальные функции остаются без изменений - копирую их полностью
@router.callback_query(F.data == "profile_subscription")
async def show_subscription_details(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            subscriptions_result = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id
                ).order_by(Subscription.created_at.desc())
            )
            subscriptions = subscriptions_result.scalars().all()

            if not subscriptions:
                text = (
                    "📦 <b>Подписки</b>\n\n"
                    "❌ У вас пока нет подписок\n\n"
                    "💡 Приобретите подписку для доступа к:\n"
                    "• Автоматическому постингу новостей\n"
                    "• Выбору категорий и стилей\n"
                    "• Настройке расписания\n"
                    "• До 3 постов в день"
                )
            else:
                text = "📦 <b>Детали подписок</b>\n\n"

                for i, sub in enumerate(subscriptions, 1):
                    emoji = get_subscription_emoji(sub.plan_type)
                    status = format_subscription_status(sub)
                    created_date = sub.created_at.strftime('%d.%m.%Y %H:%M')
                    expires_date = sub.expires_at.strftime('%d.%m.%Y %H:%M')

                    text += (
                        f"{i}. {emoji} <b>Подписка {sub.plan_type} дней</b>\n"
                        f"📊 Статус: {status}\n"
                        f"📅 Создана: {created_date}\n"
                        f"⏰ Истекает: {expires_date}\n"
                    )

                    if sub.is_active:
                        now = datetime.utcnow()
                        if sub.expires_at > now:
                            time_left = sub.expires_at - now
                            days_left = time_left.days
                            hours_left = time_left.seconds // 3600

                            if days_left > 0:
                                text += f"⏳ Осталось: {days_left} дн. {hours_left} ч.\n"
                            else:
                                text += f"⏳ Осталось: {hours_left} ч.\n"

                    text += "\n"

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения деталей подписки: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при загрузке данных",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "profile_payments")
async def show_payment_history(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            payments_result = await db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id
                ).order_by(Transaction.created_at.desc()).limit(10)
            )
            payments = payments_result.scalars().all()

            if not payments:
                text = (
                    "💳 <b>История платежей</b>\n\n"
                    "❌ Платежей пока не было\n\n"
                    "💡 После первой покупки здесь появится история ваших транзакций"
                )
            else:
                total_spent = sum(p.amount for p in payments)
                text = (
                    f"💳 <b>История платежей</b>\n\n"
                    f"💰 Всего потрачено: <b>{total_spent} ⭐</b>\n"
                    f"📊 Количество платежей: <b>{len(payments)}</b>\n\n"
                )

                for i, payment in enumerate(payments, 1):
                    payment_date = payment.created_at.strftime('%d.%m.%Y %H:%M')
                    status_emoji = "✅" if payment.status == "completed" else "❌"

                    plan_type = "неизвестно"
                    if payment.amount == 100:
                        plan_type = "7 дней"
                    elif payment.amount == 180:
                        plan_type = "14 дней"
                    elif payment.amount == 300:
                        plan_type = "30 дней"

                    text += (
                        f"{i}. {status_emoji} <b>{payment.amount} ⭐</b>\n"
                        f"📦 План: {plan_type}\n"
                        f"📅 Дата: {payment_date}\n"
                        f"🆔 ID: <code>{payment.external_id[:12]}...</code>\n\n"
                    )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения истории платежей: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при загрузке истории",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "profile_settings")
async def show_profile_settings(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            autopost_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            autopost_settings = autopost_result.scalars().all()

            channels_count = len(set(setting.channel_id for setting in autopost_settings))
            categories = set(setting.category for setting in autopost_settings)
            styles = set(setting.style for setting in autopost_settings)

            categories_text = ', '.join(
                [get_category_emoji_name(cat) for cat in categories]) if categories else 'Не выбраны'
            styles_text = ', '.join([get_style_emoji_name(style) for style in styles]) if styles else 'Не настроен'

            # Получаем статистику постов
            posts_today = await get_user_post_stats(db, user.id)

            text = (
                f"⚙️ <b>Настройки профиля</b>\n\n"
                f"👤 <b>Основная информация:</b>\n"
                f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Не указан'}\n"
                f"🌐 Язык: {user.language}\n"
                f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"📈 Постов сегодня: {posts_today}/3\n"
                f"⏰ Лимит обновляется в 00:00\n\n"
                f"🔔 <b>Уведомления:</b>\n"
                f"📱 Telegram уведомления: Включены\n"
                f"📧 Email уведомления: Не настроены\n\n"
                f"🤖 <b>Автопостинг:</b>\n"
                f"📺 Подключенные каналы: {channels_count}\n"
                f"📰 Активные категории: {categories_text}\n"
                f"🎨 Стиль постов: {styles_text}\n\n"
                f"💡 <b>Совет:</b> Настройте автопостинг после покупки подписки"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения настроек: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при загрузке настроек",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "profile_help")
async def show_profile_help(callback: CallbackQuery, state: FSMContext):
    text = (
        "❓ <b>Помощь по профилю</b>\n\n"

        "<b>📦 Подписка</b>\n"
        "• 🥉 7 дней - базовый план\n"
        "• 🥈 14 дней - популярный план\n"
        "• 🥇 30 дней - максимальный план\n\n"

        "<b>📊 Лимиты постов:</b>\n"
        "• Максимум 3 поста в день на канал\n"
        "• Лимит обновляется в 00:00 МСК\n"
        "• Автопостинг и ручные посты учитываются\n\n"

        "<b>🔴 Статусы подписки:</b>\n"
        "• 🟢 Активна - подписка работает\n"
        "• 🟡 Истекает - менее суток осталось\n"
        "• 🔴 Неактивна - подписка закончилась\n"
        "• ❌ Нет подписки - не приобретена\n\n"

        "<b>💳 Платежи:</b>\n"
        "• ✅ Завершен - платеж прошел успешно\n"
        "• ❌ Ошибка - проблема с платежом\n\n"

        "<b>⚙️ Настройки:</b>\n"
        "• Telegram ID - ваш уникальный идентификатор\n"
        "• Username - имя пользователя в Telegram\n"
        "• Автопостинг - настройки публикации новостей\n\n"

        "🆘 <b>Нужна помощь?</b>\n"
        "Обратитесь в поддержку через главное меню"
    )

    await send_text_only(callback, text, get_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile_gifts")
async def show_gift_subscriptions(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎁 <b>Подарочные подписки</b>\n\n"

        "🌟 <b>Как получить бесплатную подписку?</b>\n\n"

        "🎯 <b>Способы получения:</b>\n"
        "• 🎲 Участвуйте в розыгрышах\n"
        "• 🎈 Акции по праздникам\n"
        "• 👥 Приводите друзей (реферальная программа)\n"
        "• ⭐ Активность в сообществе\n"
        "• 📝 Отзывы и предложения\n\n"

        "🏆 <b>Текущие акции:</b>\n"
        "• 🎊 Приведи 3 друзей - получи 7 дней бесплатно\n"
        "• 📱 Поделись в соцсетях - участвуй в розыгрыше\n"
        "• 💬 Оставь отзыв - получи бонусы\n\n"

        "📢 <b>Следите за новостями:</b>\n"
        "• Telegram канал: @newsbot_channel\n"
        "• Уведомления о новых акциях\n\n"

        "💡 <b>Совет:</b> Включите уведомления, чтобы не пропустить акции!"
    )

    await send_text_only(callback, text, get_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile_posting_settings")
async def show_posting_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.autopost_setup)

    await state.update_data(
        channels=[],
        categories=[],
        style='',
        frequency=1,
        current_step='main'
    )

    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            subscription_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True
                    )
                )
            )
            active_subscription = subscription_result.first()

            if not active_subscription:
                text = (
                    "⚙️ <b>Настройки автопостинга</b>\n\n"
                    "❌ <b>Требуется активная подписка</b>\n\n"
                    "Для настройки автоматического постинга необходимо:\n"
                    "💎 Приобрести подписку\n"
                    "📺 Добавить бота в канал как администратора\n"
                    "📂 Выбрать категории новостей\n"
                    "🎨 Настроить стиль постов\n\n"
                    "💡 Приобретите подписку для доступа к настройкам"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            autopost_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            user_settings = autopost_result.scalars().all()

            if user_settings:
                channels = list(set(setting.channel_id for setting in user_settings))
                categories = list(set(setting.category for setting in user_settings))
                styles = list(set(setting.style for setting in user_settings))
                frequencies = list(set(setting.posts_per_day for setting in user_settings))

                text = (
                    "⚙️ <b>Настройки автопостинга</b>\n\n"
                    "✅ <b>Автопостинг настроен и активен</b>\n\n"
                )

                if channels:
                    text += f"📺 <b>Каналы ({len(channels)}):</b>\n"
                    for channel in channels[:3]:
                        text += f"• {channel}\n"
                    if len(channels) > 3:
                        text += f"... и еще {len(channels) - 3}\n"
                    text += "\n"

                if categories:
                    text += f"📂 <b>Категории ({len(categories)}):</b>\n"
                    for category in categories[:4]:
                        text += f"• {get_category_emoji_name(category)}\n"
                    if len(categories) > 4:
                        text += f"... и еще {len(categories) - 4}\n"
                    text += "\n"

                if styles:
                    style_names = [get_style_emoji_name(style) for style in styles]
                    text += f"🎨 <b>Стиль:</b> {', '.join(style_names)}\n\n"

                if frequencies:
                    freq_text = ', '.join([f"{f} раз в день" for f in frequencies])
                    text += f"⏰ <b>Расписание:</b> {freq_text}\n\n"

                text += "💡 Выберите действие для управления настройками"
            else:
                text = (
                    "⚙️ <b>Настройки автопостинга</b>\n\n"
                    "📊 <b>Статус:</b> ✅ Подписка активна\n\n"
                    "❌ <b>Автопостинг не настроен</b>\n\n"
                    "Для начала работы необходимо:\n"
                    "📺 Добавить каналы\n"
                    "📂 Выбрать категории новостей\n"
                    "🎨 Настроить стиль постов\n"
                    "⏰ Установить расписание\n\n"
                    "💡 Создайте новую настройку для автопостинга"
                )

            from bot.keyboards import get_autopost_setup_keyboard
            await send_text_only(callback, text, get_autopost_setup_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения настроек постинга: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при загрузке настроек",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "autopost_new", UserStates.autopost_setup)
async def start_new_autopost_setup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.adding_channel)
    await state.update_data(current_step='channels', step_number=1)

    text = (
        "📺 <b>Шаг 1/4: Настройка каналов</b>\n\n"
        "📋 <b>Инструкция:</b>\n"
        "1️⃣ Добавьте бота в ваш канал как администратора\n"
        "2️⃣ Дайте права на 'Публикация сообщений'\n"
        "3️⃣ Нажмите 'Добавить канал' и отправьте username\n\n"
        "💡 Можно добавить несколько каналов\n\n"
        "📺 <b>Добавленные каналы:</b>\n❌ Пока нет"
    )

    from bot.keyboards import get_autopost_step_keyboard
    await send_text_only(callback, text, get_autopost_step_keyboard("channels", False))
    await callback.answer()


@router.callback_query(F.data == "autopost_add_channel", UserStates.adding_channel)
async def prompt_add_channel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Отправьте username канала (например: @my_channel)")


@router.message(UserStates.adding_channel)
async def process_add_channel_new(message: Message, state: FSMContext):
    channel_input = message.text.strip()

    if not (channel_input.startswith('@') or 'telegram.me/' in channel_input or 't.me/' in channel_input):
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Отправьте username канала (например: @my_channel) или ссылку на канал.",
            parse_mode='HTML'
        )
        return

    if channel_input.startswith('@'):
        channel_username = channel_input
    elif 'telegram.me/' in channel_input:
        channel_username = '@' + channel_input.split('telegram.me/')[1]
    elif 't.me/' in channel_input:
        channel_username = '@' + channel_input.split('t.me/')[1]
    else:
        channel_username = channel_input

    channel_username = channel_username.strip().split('?')[0]

    try:
        chat = await message.bot.get_chat(channel_username)
        chat_member = await message.bot.get_chat_member(channel_username, message.bot.id)

        if chat_member.status not in ['administrator']:
            await message.answer(
                f"❌ <b>Бот не является администратором в канале {channel_username}</b>\n\n"
                "Пожалуйста, добавьте бота как администратора с правами на публикацию сообщений.",
                parse_mode='HTML'
            )
            return

        if not chat_member.can_post_messages:
            await message.answer(
                f"❌ <b>У бота нет прав на публикацию в канале {channel_username}</b>\n\n"
                "Пожалуйста, дайте боту права на публикацию сообщений.",
                parse_mode='HTML'
            )
            return

        data = await state.get_data()
        channels = data.get('channels', [])

        if channel_username not in channels:
            channels.append(channel_username)
            await state.update_data(channels=channels)

            channels_text = '\n'.join([f"• {ch}" for ch in channels])

            text = (
                "📺 <b>Шаг 1/4: Настройка каналов</b>\n\n"
                "📋 <b>Инструкция:</b>\n"
                "1️⃣ Добавьте бота в ваш канал как администратора\n"
                "2️⃣ Дайте права на 'Публикация сообщений'\n"
                "3️⃣ Нажмите 'Добавить канал' и отправьте username\n\n"
                "💡 Можно добавить несколько каналов\n\n"
                f"📺 <b>Добавленные каналы:</b>\n{channels_text}"
            )

            from bot.keyboards import get_autopost_step_keyboard
            await message.answer(
                text,
                reply_markup=get_autopost_step_keyboard("channels", False),
                parse_mode='HTML'
            )

            await message.answer(
                f"✅ Канал {channel_username} ({chat.title}) добавлен!",
                parse_mode='HTML'
            )
        else:
            await message.answer(f"⚠️ Канал {channel_username} уже добавлен")

    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower():
            await message.answer(
                f"❌ <b>Канал {channel_username} не найден</b>\n\n"
                "Проверьте правильность username канала.",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка при проверке канала</b>\n\n"
                "Убедитесь, что бот добавлен в канал как администратор.",
                parse_mode='HTML'
            )


@router.callback_query(F.data == "autopost_next_step")
async def next_autopost_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_step = data.get('current_step', 'channels')
    step_number = data.get('step_number', 1)

    if current_step == 'channels':
        channels = data.get('channels', [])
        if not channels:
            await callback.answer("❌ Добавьте хотя бы один канал!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_categories)
        await state.update_data(current_step='categories', step_number=2)

        text = (
            "📂 <b>Шаг 2/4: Выбор категорий</b>\n\n"
            "Выберите категории новостей для автопостинга:\n\n"
            "💡 <b>Совет:</b> Выбирайте 2-4 категории для лучшего качества\n\n"
            "🎯 <b>Выбранные категории:</b> Пока не выбраны"
        )

        from bot.keyboards import get_category_selection_keyboard_new
        await send_text_only(callback, text, get_category_selection_keyboard_new())

    elif current_step == 'categories':
        categories = data.get('categories', [])
        if not categories:
            await callback.answer("❌ Выберите хотя бы одну категорию!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_style)
        await state.update_data(current_step='style', step_number=3)

        text = (
            "🎨 <b>Шаг 3/4: Выбор стиля</b>\n\n"
            "Выберите стиль оформления постов:\n\n"
            "🎩 <b>Формальный</b> - деловой стиль\n"
            "😎 <b>Разговорный</b> - дружелюбный тон\n"
            "🤪 <b>Мемный</b> - юмористический стиль\n\n"
            "🎯 <b>Выбранный стиль:</b> Не выбран"
        )

        from bot.keyboards import get_style_selection_keyboard_new
        await send_text_only(callback, text, get_style_selection_keyboard_new())

    elif current_step == 'style':
        style = data.get('style', '')
        if not style:
            await callback.answer("❌ Выберите стиль!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_schedule)
        await state.update_data(current_step='schedule', step_number=4)

        text = (
            "⏰ <b>Шаг 4/4: Настройка расписания</b>\n\n"
            "Выберите частоту публикации постов:\n\n"
            "• 1️⃣ <b>1 раз в день</b> - для небольших каналов\n"
            "• 2️⃣ <b>2 раза в день</b> - оптимальный вариант\n"
            "• 3️⃣ <b>3 раза в день</b> - для активных каналов\n\n"
            "🎯 <b>Выбранное расписание:</b> Не настроено"
        )

        from bot.keyboards import get_schedule_selection_keyboard_new
        await send_text_only(callback, text, get_schedule_selection_keyboard_new())

    elif current_step == 'schedule':
        frequency = data.get('frequency', 0)
        if not frequency:
            await callback.answer("❌ Выберите расписание!", show_alert=True)
            return

        await state.set_state(UserStates.confirming_settings)
        await state.update_data(current_step='confirm')

        summary_text = format_autopost_summary(data)
        from bot.keyboards import get_confirmation_keyboard_autopost
        await send_text_only(callback, summary_text, get_confirmation_keyboard_autopost())

    await callback.answer()


@router.callback_query(F.data.startswith("autopost_toggle_cat_"))
async def toggle_category_new(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("autopost_toggle_cat_", "")

    data = await state.get_data()
    categories = data.get('categories', [])

    if category in categories:
        categories.remove(category)
        status = "убрана"
    else:
        categories.append(category)
        status = "добавлена"

    await state.update_data(categories=categories)

    selected_text = ', '.join([get_category_emoji_name(cat) for cat in categories]) if categories else "Пока не выбраны"

    text = (
        "📂 <b>Шаг 2/4: Выбор категорий</b>\n\n"
        "Выберите категории новостей для автопостинга:\n\n"
        "💡 <b>Совет:</b> Выбирайте 2-4 категории для лучшего качества\n\n"
        f"🎯 <b>Выбранные категории:</b> {selected_text}"
    )

    from bot.keyboards import get_category_selection_keyboard_new
    await callback.message.edit_text(
        text,
        reply_markup=get_category_selection_keyboard_new(categories),
        parse_mode='HTML'
    )

    await callback.answer(f"Категория {status}")


@router.callback_query(F.data.startswith("autopost_set_style_"))
async def set_style_new(callback: CallbackQuery, state: FSMContext):
    style = callback.data.replace("autopost_set_style_", "")

    await state.update_data(style=style)

    style_text = get_style_emoji_name(style)

    text = (
        "🎨 <b>Шаг 3/4: Выбор стиля</b>\n\n"
        "Выберите стиль оформления постов:\n\n"
        "🎩 <b>Формальный</b> - деловой стиль\n"
        "😎 <b>Разговорный</b> - дружелюбный тон\n"
        "🤪 <b>Мемный</b> - юмористический стиль\n\n"
        f"🎯 <b>Выбранный стиль:</b> {style_text}"
    )

    from bot.keyboards import get_style_selection_keyboard_new
    await callback.message.edit_text(
        text,
        reply_markup=get_style_selection_keyboard_new(style),
        parse_mode='HTML'
    )

    await callback.answer(f"Стиль установлен: {style_text}")


@router.callback_query(F.data.startswith("autopost_set_schedule_"))
async def set_schedule_new(callback: CallbackQuery, state: FSMContext):
    frequency = int(callback.data.replace("autopost_set_schedule_", ""))

    await state.update_data(frequency=frequency)

    schedule_names = {
        1: "1 раз в день (09:00)",
        2: "2 раза в день (09:00, 21:00)",
        3: "3 раза в день (09:00, 15:00, 21:00)"
    }

    schedule_text = schedule_names.get(frequency, "")

    text = (
        "⏰ <b>Шаг 4/4: Настройка расписания</b>\n\n"
        "Выберите частоту публикации постов:\n\n"
        "• 1️⃣ <b>1 раз в день</b> - для небольших каналов\n"
        "• 2️⃣ <b>2 раза в день</b> - оптимальный вариант\n"
        "• 3️⃣ <b>3 раза в день</b> - для активных каналов\n\n"
        f"🎯 <b>Выбранное расписание:</b> {schedule_text}"
    )

    from bot.keyboards import get_schedule_selection_keyboard_new
    await callback.message.edit_text(
        text,
        reply_markup=get_schedule_selection_keyboard_new(frequency),
        parse_mode='HTML'
    )

    await callback.answer(f"Расписание установлено: {schedule_text}")


@router.callback_query(F.data == "autopost_save_all")
async def save_autopost_settings(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        channels = data.get('channels', [])
        categories = data.get('categories', [])
        style = data.get('style', 'formal')
        frequency = data.get('frequency', 1)

        if not channels or not categories:
            await callback.answer("❌ Не все настройки заполнены!", show_alert=True)
            return

        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            await db.execute(
                delete(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                )
            )

            schedule_times = get_schedule_times(frequency)

            for channel in channels:
                for category in categories:
                    setting = AutopostSettings(
                        user_id=user.id,
                        channel_id=channel,
                        category=category,
                        style=style,
                        posts_per_day=frequency,
                        specific_times=schedule_times,
                        is_active=True
                    )
                    db.add(setting)

            await db.commit()

            text = (
                "✅ <b>Настройки автопостинга сохранены!</b>\n\n"
                f"📺 <b>Каналы:</b> {len(channels)} шт.\n"
                f"📂 <b>Категории:</b> {len(categories)} шт.\n"
                f"🎨 <b>Стиль:</b> {get_style_emoji_name(style)}\n"
                f"⏰ <b>Расписание:</b> {frequency} раз в день\n\n"
                "🚀 Автопостинг активирован и будет работать по расписанию!"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Ошибка сохранения настроек автопостинга: {e}")
        await send_text_only(
            callback,
            "❌ Произошла ошибка при сохранении настроек",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "autopost_back_step")
async def back_autopost_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_step = data.get('current_step', 'channels')

    if current_step == 'categories':
        await state.set_state(UserStates.adding_channel)
        await state.update_data(current_step='channels', step_number=1)

        channels = data.get('channels', [])
        channels_text = '\n'.join([f"• {ch}" for ch in channels]) if channels else "❌ Пока нет"

        text = (
            "📺 <b>Шаг 1/4: Настройка каналов</b>\n\n"
            "📋 <b>Инструкция:</b>\n"
            "1️⃣ Добавьте бота в ваш канал как администратора\n"
            "2️⃣ Дайте права на 'Публикация сообщений'\n"
            "3️⃣ Нажмите 'Добавить канал' и отправьте username\n\n"
            "💡 Можно добавить несколько каналов\n\n"
            f"📺 <b>Добавленные каналы:</b>\n{channels_text}"
        )

        from bot.keyboards import get_autopost_step_keyboard
        await send_text_only(callback, text, get_autopost_step_keyboard("channels", False))

    elif current_step == 'style':
        await state.set_state(UserStates.selecting_categories)
        await state.update_data(current_step='categories', step_number=2)

        categories = data.get('categories', [])
        selected_text = ', '.join(
            [get_category_emoji_name(cat) for cat in categories]) if categories else "Пока не выбраны"

        text = (
            "📂 <b>Шаг 2/4: Выбор категорий</b>\n\n"
            "Выберите категории новостей для автопостинга:\n\n"
            "💡 <b>Совет:</b> Выбирайте 2-4 категории для лучшего качества\n\n"
            f"🎯 <b>Выбранные категории:</b> {selected_text}"
        )

        from bot.keyboards import get_category_selection_keyboard_new
        await send_text_only(callback, text, get_category_selection_keyboard_new(categories))

    elif current_step == 'schedule':
        await state.set_state(UserStates.selecting_style)
        await state.update_data(current_step='style', step_number=3)

        style = data.get('style', '')
        style_text = get_style_emoji_name(style) if style else "Не выбран"

        text = (
            "🎨 <b>Шаг 3/4: Выбор стиля</b>\n\n"
            "Выберите стиль оформления постов:\n\n"
            "🎩 <b>Формальный</b> - деловой стиль\n"
            "😎 <b>Разговорный</b> - дружелюбный тон\n"
            "🤪 <b>Мемный</b> - юмористический стиль\n\n"
            f"🎯 <b>Выбранный стиль:</b> {style_text}"
        )

        from bot.keyboards import get_style_selection_keyboard_new
        await send_text_only(callback, text, get_style_selection_keyboard_new(style))

    elif current_step == 'confirm':
        await state.set_state(UserStates.selecting_schedule)
        await state.update_data(current_step='schedule', step_number=4)

        frequency = data.get('frequency', 0)
        schedule_names = {
            1: "1 раз в день (09:00)",
            2: "2 раза в день (09:00, 21:00)",
            3: "3 раза в день (09:00, 15:00, 21:00)"
        }
        schedule_text = schedule_names.get(frequency, "Не настроено")

        text = (
            "⏰ <b>Шаг 4/4: Настройка расписания</b>\n\n"
            "Выберите частоту публикации постов:\n\n"
            "• 1️⃣ <b>1 раз в день</b> - для небольших каналов\n"
            "• 2️⃣ <b>2 раза в день</b> - оптимальный вариант\n"
            "• 3️⃣ <b>3 раза в день</b> - для активных каналов\n\n"
            f"🎯 <b>Выбранное расписание:</b> {schedule_text}"
        )

        from bot.keyboards import get_schedule_selection_keyboard_new
        await send_text_only(callback, text, get_schedule_selection_keyboard_new(frequency))

    await callback.answer()


@router.callback_query(F.data == "autopost_edit_settings")
async def edit_autopost_settings(callback: CallbackQuery, state: FSMContext):
    await start_new_autopost_setup(callback, state)


@router.callback_query(F.data == "autopost_cancel")
async def cancel_autopost_setup(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    text = (
        "❌ <b>Настройка автопостинга отменена</b>\n\n"
        "Вы можете вернуться к настройке в любое время через профиль."
    )

    await send_text_only(callback, text, get_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "autopost_edit")
async def edit_existing_autopost(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                )
            )
            settings = settings_result.scalars().all()

            if not settings:
                text = (
                    "❌ <b>Нет настроек для редактирования</b>\n\n"
                    "Сначала создайте новую настройку автопостинга."
                )
                from bot.keyboards import get_autopost_setup_keyboard
                await send_text_only(callback, text, get_autopost_setup_keyboard())
                await callback.answer()
                return

            channels = list(set(s.channel_id for s in settings))
            categories = list(set(s.category for s in settings))
            style = settings[0].style if settings else 'formal'
            frequency = settings[0].posts_per_day if settings else 1

            await state.update_data(
                channels=channels,
                categories=categories,
                style=style,
                frequency=frequency,
                current_step='main'
            )

            summary_text = format_autopost_summary({
                'channels': channels,
                'categories': categories,
                'style': style,
                'frequency': frequency
            })

            summary_text += "\n\n💡 Нажмите 'Редактировать' для изменения настроек"

            from bot.keyboards import get_confirmation_keyboard_autopost
            await send_text_only(callback, summary_text, get_confirmation_keyboard_autopost())
            break

    except Exception as e:
        logging.error(f"Ошибка загрузки настроек для редактирования: {e}")
        text = "❌ Произошла ошибка при загрузке настроек"
        from bot.keyboards import get_autopost_setup_keyboard
        await send_text_only(callback, text, get_autopost_setup_keyboard())

    await callback.answer()


@router.callback_query(F.data == "autopost_delete")
async def delete_autopost_settings(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            result = await db.execute(
                delete(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                )
            )

            await db.commit()

            if result.rowcount > 0:
                text = (
                    "✅ <b>Настройки автопостинга удалены</b>\n\n"
                    f"Удалено настроек: {result.rowcount}\n\n"
                    "Автопостинг остановлен. Вы можете создать новую настройку в любое время."
                )
            else:
                text = (
                    "⚠️ <b>Настройки автопостинга не найдены</b>\n\n"
                    "У вас нет активных настроек для удаления."
                )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка удаления настроек автопостинга: {e}")
        text = "❌ Произошла ошибка при удалении настроек"
        await send_text_only(callback, text, get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "profile_back")
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    await show_profile(callback, state)

@router.callback_query(F.data == "manual_post")
async def show_manual_post_menu(callback: CallbackQuery, state: FSMContext):
    """Меню ручной отправки постов"""
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            subscription_result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.user_id == user.id,
                        Subscription.is_active == True,
                        Subscription.expires_at > datetime.utcnow()
                    )
                )
            )
            active_subscription = subscription_result.first()

            if not active_subscription:
                text = (
                    "📤 <b>Ручная отправка постов</b>\n\n"
                    "❌ <b>Требуется активная подписка</b>\n\n"
                    "Для ручной отправки постов необходима активная подписка.\n\n"
                    "💎 Приобретите подписку для доступа к функции"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            autopost_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = autopost_result.scalar_one_or_none()

            if not setting:
                text = (
                    "📤 <b>Ручная отправка постов</b>\n\n"
                    "❌ <b>Автопостинг не настроен</b>\n\n"
                    "Сначала настройте автопостинг в разделе 'Настройки постинга'.\n\n"
                    "💡 После настройки здесь появятся функции ручной отправки"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            text = (
                "📤 <b>Ручная отправка постов</b>\n\n"
                "Выберите действие:\n\n"
                "🚀 <b>Отправить сейчас</b> - немедленная отправка поста\n"
                "⏰ <b>Запланировать</b> - отправка в указанное время\n"
                "📊 <b>Тестовый пост</b> - отправка тестового сообщения\n\n"
                f"📺 <b>Канал:</b> {setting.channel_id}\n"
                f"📂 <b>Категория:</b> {get_category_emoji_name(setting.category)}\n"
                f"🎨 <b>Стиль:</b> {get_style_emoji_name(setting.style)}"
            )

            from bot.keyboards import get_manual_post_keyboard
            await send_text_only(callback, text, get_manual_post_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка показа меню ручной отправки: {e}")
        await send_text_only(callback, "❌ Произошла ошибка", get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "manual_send_now")
async def manual_send_now(callback: CallbackQuery, state: FSMContext):
    """Отправка поста прямо сейчас"""
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден", show_alert=True)
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = settings_result.scalar_one_or_none()

            if not setting:
                await callback.answer("❌ Настройки автопостинга не найдены", show_alert=True)
                return

            send_manual_post.delay(
                user_id=user.id,
                channel_id=setting.channel_id,
                category=setting.category,
                style=setting.style
            )

            text = (
                "🚀 <b>Пост отправляется!</b>\n\n"
                f"📺 Канал: {setting.channel_id}\n"
                f"📂 Категория: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Стиль: {get_style_emoji_name(setting.style)}\n\n"
                "⏳ Пост будет опубликован в течение минуты"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка ручной отправки: {e}")
        await callback.answer("❌ Ошибка при отправке поста", show_alert=True)


@router.callback_query(F.data == "manual_schedule")
async def manual_schedule_setup(callback: CallbackQuery, state: FSMContext):
    """Настройка запланированной отправки"""
    await state.set_state(UserStates.scheduling_manual_post)

    text = (
        "⏰ <b>Запланировать отправку поста</b>\n\n"
        "Отправьте время в формате ЧЧ:ММ\n"
        "Например: <code>15:23</code> или <code>09:00</code>\n\n"
        "📅 Если время уже прошло сегодня, пост будет отправлен завтра\n\n"
        "💡 Введите время:"
    )

    from bot.keyboards import get_manual_schedule_cancel_keyboard
    await send_text_only(callback, text, get_manual_schedule_cancel_keyboard())
    await callback.answer()


@router.message(UserStates.scheduling_manual_post)
async def process_schedule_time(message: Message, state: FSMContext):
    """Обработка времени для запланированной отправки"""
    time_input = message.text.strip()

    try:
        hour, minute = map(int, time_input.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "❌ <b>Неверный формат времени!</b>\n\n"
            "Используйте формат ЧЧ:ММ (например: 15:23)",
            parse_mode='HTML'
        )
        return

    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer("❌ Пользователь не найден")
                return

            settings_result = await db.execute(
                select(AutopostSettings).where(
                    and_(
                        AutopostSettings.user_id == user.id,
                        AutopostSettings.is_active == True
                    )
                ).limit(1)
            )
            setting = settings_result.scalar_one_or_none()

            if not setting:
                await message.answer("❌ Настройки автопостинга не найдены")
                return

            schedule_post_at_time.delay(
                user_id=user.id,
                channel_id=setting.channel_id,
                category=setting.category,
                style=setting.style,
                target_time=time_input
            )

            now = datetime.now()
            target_hour, target_minute = hour, minute
            target_datetime = now.replace(hour=target_hour, minute=target_minute, second=0)

            if target_datetime <= now:
                target_datetime += timedelta(days=1)
                day_text = "завтра"
            else:
                day_text = "сегодня"

            text = (
                "✅ <b>Пост запланирован!</b>\n\n"
                f"⏰ Время отправки: {time_input} ({day_text})\n"
                f"📺 Канал: {setting.channel_id}\n"
                f"📂 Категория: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Стиль: {get_style_emoji_name(setting.style)}\n\n"
                "🔔 Пост будет автоматически отправлен в указанное время"
            )

            await message.answer(text, reply_markup=get_profile_keyboard(), parse_mode='HTML')
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Ошибка планирования поста: {e}")
        await message.answer("❌ Ошибка при планировании поста")
