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
    try:
        await callback.message.delete()
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.warning(f"Failed to delete message: {e}")
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


def is_admin(user_id: int) -> bool:
    is_admin_user = user_id in settings.ADMIN_IDS

    logging.info(f"🔍 Admin check - User ID: {user_id}, Admin IDs: {settings.ADMIN_IDS}, Is admin: {is_admin_user}")

    if not is_admin_user:
        logging.warning(f"❌ Unauthorized admin access attempt by user {user_id}")
    else:
        logging.info(f"✅ Admin access granted to user {user_id}")

    return is_admin_user


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ You do not have access to the admin panel.")
        return

    await state.set_state(AdminStates.main_menu)

    admin_text = (
        "🛡️ <b>Admin Panel NewsBot</b>\n\n"
        f"👤 Administrator: {message.from_user.first_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        "Select a section to manage:"
    )

    await message.answer(
        admin_text,
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "admin_users")
@router.callback_query(F.data.startswith("admin_users_page_"))
async def show_users(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    page = 0
    if callback.data.startswith("admin_users_page_"):
        page = int(callback.data.split("_")[-1])

    try:
        async for db in get_db():
            count_result = await db.execute(
                select(func.count(Subscription.id)).where(Subscription.is_active == True)
            )
            total_count = count_result.scalar()

            users_per_page = 10
            total_pages = (total_count + users_per_page - 1) // users_per_page
            offset = page * users_per_page

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
                    "👥 <b>Users</b>\n\n❌ No active subscriptions",
                    get_admin_users_keyboard(page, total_pages)
                )
            else:
                users_text = f"👥 <b>Users</b> (page {page + 1}/{total_pages})\n\n"

                for subscription, user in subscriptions:
                    expires_date = subscription.expires_at.strftime('%d.%m.%Y %H:%M')
                    username = f"@{user.username}" if user.username else f"ID: {user.telegram_id}"

                    users_text += (
                        f"👤 {username}\n"
                        f"📦 Plan: {subscription.plan_type} days\n"
                        f"⏰ Until: {expires_date}\n\n"
                    )

                await send_text_only(callback, users_text, get_admin_users_keyboard(page, total_pages))
            break

    except Exception as e:
        logging.error(f"Error retrieving user list: {e}")
        await send_text_only(
            callback,
            "❌ Error retrieving user list",
            get_admin_back_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "admin_add_subscription")
async def add_subscription_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.adding_subscription)

    text = (
        "➕ <b>Add Subscription</b>\n\n"
        "Send the data in the format:\n"
        "<code>telegram_id|days</code>\n\n"
        "<b>Example:</b>\n"
        "<code>123456789|30</code>\n\n"
        "<b>Available plans:</b> 7, 14, 30 days"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_subscription)
async def process_add_subscription(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 2:
            await message.answer(
                "❌ <b>Invalid format!</b>\n\n"
                "Use: <code>telegram_id|days</code>",
                parse_mode='HTML'
            )
            return

        telegram_id, days = [part.strip() for part in parts]

        if not telegram_id.isdigit() or not days.isdigit():
            await message.answer("❌ ID and number of days must be numbers")
            return

        telegram_id = int(telegram_id)
        days = int(days)

        if days not in [7, 14, 30]:
            await message.answer("❌ Only plans available: 7, 14, 30 days")
            return

        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer(f"❌ User with ID {telegram_id} was not found in the system")
                return

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
                "✅ <b>Subscription added!</b>\n\n"
                f"👤 User: @{user.username or 'Unknown'}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"📦 Plan: {days} days\n"
                f"📅 Valid until: {expires_at.strftime('%d.%m.%Y %H:%M')}"
            )

            await message.answer(
                success_text,
                reply_markup=get_admin_back_keyboard(),
                parse_mode='HTML'
            )

            logging.info(f"Admin {message.from_user.id} added subscription: {telegram_id}|{days} days")
            break

    except Exception as e:
        logging.error(f"Error adding subscription: {e}")
        await message.answer(
            "❌ An error occurred while adding the subscription.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_disable_subscription")
