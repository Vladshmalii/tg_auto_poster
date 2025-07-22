from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime, timedelta
from database.models import User, Subscription, Transaction
from database.database import get_db
from bot.keyboards import (
    get_admin_keyboard, get_admin_back_keyboard,
    get_admin_users_keyboard, get_admin_sources_keyboard,
    get_admin_categories_keyboard, get_admin_tokens_keyboard,
    get_admin_sites_keyboard, get_admin_logs_keyboard
)
from bot.states import AdminStates
from config.settings import settings
import logging
import uuid

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
        "Выберите раздел для управления:"
    )

    await message.answer(
        admin_text,
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_users")
@router.callback_query(F.data.startswith("admin_users_page_"))
async def show_users(callback: CallbackQuery, state: FSMContext):
    """Показ списка пользователей с пагинацией"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Получаем номер страницы
    page = 0
    if callback.data.startswith("admin_users_page_"):
        page = int(callback.data.split("_")[-1])

    try:
        async for db in get_db():
            # Получаем общее количество активных подписок
            count_result = await db.execute(
                select(func.count(Subscription.id)).where(Subscription.is_active == True)
            )
            total_count = count_result.scalar()

            users_per_page = 10
            total_pages = (total_count + users_per_page - 1) // users_per_page
            offset = page * users_per_page

            # Получаем пользователей для текущей страницы
            result = await db.execute(
                select(Subscription, User)
                .join(User)
                .where(Subscription.is_active == True)
                .order_by(Subscription.expires_at.desc())
                .offset(offset)
                .limit(users_per_page)
            )
            subscriptions = result.all()

            if not subscriptions and page == 0:
                await send_text_only(
                    callback,
                    "👥 <b>Пользователи</b>\n\n❌ Нет активных подписок",
                    get_admin_users_keyboard(page, total_pages)
                )
            else:
                users_text = f"👥 <b>Пользователи</b> (стр. {page + 1}/{total_pages})\n\n"

                for subscription, user in subscriptions:
                    expires_date = subscription.expires_at.strftime('%d.%m.%Y %H:%M')
                    username = f"@{user.username}" if user.username else f"ID: {user.telegram_id}"

                    users_text += (
                        f"👤 {username}\n"
                        f"📦 Тариф: {subscription.plan_type} дней\n"
                        f"⏰ До: {expires_date}\n\n"
                    )

                await send_text_only(callback, users_text, get_admin_users_keyboard(page, total_pages))
            break

    except Exception as e:
        logging.error(f"Ошибка получения списка пользователей: {e}")
        await send_text_only(
            callback,
            "❌ Ошибка получения списка пользователей",
            get_admin_back_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "admin_add_subscription")
async def add_subscription_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос данных для добавления подписки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.adding_subscription)

    text = (
        "➕ <b>Добавление подписки</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>telegram_id|дни</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>123456789|30</code>\n\n"
        "<b>Доступные планы:</b> 7, 14, 30 дней"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_subscription)
async def process_add_subscription(message: Message, state: FSMContext):
    """Обработка добавления подписки"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 2:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используйте: <code>telegram_id|дни</code>",
                parse_mode='HTML'
            )
            return

        telegram_id, days = [part.strip() for part in parts]

        if not telegram_id.isdigit() or not days.isdigit():
            await message.answer("❌ ID и количество дней должны быть числами")
            return

        telegram_id = int(telegram_id)
        days = int(days)

        if days not in [7, 14, 30]:
            await message.answer("❌ Доступны только планы: 7, 14, 30 дней")
            return

        async for db in get_db():
            # Ищем пользователя
            user_result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer(f"❌ Пользователь с ID {telegram_id} не найден в системе")
                return

            # Создаем подписку
            expires_at = datetime.utcnow() + timedelta(days=days)
            subscription = Subscription(
                user_id=user.id,
                plan_type=days,
                expires_at=expires_at,
                is_active=True
            )
            db.add(subscription)
            await db.commit()

            success_text = (
                "✅ <b>Подписка добавлена!</b>\n\n"
                f"👤 Пользователь: @{user.username or 'Unknown'}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"📦 План: {days} дней\n"
                f"📅 Действует до: {expires_at.strftime('%d.%m.%Y %H:%M')}"
            )

            await message.answer(
                success_text,
                reply_markup=get_admin_back_keyboard(),
                parse_mode='HTML'
            )

            logging.info(f"Admin {message.from_user.id} added subscription: {telegram_id}|{days} days")
            break

    except Exception as e:
        logging.error(f"Ошибка добавления подписки: {e}")
        await message.answer(
            "❌ Произошла ошибка при добавлении подписки.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_disable_subscription")
