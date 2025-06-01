from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from database.models import User, Subscription, Transaction
from database.database import get_db
from bot.keyboards import get_admin_keyboard, get_admin_back_keyboard
from bot.states import AdminStates
from config.settings import settings
import logging

router = Router()


async def send_text_only(callback: CallbackQuery, text: str, reply_markup=None):
    """Отправляет текстовое сообщение, удаляя предыдущее (даже если оно с фото)"""
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


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    is_admin_user = user_id in settings.ADMIN_IDS

    logging.info(f"🔍 Admin check - User ID: {user_id}, Admin IDs: {settings.ADMIN_IDS}, Is admin: {is_admin_user}")

    if not is_admin_user:
        logging.warning(f"❌ Unauthorized admin access attempt by user {user_id}")
    else:
        logging.info(f"✅ Admin access granted to user {user_id}")

    return is_admin_user


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    """Вход в админ панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ панели.")
        return

    await state.set_state(AdminStates.main_menu)

    admin_text = (
        "🛡️ <b>Админ панель NewsBot</b>\n\n"
        f"👤 Администратор: {message.from_user.first_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        "Выберите действие:"
    )

    await message.answer(
        admin_text,
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_add_source")
async def add_news_source(callback: CallbackQuery, state: FSMContext):
    """Добавление нового новостного источника"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.adding_source)

    text = (
        "📰 <b>Добавление нового источника</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>категория|название|url</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>it|Хабр|https://habr.com/ru/rss/hub/programming/</code>\n\n"
        "<b>Доступные категории:</b>\n"
        "• it, crypto, business, general\n"
        "• esports, tech, politics, science\n"
        "• auto, health, entertainment, sport"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_source)
async def process_add_source(message: Message, state: FSMContext):
    """Обработка добавления источника"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 3:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используйте: <code>категория|название|url</code>",
                parse_mode='HTML'
            )
            return

        category, name, url = [part.strip() for part in parts]

        # Здесь можно добавить логику сохранения в базу данных
        # Пока просто подтверждаем добавление

        success_text = (
            "✅ <b>Источник добавлен!</b>\n\n"
            f"📂 Категория: <b>{category}</b>\n"
            f"📰 Название: <b>{name}</b>\n"
            f"🔗 URL: <code>{url}</code>\n\n"
            "Источник будет активен при следующем обновлении новостей."
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} added source: {category}|{name}|{url}")

    except Exception as e:
        logging.error(f"Ошибка добавления источника: {e}")
        await message.answer(
            "❌ Произошла ошибка при добавлении источника.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_add_category")
async def add_category(callback: CallbackQuery, state: FSMContext):
    """Добавление новой категории"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.adding_category)

    text = (
        "📂 <b>Добавление новой категории</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>код|название|эмодзи</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>gaming|Игры|🎮</code>\n\n"
        "<b>Требования:</b>\n"
        "• Код только латинские буквы\n"
        "• Название на русском\n"
        "• Один эмодзи"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_category)