async def disable_subscription_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.disabling_subscription)

    text = (
        "🗑 <b>Disable Subscription</b>\n\n"
        "Send the Telegram ID of the user:\n\n"
        "<b>Example:</b>\n"
        "<code>123456789</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.disabling_subscription)
async def process_disable_subscription(message: Message, state: FSMContext):
    try:
        telegram_id = message.text.strip()

        if not telegram_id.isdigit():
            await message.answer("❌ ID должен быть числом")
            return

        telegram_id = int(telegram_id)

        async for db in get_db():
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
                await message.answer(f"❌ No active subscription found for user {telegram_id}")
                return

            subscription, user = subscription_user

            subscription.is_active = False
            await db.commit()

            success_text = (
                "✅ <b>Subscription disabled!</b>\n\n"
                f"👤 User: @{user.username or 'Unknown'}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"📦 Previous plan: {subscription.plan_type} days"
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
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.searching_user)

    text = (
        "🔍 <b>Search for a User</b>\n\n"
        "Send the Telegram ID or username:\n\n"
        "<b>Examples:</b>\n"
        "<code>123456789</code>\n"
        "<code>@username</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.searching_user)
async def process_search_user(message: Message, state: FSMContext):
    try:
        search_query = message.text.strip()

        async for db in get_db():
            if search_query.startswith('@'):
                username = search_query[1:]
                result = await db.execute(
                    select(User, Subscription)
                    .outerjoin(Subscription)
                    .where(User.username == username)
                )
            elif search_query.isdigit():
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
                    f"❌ User <code>{search_query}</code> not found",
                    parse_mode='HTML'
                )
                return

            user = user_data[0][0]  # Первый пользователь
            subscriptions = [row[1] for row in user_data if row[1]]

            result_text = (
                f"👤 <b>User found</b>\n\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Not specified'}\n"
                f"📅 Registered: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
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
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    text = (
        "📰 <b>Manage Sources</b>\n\n"
        "Here you can manage news sources"
    )

    await send_text_only(callback, text, get_admin_sources_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_sources")
async def list_sources(callback: CallbackQuery, state: FSMContext):
    """Список всех источников"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    # Заглушка - в реальности источники хранятся в конфиге или БД
    sources_text = (
        "📋 <b>List of Sources</b>\n\n"
        "<b>IT & Tech:</b>\n"
        "• DOU.ua - https://dou.ua/rss/articles\n"
        "• ITC.ua - https://itc.ua/feed/\n\n"
        "<b>Cryptocurrencies:</b>\n"
        "• ForkLog - https://forklog.com/feed/\n"
        "• CoinDesk - https://coindesk.com/arc/outboundfeeds/rss/\n\n"
        "💡 To add/remove use corresponding buttons"
    )

    await send_text_only(callback, sources_text, get_admin_sources_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_add_source")
async def add_news_source(callback: CallbackQuery, state: FSMContext):
    """Add a new news source"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.adding_source)

    text = (
        "📰 <b>Add a New Source</b>\n\n"
        "Send the data in the format:\n"
        "<code>category|name|url</code>\n\n"
        "<b>Example:</b>\n"
        "<code>it|Habr|https://habr.com/ru/rss/hub/programming/</code>\n\n"
        "<b>Available categories:</b>\n"
        "• it, crypto, business, general\n"
        "• esports, tech, politics, science\n"
        "• auto, health, entertainment, sport"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_source)
async def process_add_source(message: Message, state: FSMContext):
    """Process adding a source"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 3:
            await message.answer(
                "❌ <b>Invalid format!</b>\n\n"
                "Use: <code>category|name|url</code>",
                parse_mode='HTML'
            )
            return

        category, name, url = [part.strip() for part in parts]

        # URL validation
        if not url.startswith(('http://', 'https://')):
            await message.answer("❌ URL must start with http:// or https://")
            return

        # Here you can add logic to save to the database

        success_text = (
            "✅ <b>Source added!</b>\n\n"
            f"📂 Category: <b>{category}</b>\n"
            f"📰 Name: <b>{name}</b>\n"
            f"🔗 URL: <code>{url}</code>\n\n"
            "The source will be active during the next news update."
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} added source: {category}|{name}|{url}")

    except Exception as e:
        logging.error(f"Error adding source: {e}")
        await message.answer(
            "❌ An error occurred while adding the source.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_categories")
async def show_categories_menu(callback: CallbackQuery, state: FSMContext):
    """Categories management menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    text = (
        "📂 <b>Categories Management</b>\n\n"
        "Here you can manage news categories"
    )

    await send_text_only(callback, text, get_admin_categories_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_categories")
async def list_categories(callback: CallbackQuery, state: FSMContext):
    """List of all categories"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    categories_text = (
        "📋 <b>List of Categories</b>\n\n"
        "💻 <b>it</b> - IT & Tech\n"
        "₿ <b>crypto</b> - Cryptocurrencies\n"
        "💼 <b>business</b> - Business\n"
        "🌍 <b>general</b> - General news\n"
        "🎮 <b>esports</b> - Esports\n"
        "📱 <b>tech</b> - Technology\n"
        "🏛️ <b>politics</b> - Politics\n"
        "🔬 <b>science</b> - Science\n"
        "🚗 <b>auto</b> - Auto\n"
        "💊 <b>health</b> - Health\n"
        "🎭 <b>entertainment</b> - Entertainment\n"
        "⚽ <b>sport</b> - Sport"
    )

    await send_text_only(callback, categories_text, get_admin_categories_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_add_category")
async def add_category(callback: CallbackQuery, state: FSMContext):
    """Add a new category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.adding_category)

    text = (
        "📂 <b>Add a New Category</b>\n\n"
        "Send the data in the format:\n"
        "<code>code|name|emoji</code>\n\n"
        "<b>Example:</b>\n"
        "<code>gaming|Games|🎮</code>\n\n"
        "<b>Requirements:</b>\n"
        "• Code must be Latin letters only\n"
        "• Name in English\n"
        "• One emoji"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.adding_category)
async def process_add_category(message: Message, state: FSMContext):
    """Process adding a category"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 3:
            await message.answer(
                "❌ <b>Invalid format!</b>\n\n"
                "Use: <code>code|name|emoji</code>",
                parse_mode='HTML'
            )
            return

        code, name, emoji = [part.strip() for part in parts]

        # Validation
        if not code.isalpha() or not code.islower():
            await message.answer("❌ Code must contain only lowercase Latin letters")
            return

        if len(emoji) != 1:
            await message.answer("❌ Exactly one emoji must be provided")
            return

        # Here you can add logic to save the category

        success_text = (
            "✅ <b>Category added!</b>\n\n"
            f"🔤 Code: <b>{code}</b>\n"
            f"📝 Name: <b>{name}</b>\n"
            f"😀 Emoji: {emoji}\n\n"
            "Don't forget to add sources for the new category!"
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} added category: {code}|{name}|{emoji}")

    except Exception as e:
        logging.error(f"Error adding category: {e}")
        await message.answer(
            "❌ An error occurred while adding the category.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_tokens")
async def show_tokens_menu(callback: CallbackQuery, state: FSMContext):
    """API Tokens management menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    text = (
        "🔐 <b>Manage API Tokens</b>\n\n"
        "Here you can manage API tokens for external access"
    )

    await send_text_only(callback, text, get_admin_tokens_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_tokens")
async def list_tokens(callback: CallbackQuery, state: FSMContext):
    """List of all API tokens"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    # Placeholder - in reality tokens are stored in DB
    tokens_text = (
        "📋 <b>List of API Tokens</b>\n\n"
        "🟢 <b>example.com</b>\n"
        "📧 Email: admin@example.com\n"
        "🔑 Token: abc123***\n"
        "📅 Created: 01.06.2025\n\n"
        "🔴 <b>test.ua</b>\n"
        "📧 Email: test@test.ua\n"
        "🔑 Token: xyz789***\n"
        "📅 Created: 25.05.2025\n"
        "❌ Blocked\n\n"
        "💡 Total tokens: 2 (1 active)"
    )

    await send_text_only(callback, tokens_text, get_admin_tokens_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_create_token")
async def create_token_prompt(callback: CallbackQuery, state: FSMContext):
    """Create a new API token"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.creating_token)

    text = (
        "🔐 <b>Create API Token</b>\n\n"
        "Send the data in the format:\n"
        "<code>email|domain</code>\n\n"
        "<b>Example:</b>\n"
        "<code>admin@example.com|example.com</code>"
    )

    await send_text_only(callback, text, get_admin_back_keyboard())
    await callback.answer()


@router.message(AdminStates.creating_token)
async def process_create_token(message: Message, state: FSMContext):
    """Process token creation"""
    try:
        parts = message.text.strip().split('|')
        if len(parts) != 2:
            await message.answer(
                "❌ <b>Invalid format!</b>\n\n"
                "Use: <code>email|domain</code>",
                parse_mode='HTML'
            )
            return

        email, domain = [part.strip() for part in parts]

        # Simple email validation
        if '@' not in email:
            await message.answer("❌ Invalid email format")
            return

        # Generate token
        token = str(uuid.uuid4())

        # Here you can add logic to save to the database

        success_text = (
            "✅ <b>API Token created!</b>\n\n"
            f"📧 Email: <b>{email}</b>\n"
            f"🌐 Domain: <b>{domain}</b>\n"
            f"🔑 Token: <code>{token}</code>\n\n"
            "⚠️ Save the token, it will not be shown fully again!"
        )

        await message.answer(
            success_text,
            reply_markup=get_admin_back_keyboard(),
            parse_mode='HTML'
        )

        logging.info(f"Admin {message.from_user.id} created API token for {email}|{domain}")

    except Exception as e:
        logging.error(f"Error creating token: {e}")
        await message.answer(
            "❌ An error occurred while creating the token.",
            reply_markup=get_admin_back_keyboard()
        )


@router.callback_query(F.data == "admin_sites")
async def show_sites_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    text = (
        "🌐 <b>Manage Sites</b>\n\n"
        "Here you can manage sites connected to the API"
    )

    await send_text_only(callback, text, get_admin_sites_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_list_sites")
async def list_sites(callback: CallbackQuery, state: FSMContext):
    """List of all sites"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    sites_text = (
        "📋 <b>List of Sites</b>\n\n"
        "🟢 <b>Example News</b>\n"
        "🌐 Domain: example.com\n"
        "🔑 Token: abc123***\n"
        "✅ Active\n\n"
        "🔴 <b>Test Site</b>\n"
        "🌐 Domain: test.ua\n"
        "🔑 Token: xyz789***\n"
        "❌ Blocked\n\n"
        "💡 Total sites: 2 (1 active)"
    )

    await send_text_only(callback, sites_text, get_admin_sites_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_logs")
@router.callback_query(F.data.startswith("admin_logs_page_"))
async def show_logs(callback: CallbackQuery, state: FSMContext):
    """Show admin action logs"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    # Get page number
    page = 0
    if callback.data.startswith("admin_logs_page_"):
        page = int(callback.data.split("_")[-1])

    # Placeholder - in reality logs are taken from the database
    logs_per_page = 10
    total_logs = 25
    total_pages = (total_logs + logs_per_page - 1) // logs_per_page

    logs_text = f"📜 <b>Admin action logs</b> (page {page + 1}/{total_pages})\n\n"

    # Example logs (should be translated for demo)
    sample_logs = [
        "01.06.2025 21:00 - ID:123456 - Source added: it|Habr|...",
        "01.06.2025 20:45 - ID:123456 - Token created for example.com",
        "01.06.2025 20:30 - ID:123456 - Subscription disabled: 987654321",
        "01.06.2025 20:15 - ID:123456 - Category added: gaming|Games|🎮",
        "01.06.2025 20:00 - ID:123456 - Admin panel login",
    ]

    start_idx = page * logs_per_page
    end_idx = start_idx + logs_per_page

    for i, log in enumerate(sample_logs[start_idx:end_idx], 1):
        logs_text += f"{start_idx + i}. {log}\n"

    await send_text_only(callback, logs_text, get_admin_logs_keyboard(page, total_pages))
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def show_purchase_stats(callback: CallbackQuery, state: FSMContext):
    """View purchase statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
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

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_transactions = [t for t in transactions if t.created_at >= today_start]

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

            active_subs_result = await db.execute(
                select(func.count(Subscription.id)).where(Subscription.is_active == True)
            )
            active_subs_count = active_subs_result.scalar()

            stats_text = (
                "📊 <b>Detailed Statistics</b>\n\n"
                f"👥 <b>Active subscriptions:</b> {active_subs_count}\n\n"

                f"📅 <b>Last 30 days:</b>\n"
                f"💰 Total amount: <b>{total_amount} ⭐</b>\n"
                f"📦 Purchases: <b>{len(transactions)}</b>\n"
                f"📈 Average check: <b>{total_amount / len(transactions) if transactions else 0:.1f} ⭐</b>\n\n"

                f"🗓️ <b>Today:</b>\n"
                f"💰 Amount: <b>{today_amount} ⭐</b>\n"
                f"📦 Purchases: <b>{len(today_transactions)}</b>\n\n"

                f"📊 <b>By plan (30 days):</b>\n"
                f"• 7 days: <b>{plans_stats.get('7_days', 0)}</b> pcs (100⭐)\n"
                f"• 14 days: <b>{plans_stats.get('14_days', 0)}</b> pcs (180⭐)\n"
                f"• 30 days: <b>{plans_stats.get('30_days', 0)}</b> pcs (300⭐)\n\n"

                f"💡 <b>Conversion:</b>\n"
                f"• Most popular plan: {max(plans_stats.items(), key=lambda x: x[1])[0] if plans_stats else 'No data'}\n"
                f"• Average duration: {sum(int(k.split('_')[0]) * v for k, v in plans_stats.items()) / sum(plans_stats.values()) if plans_stats else 0:.1f} days"
            )

            await send_text_only(callback, stats_text, get_admin_back_keyboard())
            break

    except Exception as e:
        logging.error(f"Error retrieving statistics: {e}")
        await send_text_only(
            callback,
            "❌ Error retrieving statistics",
            get_admin_back_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Return to the main admin menu"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    await state.set_state(AdminStates.main_menu)

    admin_text = (
        "🛡️ <b>Admin Panel NewsBot</b>\n\n"
        f"👤 Administrator: {callback.from_user.first_name}\n"
        f"🆔 ID: <code>{callback.from_user.id}</code>\n\n"
        "Select a section to manage:"
    )

    # Extended keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📰 Sources", callback_data="admin_sources")],
        [InlineKeyboardButton(text="📂 Categories", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🔐 API Tokens", callback_data="admin_tokens")],
        [InlineKeyboardButton(text="🌐 Sites", callback_data="admin_sites")],
        [InlineKeyboardButton(text="📜 Logs", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🏠 Exit admin panel", callback_data="back_to_main")]
        
    ])

    await send_text_only(callback, admin_text, keyboard)
    await callback.answer()


@router.callback_query(F.data.in_([
    "admin_delete_source", "admin_delete_category",
    "admin_delete_token", "admin_add_site", "admin_delete_site", "noop"
]))
async def placeholder_handlers(callback: CallbackQuery):
    """Placeholder handlers for future functionality"""
    await callback.answer("🚧 Feature in development", show_alert=True)