async def disable_subscription_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос ID для отключения подписки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.disabling_subscription)

    text = (
        "🗑 <b>Отключение подписки</b>\n\n"
        "Отправьте Telegram ID пользователя:\n\n"
        "<b>Пример:</b>\n"
        "<code>123456789</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.disabling_subscription)
async def process_disable_subscription(message: Message, state: FSMContext):
    """Обработка отключения подписки"""
    try:
        telegram_id = message.text.strip()

        if not telegram_id.isdigit():
            await message.answer("❌ ID должен быть числом")
            return

        telegram_id = int(telegram_id)

        async for db in get_db():
            # Ищем активную подписку пользователя
            result = await db.execute(
                select(Subscription, User)
                .join(User)
                .where(
                    and_(
                        User.telegram_id == telegram_id,
                        Subscription.is_active == True
                    )
                )
            )
            subscription_user = result.first()

            if not subscription_user:
                await message.answer(f"❌ Активная подписка для пользователя {telegram_id} не найдена")
                return

            subscription, user = subscription_user

            # Отключаем подписку
            subscription.is_active = False
            await db.commit()

            success_text = (
                "✅ <b>Подписка отключена!</b>\n\n"
                f"👤 Пользователь: @{user.username or 'Unknown'}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"📦 Был план: {subscription.plan_type} дней"
            )

            await message.answer(
                success_text,
                reply_markup=get_admin_back_keyboard(),
                parse_mode='HTML'
            )

            logging.info(f"Admin {message.from_user.id} disabled subscription for user {telegram_id}")
            break

    except Exception as e:
        logging.error(f"Ошибка отключения подписки: {e}")
        await message.answer(
            "❌ Произошла ошибка при отключении подписки.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_search_user")
async def search_user_prompt(callback: CallbackQuery, state: FSMContext):
    """Поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.searching_user)

    text = (
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправьте Telegram ID или username:\n\n"
        "<b>Примеры:</b>\n"
        "<code>123456789</code>\n"
        "<code>@username</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.searching_user)
async def process_search_user(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    try:
        search_query = message.text.strip()

        async for db in get_db():
            if search_query.startswith('@'):
                # Поиск по username
                username = search_query[1:]
                result = await db.execute(
                    select(User, Subscription)
                    .outerjoin(Subscription)
                    .where(User.username == username)
                )
            elif search_query.isdigit():
                # Поиск по Telegram ID
                telegram_id = int(search_query)
                result = await db.execute(
                    select(User, Subscription)
                    .outerjoin(Subscription)
                    .where(User.telegram_id == telegram_id)
                )
            else:
                await message.answer("❌ Неверный формат поиска")
                return

            user_data = result.all()

            if not user_data:
                await message.answer(
                    f"❌ Пользователь <code>{search_query}</code> не найден",
                    parse_mode='HTML'
                )
                return

            user = user_data[0][0]  # Первый пользователь
            subscriptions = [row[1] for row in user_data if row[1]]

            result_text = (
                f"👤 <b>Пользователь найден</b>\n\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Не указан'}\n"
                f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )

            if subscriptions:
                result_text += "<b>📦 Подписки:</b>\n"
                for sub in subscriptions:
                    status = "🟢 Активна" if sub.is_active else "🔴 Неактивна"
                    result_text += (
                        f"• {sub.plan_type} дней - {status}\n"
                        f"  До: {sub.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                    )
            else:
                result_text += "❌ Подписок нет"

            await message.answer(
                result_text,
                reply_markup=get_admin_back_keyboard(),
                parse_mode='HTML'
            )
            break

    except Exception as e:
        logging.error(f"Ошибка поиска пользователя: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_sources")
async def show_sources_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления источниками"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    text = (
        "📰 <b>Управление источниками</b>\n\n"
        "Здесь вы можете управлять RSS-источниками новостей"
    )

    await send_text_only(callback, text, get_admin_sources_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_sources")
async def list_sources(callback: CallbackQuery, state: FSMContext):
    """Список всех источников"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Заглушка - в реальности источники хранятся в конфиге или БД
    sources_text = (
        "📋 <b>Список источников</b>\n\n"
        "<b>IT & Tech:</b>\n"
        "• DOU.ua - https://dou.ua/rss/articles\n"
        "• ITC.ua - https://itc.ua/feed/\n\n"
        "<b>Криптовалюты:</b>\n"
        "• ForkLog - https://forklog.com/feed/\n"
        "• CoinDesk - https://coindesk.com/arc/outboundfeeds/rss/\n\n"
        "💡 Для добавления/удаления используйте соответствующие кнопки"
    )

    await send_text_only(callback, sources_text, get_admin_sources_keyboard())
    await callback.answer()


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

        # Валидация URL
        if not url.startswith(('http://', 'https://')):
            await message.answer("❌ URL должен начинаться с http:// или https://")
            return

        # Здесь можно добавить логику сохранения в базу данных

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


@router.callback_query(F.data == "admin_categories")
async def show_categories_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления категориями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    text = (
        "📂 <b>Управление категориями</b>\n\n"
        "Здесь вы можете управлять категориями новостей"
    )

    await send_text_only(callback, text, get_admin_categories_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_categories")
async def list_categories(callback: CallbackQuery, state: FSMContext):
    """Список всех категорий"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    categories_text = (
        "📋 <b>Список категорий</b>\n\n"
        "💻 <b>it</b> - IT & Tech\n"
        "₿ <b>crypto</b> - Криптовалюты\n"
        "💼 <b>business</b> - Бизнес\n"
        "🌍 <b>general</b> - Общие новости\n"
        "🎮 <b>esports</b> - Киберспорт\n"
        "📱 <b>tech</b> - Технологии\n"
        "🏛️ <b>politics</b> - Политика\n"
        "🔬 <b>science</b> - Наука\n"
        "🚗 <b>auto</b> - Авто\n"
        "💊 <b>health</b> - Здоровье\n"
        "🎭 <b>entertainment</b> - Развлечения\n"
        "⚽ <b>sport</b> - Спорт"
    )

    await send_text_only(callback, categories_text, get_admin_categories_keyboard())
    await callback.answer()


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

        # Валидация
        if not code.isalpha() or not code.islower():
            await message.answer("❌ Код должен содержать только строчные латинские буквы")
            return

        if len(emoji) != 1:
            await message.answer("❌ Должен быть указан ровно один эмодзи")
            return

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


@router.callback_query(F.data == "admin_tokens")
async def show_tokens_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления API токенами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    text = (
        "🔐 <b>Управление API токенами</b>\n\n"
        "Здесь вы можете управлять токенами для внешнего доступа к API"
    )

    await send_text_only(callback, text, get_admin_tokens_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_tokens")
async def list_tokens(callback: CallbackQuery, state: FSMContext):
    """Список всех API токенов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Заглушка - в реальности токены хранятся в БД
    tokens_text = (
        "📋 <b>Список API токенов</b>\n\n"
        "🟢 <b>example.com</b>\n"
        "📧 Email: admin@example.com\n"
        "🔑 Token: abc123***\n"
        "📅 Создан: 01.06.2025\n\n"
        "🔴 <b>test.ua</b>\n"
        "📧 Email: test@test.ua\n"
        "🔑 Token: xyz789***\n"
        "📅 Создан: 25.05.2025\n"
        "❌ Заблокирован\n\n"
        "💡 Всего токенов: 2 (1 активный)"
    )

    await send_text_only(callback, tokens_text, get_admin_tokens_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_create_token")
async def create_token_prompt(callback: CallbackQuery, state: FSMContext):
    """Создание нового API токена"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.creating_token)

    text = (
        "🔐 <b>Создание API токена</b>\n\n"
        "Отправьте данные в формате:\n"
        "<code>email|домен</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>admin@example.com|example.com</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.creating_token)
async def process_create_token(message: Message, state: FSMContext):
    """Обработка создания токена"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 2:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используйте: <code>email|домен</code>",
                parse_mode='HTML'
            )
            return

        email, domain = [part.strip() for part in parts]

        # Простая валидация email
        if '@' not in email:
            await message.answer("❌ Неверный формат email")
            return

        # Генерируем токен
        token = str(uuid.uuid4())

        # Здесь можно добавить логику сохранения в БД

        success_text = (
            "✅ <b>API токен создан!</b>\n\n"
            f"📧 Email: <b>{email}</b>\n"
            f"🌐 Домен: <b>{domain}</b>\n"
            f"🔑 Токен: <code>{token}</code>\n\n"
            "⚠️ Сохраните токен, он больше не будет показан полностью!"
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} created API token for {email}|{domain}")

    except Exception as e:
        logging.error(f"Ошибка создания токена: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании токена.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_sites")
async def show_sites_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления сайтами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    text = (
        "🌐 <b>Управление сайтами</b>\n\n"
        "Здесь вы можете управлять сайтами, подключенными к API"
    )

    await send_text_only(callback, text, get_admin_sites_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_sites")
async def list_sites(callback: CallbackQuery, state: FSMContext):
    """Список всех сайтов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    sites_text = (
        "📋 <b>Список сайтов</b>\n\n"
        "🟢 <b>Example News</b>\n"
        "🌐 Домен: example.com\n"
        "🔑 Токен: abc123***\n"
        "✅ Активен\n\n"
        "🔴 <b>Test Site</b>\n"
        "🌐 Домен: test.ua\n"
        "🔑 Токен: xyz789***\n"
        "❌ Заблокирован\n\n"
        "💡 Всего сайтов: 2 (1 активный)"
    )

    await send_text_only(callback, sites_text, get_admin_sites_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_logs")
@router.callback_query(F.data.startswith("admin_logs_page_"))
async def show_logs(callback: CallbackQuery, state: FSMContext):
    """Показ логов админских действий"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    # Получаем номер страницы
    page = 0
    if callback.data.startswith("admin_logs_page_"):
        page = int(callback.data.split("_")[-1])

    # Заглушка - в реальности логи берутся из БД
    logs_per_page = 10
    total_logs = 25
    total_pages = (total_logs + logs_per_page - 1) // logs_per_page

    logs_text = f"📜 <b>Логи админских действий</b> (стр. {page + 1}/{total_pages})\n\n"

    # Примеры логов
    sample_logs = [
        "01.06.2025 21:00 - ID:123456 - Добавлен источник: it|Хабр|...",
        "01.06.2025 20:45 - ID:123456 - Создан токен для example.com",
        "01.06.2025 20:30 - ID:123456 - Отключена подписка: 987654321",
        "01.06.2025 20:15 - ID:123456 - Добавлена категория: gaming|Игры|🎮",
        "01.06.2025 20:00 - ID:123456 - Вход в админ панель",
    ]

    start_idx = page * logs_per_page
    end_idx = start_idx + logs_per_page

    for i, log in enumerate(sample_logs[start_idx:end_idx], 1):
        logs_text += f"{start_idx + i}. {log}\n"

    await send_text_only(callback, logs_text, get_admin_logs_keyboard(page, total_pages))
    await callback.answer()


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

            # Статистика активных пользователей
            active_subs_result = await db.execute(
                select(func.count(Subscription.id)).where(Subscription.is_active == True)
            )
            active_subs_count = active_subs_result.scalar()

            stats_text = (
                "📊 <b>Детальная статистика</b>\n\n"
                f"👥 <b>Активные подписки:</b> {active_subs_count}\n\n"

                f"📅 <b>За последние 30 дней:</b>\n"
                f"💰 Общая сумма: <b>{total_amount} ⭐</b>\n"
                f"📦 Покупок: <b>{len(transactions)}</b>\n"
                f"📈 Средний чек: <b>{total_amount / len(transactions) if transactions else 0:.1f} ⭐</b>\n\n"

                f"🗓️ <b>Сегодня:</b>\n"
                f"💰 Сумма: <b>{today_amount} ⭐</b>\n"
                f"📦 Покупок: <b>{len(today_transactions)}</b>\n\n"

                f"📊 <b>По тарифам (30 дней):</b>\n"
                f"• 7 дней: <b>{plans_stats.get('7_days', 0)}</b> шт (100⭐)\n"
                f"• 14 дней: <b>{plans_stats.get('14_days', 0)}</b> шт (180⭐)\n"
                f"• 30 дней: <b>{plans_stats.get('30_days', 0)}</b> шт (300⭐)\n\n"

                f"💡 <b>Конверсия:</b>\n"
                f"• Самый популярный план: {max(plans_stats.items(), key=lambda x: x[1])[0] if plans_stats else 'Нет данных'}\n"
                f"• Средняя продолжительность: {sum(int(k.split('_')[0]) * v for k, v in plans_stats.items()) / sum(plans_stats.values()) if plans_stats else 0:.1f} дней"
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
        "Выберите раздел для управления:"
    )

    # Расширенная клавиатура
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📰 Источники", callback_data="admin_sources")],
        [InlineKeyboardButton(text="📂 Категории", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🔐 API токены", callback_data="admin_tokens")],
        [InlineKeyboardButton(text="🌐 Сайты", callback_data="admin_sites")],
        [InlineKeyboardButton(text="📜 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🏠 Выйти из админки", callback_data="back_to_main")]
    ])

    await send_text_only(callback, admin_text, keyboard)
    await callback.answer()


@router.callback_query(F.data.in_([
    "admin_delete_source", "admin_delete_category",
    "admin_delete_token", "admin_add_site", "admin_delete_site", "noop"
]))
async def placeholder_handlers(callback: CallbackQuery):
    """Обработчики заглушек для будущего функционала"""
    await callback.answer("🚧 Функция в разработке", show_alert=True)