async def process_add_category(message: Message, state: FSMContext):
    """Обработка добавления категории"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 3:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используйте: <code>код|название|эмодзи</code>",
                parse_mode='HTML'
            )
            return

        code, name, emoji = [part.strip() for part in parts]

        # Здесь можно добавить логику сохранения категории

        success_text = (
            "✅ <b>Категория добавлена!</b>\n\n"
            f"🔤 Код: <b>{code}</b>\n"
            f"📝 Название: <b>{name}</b>\n"
            f"😀 Эмодзи: {emoji}\n\n"
            "Не забудьте добавить источники для новой категории!"
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} added category: {code}|{name}|{emoji}")

    except Exception as e:
        logging.error(f"Ошибка добавления категории: {e}")
        await message.answer(
            "❌ Произошла ошибка при добавлении категории.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_stats")
async def show_purchase_stats(callback: CallbackQuery, state: FSMContext):
    """Просмотр статистики покупок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    try:
        async for db in get_db():
            # Статистика за последние 30 дней
            start_date = datetime.utcnow() - timedelta(days=30)

            # Общая статистика транзакций
            result = await db.execute(
                select(Transaction).where(
                    and_(
                        Transaction.status == 'completed',
                        Transaction.created_at >= start_date
                    )
                )
            )
            transactions = result.scalars().all()

            # Статистика по дням
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_transactions = [t for t in transactions if t.created_at >= today_start]

            # Статистика по тарифам
            plans_stats = {}
            for transaction in transactions:
                if transaction.amount == 100:
                    plans_stats['7_days'] = plans_stats.get('7_days', 0) + 1
                elif transaction.amount == 180:
                    plans_stats['14_days'] = plans_stats.get('14_days', 0) + 1
                elif transaction.amount == 300:
                    plans_stats['30_days'] = plans_stats.get('30_days', 0) + 1

            total_amount = sum(t.amount for t in transactions)
            today_amount = sum(t.amount for t in today_transactions)

            stats_text = (
                "📊 <b>Статистика покупок</b>\n\n"
                f"📅 <b>За последние 30 дней:</b>\n"
                f"💰 Общая сумма: <b>{total_amount} ⭐</b>\n"
                f"📦 Покупок: <b>{len(transactions)}</b>\n"
                f"📈 Средний чек: <b>{total_amount / len(transactions) if transactions else 0:.1f} ⭐</b>\n\n"

                f"🗓️ <b>Сегодня:</b>\n"
                f"💰 Сумма: <b>{today_amount} ⭐</b>\n"
                f"📦 Покупок: <b>{len(today_transactions)}</b>\n\n"

                f"📊 <b>По тарифам (30 дней):</b>\n"
                f"• 7 дней: <b>{plans_stats.get('7_days', 0)}</b> шт\n"
                f"• 14 дней: <b>{plans_stats.get('14_days', 0)}</b> шт\n"
                f"• 30 дней: <b>{plans_stats.get('30_days', 0)}</b> шт"
            )

            await send_text_only(callback, stats_text, get_admin_back_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}")
        await send_text_only(
            callback,
            "❌ Ошибка получения статистики",
            get_admin_back_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def show_subscribed_users(callback: CallbackQuery, state: FSMContext):
    """Список пользователей с подписками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    try:
        async for db in get_db():
            # Получаем активные подписки
            result = await db.execute(
                select(Subscription, User).join(User).where(
                    Subscription.is_active == True
                ).order_by(Subscription.expires_at.desc())
            )
            subscriptions = result.all()

            if not subscriptions:
                await send_text_only(
                    callback,
                    "📋 <b>Активные подписки</b>\n\n❌ Нет активных подписок",
                    get_admin_back_keyboard()
                )
                await callback.answer()
                return

            users_text = "📋 <b>Активные подписки</b>\n\n"

            for subscription, user in subscriptions[:10]:  # Показываем первые 10
                expires_date = subscription.expires_at.strftime('%d.%m.%Y %H:%M')
                username = f"@{user.username}" if user.username else "Без username"

                users_text += (
                    f"👤 {username}\n"
                    f"🆔 <code>{user.telegram_id}</code>\n"
                    f"📦 Тариф: {subscription.plan_type} дней\n"
                    f"⏰ До: {expires_date}\n\n"
                )

            if len(subscriptions) > 10:
                users_text += f"... и еще {len(subscriptions) - 10} пользователей"

            await send_text_only(callback, users_text, get_admin_back_keyboard())
            break

    except Exception as e:
        logging.error(f"Ошибка получения списка пользователей: {e}")
        await send_text_only(
            callback,
            "❌ Ошибка получения списка пользователей",
            get_admin_back_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.main_menu)

    admin_text = (
        "🛡️ <b>Админ панель NewsBot</b>\n\n"
        f"👤 Администратор: {callback.from_user.first_name}\n"
        f"🆔 ID: <code>{callback.from_user.id}</code>\n\n"
        "Выберите действие:"
    )

    await send_text_only(callback, admin_text, get_admin_keyboard())
    await callback.answer()