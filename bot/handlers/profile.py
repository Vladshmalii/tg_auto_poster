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
        logging.warning(f"Failed to delete message: {e}")
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


def format_subscription_status(subscription):
    if not subscription:
        return "❌ No subscription"

    if not subscription.is_active:
        return "🔴 Subscription inactive"

    expires_at = subscription.expires_at
    now = datetime.utcnow()

    if expires_at <= now:
        return "⏰ Subscription expired"

    time_left = expires_at - now
    days_left = time_left.days
    hours_left = time_left.seconds // 3600

    if days_left > 0:
        return f"🟢 Active ({days_left} days)"
    elif hours_left > 0:
        return f"🟡 Active ({hours_left} hours)"
    else:
        return "🔴 Expires today"


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
        'crypto': '₿ Cryptocurrencies',
        'business': '💼 Business',
        'general': '🌍 General news',
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
        'casual': '😎 Conversational',
        'meme': '🤪 Meme'
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

    channels_text = '\n'.join([f"• {ch}" for ch in channels]) if channels else "❌ Not selected"

    category_names = [get_category_emoji_name(cat) for cat in categories]
    categories_text = '\n'.join([f"• {name}" for name in category_names]) if categories else "❌ Not selected"

    style_text = get_style_emoji_name(style) if style else "❌ Not selected"

    schedule_names = {
        1: "Once a day (09:00)",
        2: "Twice a day (09:00, 21:00)",
        3: "Three times a day (09:00, 15:00, 21:00)"
    }
    schedule_text = schedule_names.get(frequency, "❌ Не настроено")

    return f"""📋 <b>Summary of auto-posting settings</b>

📺 <b>Channels:</b>
{channels_text}

📂 <b>Categories:</b>
{categories_text}

🎨 <b>Style:</b> {style_text}

⏰ <b>Schedule:</b> {schedule_text}

💡 Check the settings before saving"""


async def get_user_post_stats(db: AsyncSession, user_id: int, channel_id: str = None):
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
                    "❌ User not found in the system",
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

            posts_today = await get_user_post_stats(db, user.id)

            total_spent = sum(payment.amount for payment in payments)
            total_payments = len(payments)
            last_payment = payments[0] if payments else None

            profile_text = (
                f"👤 <b>My Profile</b>\n\n"
                f"🆔 ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Not set'}\n"
                f"📅 Registered: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            )

            if subscription:
                emoji = get_subscription_emoji(subscription.plan_type)
                status = format_subscription_status(subscription)
                expires_date = subscription.expires_at.strftime('%d.%m.%Y %H:%M')

                profile_text += (
                    f"📦 <b>Current Subscription</b>\n"
                    f"{emoji} Plan: {subscription.plan_type} days\n"
                    f"📊 Status: {status}\n"
                    f"⏰ Valid until: {expires_date}\n\n"
                )
            else:
                profile_text += (
                    f"📦 <b>Subscription</b>\n"
                    f"❌ No active subscription\n"
                    f"💡 Purchase a subscription to access features\n\n"
                )

            profile_text += (
                f"📊 <b>Post Statistics</b>\n"
                f"📈 Sent today: {posts_today}/3\n"
                f"⏰ Limit resets at 00:00\n\n"
            )

            if payments:
                last_payment_date = last_payment.created_at.strftime('%d.%m.%Y')
                profile_text += (
                    f"💳 <b>Payment Statistics</b>\n"
                    f"💰 Total spent: {total_spent} ⭐\n"
                    f"📊 Number of purchases: {total_payments}\n"
                    f"📅 Last payment: {last_payment_date}\n\n"
                )
            else:
                profile_text += (
                    f"🎁 <b>Gift Subscriptions</b>\n"
                    f"💡 You have the opportunity to get a gift subscription!\n"
                    f"🎯 Participate in giveaways and promotions\n"
                    f"🔔 Follow our channel for updates\n\n"
                )

            if subscription_history:
                profile_text += f"📜 <b>Subscription History</b>\n"
                for i, sub in enumerate(subscription_history[:3], 1):
                    emoji = get_subscription_emoji(sub.plan_type)
                    status_emoji = "🟢" if sub.is_active else "🔴"
                    created_date = sub.created_at.strftime('%d.%m.%Y')
                    profile_text += f"{status_emoji} {emoji} {sub.plan_type}d - {created_date}\n"

                if len(subscription_history) > 3:
                    profile_text += f"... and {len(subscription_history) - 3} more\n"

            await send_text_only(callback, profile_text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error retrieving profile: {e}")
        await send_text_only(
            callback,
            "❌ Error loading profile",
            get_main_menu_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "manual_post")
async def show_manual_post_menu(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                    "📤 <b>Manual Post Sending</b>\n\n"
                    "❌ <b>An active subscription is required</b>\n\n"
                    "You need an active subscription to send posts manually.\n\n"
                    "💎 Purchase a subscription to access this feature"
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
                    "📤 <b>Manual Post Sending</b>\n\n"
                    "❌ <b>Autoposting is not configured</b>\n\n"
                    "First, set up autoposting in the 'Posting Settings' section.\n\n"
                    "💡 After setup, manual posting features will appear here"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            text = (
                "📤 <b>Manual Post Sending</b>\n\n"
                "Choose an action:\n\n"
                "🚀 <b>Send now</b> - send a post immediately\n"
                "⏰ <b>Schedule</b> - send at a specified time\n\n"
                f"📺 <b>Channel:</b> {setting.channel_id}\n"
                f"📂 <b>Category:</b> {get_category_emoji_name(setting.category)}\n"
                f"🎨 <b>Style:</b> {get_style_emoji_name(setting.style)}\n\n"
                f"📊 <b>Post limit:</b> {posts_today}/3 today\n"
            )

            if posts_today >= 3:
                text += "⚠️ <b>Limit reached!</b> Try again tomorrow"

            from bot.keyboards import get_manual_post_keyboard
            await send_text_only(callback, text, get_manual_post_keyboard(posts_today >= 3))
            break

    except Exception as e:
        logging.error(f"Error showing manual post menu: {e}")
        await send_text_only(callback, "❌ An error occurred", get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "manual_send_now")
async def manual_send_now(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                await callback.answer("❌ Auto-posting settings not found", show_alert=True)
                return

            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            if posts_today >= 3:
                await callback.answer(
                    f"❌ Limit reached! {posts_today}/3 posts sent today",
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
                "🚀 <b>Post is being sent!</b>\n\n"
                f"📺 Channel: {setting.channel_id}\n"
                f"📂 Category: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Style: {get_style_emoji_name(setting.style)}\n"
                f"📊 Will be: {posts_today + 1}/3 posts today\n\n"
                "⏳ The post will be published within a minute"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error sending manual post: {e}")
        await callback.answer("❌ Error sending post", show_alert=True)


@router.callback_query(F.data == "manual_schedule")
async def manual_schedule_setup(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                await callback.answer("❌ Autoposting settings not found", show_alert=True)
                return

            posts_today = await get_user_post_stats(db, user.id, setting.channel_id)

            await state.set_state(UserStates.scheduling_manual_post)

            text = (
                "⏰ <b>Schedule a post</b>\n\n"
                "Send the time in HH:MM format\n"
                "For example: <code>15:23</code> or <code>09:00</code>\n\n"
                "📅 If the time has already passed today, the post will be sent tomorrow\n"
                f"📊 Current limit: {posts_today}/3 posts today\n\n"
                "💡 Enter the time:"
            )

            from bot.keyboards import get_manual_schedule_cancel_keyboard
            await send_text_only(callback, text, get_manual_schedule_cancel_keyboard())
            break

    except Exception as e:
        logging.error(f"Error scheduling setup: {e}")
        await callback.answer("❌ Error setting up scheduling", show_alert=True)

    await callback.answer()


@router.message(UserStates.scheduling_manual_post)
async def process_schedule_time(message: Message, state: FSMContext):
    time_input = message.text.strip()

    try:
        hour, minute = map(int, time_input.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "❌ <b>Invalid time format!</b>\n\n"
            "Use the HH:MM format (for example: 15:23)",
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
                await message.answer("❌ User not found")
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
                await message.answer("❌ Autoposting settings not found")
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
                day_text = "tomorrow"
            else:
                day_text = "today"

            text = (
                "✅ <b>Post scheduled!</b>\n\n"
                f"⏰ Send time: {time_input} ({day_text})\n"
                f"📺 Channel: {setting.channel_id}\n"
                f"📂 Category: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Style: {get_style_emoji_name(setting.style)}\n\n"
                "🔔 The post will be sent automatically at the specified time\n"
                "⚠️ The 3 posts per day limit applies"
            )

            await message.answer(text, reply_markup=get_profile_keyboard(), parse_mode='HTML')
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Error scheduling post: {e}")
        await message.answer("❌ Error scheduling post")


@router.callback_query(F.data == "profile_subscription")
async def show_subscription_details(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
                return

            subscriptions_result = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id
                ).order_by(Subscription.created_at.desc())
            )
            subscriptions = subscriptions_result.scalars().all()

            if not subscriptions:
                text = (
                    "📦 <b>Subscriptions</b>\n\n"
                    "❌ You have no subscriptions yet\n\n"
                    "💡 Purchase a subscription to access:\n"
                    "• Automatic news posting\n"
                    "• Category and style selection\n"
                    "• Schedule setup\n"
                    "• Up to 3 posts per day"
                )
            else:
                text = "📦 <b>Subscription Details</b>\n\n"

                for i, sub in enumerate(subscriptions, 1):
                    emoji = get_subscription_emoji(sub.plan_type)
                    status = format_subscription_status(sub)
                    created_date = sub.created_at.strftime('%d.%m.%Y %H:%M')
                    expires_date = sub.expires_at.strftime('%d.%m.%Y %H:%M')

                    text += (
                        f"{i}. {emoji} <b>Subscription {sub.plan_type} days</b>\n"
                        f"📊 Status: {status}\n"
                        f"📅 Created: {created_date}\n"
                        f"⏰ Expires: {expires_date}\n"
                    )

                    if sub.is_active:
                        now = datetime.utcnow()
                        if sub.expires_at > now:
                            time_left = sub.expires_at - now
                            days_left = time_left.days
                            hours_left = time_left.seconds // 3600

                            if days_left > 0:
                                text += f"⏳ Remaining: {days_left} days {hours_left} hours\n"
                            else:
                                text += f"⏳ Remaining: {hours_left} hours\n"

                    text += "\n"

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error retrieving subscription details: {e}")
        await send_text_only(
            callback,
            "❌ Error loading data",
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
                await callback.answer("❌ User not found", show_alert=True)
                return

            payments_result = await db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id
                ).order_by(Transaction.created_at.desc()).limit(10)
            )
            payments = payments_result.scalars().all()

            if not payments:
                text = (
                    "💳 <b>Payment History</b>\n\n"
                    "❌ No payments yet\n\n"
                    "💡 After your first purchase, your transaction history will appear here"
                )
            else:
                total_spent = sum(p.amount for p in payments)
                text = (
                    f"💳 <b>Payment History</b>\n\n"
                    f"💰 Total spent: <b>{total_spent} ⭐</b>\n"
                    f"📊 Number of payments: <b>{len(payments)}</b>\n\n"
                )

                for i, payment in enumerate(payments, 1):
                    payment_date = payment.created_at.strftime('%d.%m.%Y %H:%M')
                    status_emoji = "✅" if payment.status == "completed" else "❌"

                    plan_type = "unknown"
                    if payment.amount == 100:
                        plan_type = "7 days"
                    elif payment.amount == 180:
                        plan_type = "14 days"
                    elif payment.amount == 300:
                        plan_type = "30 days"

                    text += (
                        f"{i}. {status_emoji} {plan_type} — {payment.amount} ⭐ — {payment_date}\n"
                        f"📦 Plan: {plan_type}\n"
                        f"📅 Date: {payment_date}\n"
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
                await callback.answer("❌ User not found", show_alert=True)
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
                [get_category_emoji_name(cat) for cat in categories]) if categories else 'Not selected'
            styles_text = ', '.join([get_style_emoji_name(style) for style in styles]) if styles else 'Not configured'

            posts_today = await get_user_post_stats(db, user.id)

            text = (
                f"⚙️ <b>Profile Settings</b>\n\n"
                f"👤 <b>Basic Information:</b>\n"
                f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
                f"👤 Username: @{user.username or 'Not set'}\n"
                f"🌐 Language: {user.language}\n"
                f"📅 Registered: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📊 <b>Statistics:</b>\n"
                f"📈 Posts today: {posts_today}/3\n"
                f"⏰ Limit resets at 00:00\n\n"
                f"🔔 <b>Notifications:</b>\n"
                f"📱 Telegram notifications: Enabled\n"
                f"📧 Email notifications: Not configured\n\n"
                f"🤖 <b>Autoposting:</b>\n"
                f"📺 Connected channels: {channels_count}\n"
                f"📰 Active categories: {categories_text}\n"
                f"🎨 Post style: {styles_text}\n\n"
                f"💡 <b>Tip:</b> Set up autoposting after purchasing a subscription"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error receiving settings: {e}")
        await send_text_only(
            callback,
            "❌ An error occurred while loading settings",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "profile_help")
async def show_profile_help(callback: CallbackQuery, state: FSMContext):
    text = (
        "❓ <b>Profile Help</b>\n\n"

        "<b>📦 Subscription</b>\n"
        "• 🥉 7 days - basic plan\n"
        "• 🥈 14 days - popular plan\n"
        "• 🥇 30 days - maximum plan\n\n"

        "<b>📊 Post Limits:</b>\n"
        "• Maximum 3 posts per channel per day\n"
        "• Limit resets at 00:00 MSK\n"
        "• Both autoposting and manual posts count\n\n"

        "<b>🔴 Subscription Statuses:</b>\n"
        "• 🟢 Active - subscription is working\n"
        "• 🟡 Expiring - less than a day left\n"
        "• 🔴 Inactive - subscription expired\n"
        "• ❌ No subscription - not purchased\n\n"

        "<b>💳 Payments:</b>\n"
        "• ✅ Completed - payment successful\n"
        "• ❌ Error - payment issue\n\n"

        "<b>⚙️ Settings:</b>\n"
        "• Telegram ID - your unique identifier\n"
        "• Username - your Telegram username\n"
        "• Autoposting - news posting settings\n\n"

        "🆘 <b>Need help?</b>\n"
        "Contact support via the main menu"
    )

    await send_text_only(callback, text, get_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile_gifts")
async def show_gift_subscriptions(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎁 <b>Gift Subscriptions</b>\n\n"

        "🌟 <b>How to get a free subscription?</b>\n\n"

        "🎯 <b>Ways to get it:</b>\n"
        "• 🎲 Participate in giveaways\n"
        "• 🎈 Holiday promotions\n"
        "• 👥 Invite friends (referral program)\n"
        "• ⭐ Be active in the community\n"
        "• 📝 Leave feedback and suggestions\n\n"

        "🏆 <b>Current offers:</b>\n"
        "• 🎊 Invite 3 friends - get 7 days free\n"
        "• 📱 Share on social media - join the giveaway\n"
        "• 💬 Leave a review - get bonuses\n\n"

        "📢 <b>Stay tuned for news:</b>\n"
        "• Telegram channel: @newsbot_channel\n"
        "• Notifications about new offers\n\n"

        "💡 <b>Tip:</b> Enable notifications so you don't miss promotions!"
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
                await callback.answer("❌ User not found", show_alert=True)
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
                    "⚙️ <b> Auto-posting Settings </b>\n\n"
                    "❌ <b> Active Subscription Required </b>\n\n"
                    "To configure automatic posting, you need to:\n"
                    "💎 Purchase a subscription\n"
                    "📺 Add the bot to your channel as an administrator\n"
                    "📂 Choose news categories\n"
                    "🎨 Customize post style\n\n"
                    "💡 Purchase a subscription to access the settings"
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
                    "⚙️ <b>Autoposting Settings</b>\n\n"
                    "✅ <b>Autoposting is configured and active</b>\n\n"
                )

                if channels:
                    text += f"📺 <b>Channels ({len(channels)}):</b>\n"
                    for channel in channels[:3]:
                        text += f"• {channel}\n"
                    if len(channels) > 3:
                        text += f"... and {len(channels) - 3} more\n"
                    text += "\n"

                if categories:
                    text += f"📂 <b>Categories ({len(categories)}):</b>\n"
                    for category in categories[:4]:
                        text += f"• {get_category_emoji_name(category)}\n"
                    if len(categories) > 4:
                        text += f"... and {len(categories) - 4} more\n"
                    text += "\n"

                if styles:
                    style_names = [get_style_emoji_name(style) for style in styles]
                    text += f"🎨 <b>Style:</b> {', '.join(style_names)}\n\n"

                if frequencies:
                    freq_text = ', '.join([f"{f} times per day" for f in frequencies])
                    text += f"⏰ <b>Schedule:</b> {freq_text}\n\n"

                text += "💡 Choose an action to manage settings"
            else:
                text = (
                    "⚙️ <b>Autoposting Settings</b>\n\n"
                    "📊 <b>Status:</b> ✅ Subscription active\n\n"
                    "❌ <b>Autoposting not configured</b>\n\n"
                    "To get started, you need to:\n"
                    "📺 Add channels\n"
                    "📂 Select news categories\n"
                    "🎨 Configure post style\n"
                    "⏰ Set up schedule\n\n"
                    "💡 Create a new autoposting setting"
                )

                from bot.keyboards import get_autopost_setup_keyboard
                await send_text_only(callback, text, get_autopost_setup_keyboard())
                break

    except Exception as e:
        logging.error(f"Error getting posting settings: {e}")
        await send_text_only(
            callback,
            "❌ An error occurred while loading settings",
            get_profile_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "autopost_new", UserStates.autopost_setup)
async def start_new_autopost_setup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.adding_channel)
    await state.update_data(current_step='channels', step_number=1)

    text = (
        "📺 <b>Step 1/4: Channel setup</b>\n\n"
        "📋 <b>Instructions:</b>\n"
        "1️⃣ Add the bot to your channel as an admin\n"
        "2️⃣ Grant 'Post Messages' permission\n"
        "3️⃣ Click 'Add Channel' and send the username\n\n"
        "💡 You can add multiple channels\n\n"
        "📺 <b>Added channels:</b>\n❌ None yet"
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
                "📺 <b>Step 1/4: Channel setup</b>\n\n"
                "📋 <b>Instructions:</b>\n"
                "1️⃣ Add the bot to your channel as an admin\n"
                "2️⃣ Grant 'Post Messages' permission\n"
                "3️⃣ Click 'Add Channel' and send the username\n\n"
                "💡 You can add multiple channels\n\n"
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
                f"❌ <b>Channel {channel_username} not found</b>\n\n"
                "Check that the channel username is correct.",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                f"❌ <b>Error checking channel</b>\n\n"
                "Make sure the bot is added to the channel as an administrator.",
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
            await callback.answer("❌ Add at least one channel!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_categories)
        await state.update_data(current_step='categories', step_number=2)

        text = (
            "📂 <b>Step 2/4: Category Selection</b>\n\n"
            "Select news categories for autoposting:\n\n"
            "💡 <b>Tip:</b> Choose 2-4 categories for better quality\n\n"
            "🎯 <b>Selected categories:</b> None selected yet"
        )

        from bot.keyboards import get_category_selection_keyboard_new
        await send_text_only(callback, text, get_category_selection_keyboard_new())

    elif current_step == 'categories':
        categories = data.get('categories', [])
        if not categories:
            await callback.answer("❌ Select at least one category!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_style)
        await state.update_data(current_step='style', step_number=3)

        text = (
            "🎨 <b>Step 3/4: Style Selection</b>\n\n"
            "Select post style:\n\n"
            "🎩 <b>Formal</b> - business style\n"
            "😎 <b>Casual</b> - friendly tone\n"
            "🤪 <b>Meme</b> - humorous style\n\n"
            "🎯 <b>Selected style:</b> Not selected"
        )

        from bot.keyboards import get_style_selection_keyboard_new
        await send_text_only(callback, text, get_style_selection_keyboard_new())

    elif current_step == 'style':
        style = data.get('style', '')
        if not style:
            await callback.answer("❌ Select a style!", show_alert=True)
            return

        await state.set_state(UserStates.selecting_schedule)
        await state.update_data(current_step='schedule', step_number=4)

        text = (
            "⏰ <b>Step 4/4: Schedule Setup</b>\n\n"
            "Choose posting frequency:\n\n"
            "• 1️⃣ <b>1 time per day</b> - for small channels\n"
            "• 2️⃣ <b>2 times per day</b> - optimal choice\n"
            "• 3️⃣ <b>3 times per day</b> - for active channels\n\n"
            "🎯 <b>Selected schedule:</b> Not configured"
        )

        from bot.keyboards import get_schedule_selection_keyboard_new
        await send_text_only(callback, text, get_schedule_selection_keyboard_new())

    elif current_step == 'schedule':
        frequency = data.get('frequency', 0)
        if not frequency:
            await callback.answer("❌ Select a schedule!", show_alert=True)
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
    style = data.get('style', '')
    categories = data.get('categories', [])

    if category in categories:
        categories.remove(category)
        status = "removed"
    else:
        categories.append(category)
        status = "added"

    await state.update_data(categories=categories)

    selected_text = ', '.join([get_category_emoji_name(cat) for cat in categories]) if categories else "Not selected yet"

    text = (
        "📂 <b>Step 2/4: Select categories</b>\n\n"
        "Select news categories for autoposting:\n\n"
        "💡 <b>Tip:</b> Choose 2-4 categories for the best quality\n\n"
        f"🎯 <b>Selected categories:</b> {selected_text}"
    )

    from bot.keyboards import get_category_selection_keyboard_new
    await callback.message.edit_text(
        text,
        reply_markup=get_category_selection_keyboard_new(categories),
        parse_mode='HTML'
    )

    await callback.answer(f"Category {status}")

    await state.update_data(style=style)

    style_text = get_style_emoji_name(style)

    text = (
        "🎨 <b>Step 3/4: Style Selection</b>\n\n"
        "Select post style:\n\n"
        "🎩 <b>Formal</b> - business style\n"
        "😎 <b>Conversational</b> - friendly tone\n"
        "🤪 <b>Meme</b> - humorous style\n\n"
        f"🎯 <b>Selected style:</b> {style_text}"
    )

    from bot.keyboards import get_style_selection_keyboard_new
    await callback.message.edit_text(
        text,
        reply_markup=get_style_selection_keyboard_new(style),
        parse_mode='HTML'
    )

    await callback.answer(f"Style set: {style_text}")


@router.callback_query(F.data.startswith("autopost_set_schedule_"))
async def set_schedule_new(callback: CallbackQuery, state: FSMContext):
    frequency = int(callback.data.replace("autopost_set_schedule_", ""))

    await state.update_data(frequency=frequency)

    schedule_names = {
        1: "1 time per day (09:00)",
        2: "2 times per day (09:00, 21:00)",
        3: "3 times per day (09:00, 15:00, 21:00)"
    }

    schedule_text = schedule_names.get(frequency, "")

    text = (
        "⏰ <b>Step 4/4: Set schedule</b>\n\n"
        "Select post frequency:\n\n"
        "• 1️⃣ <b>1 time per day</b> - for small channels\n"
        "• 2️⃣ <b>2 times per day</b> - optimal\n"
        "• 3️⃣ <b>3 times per day</b> - for active channels\n\n"
        f"🎯 <b>Selected schedule:</b> {schedule_text}"
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
            await callback.answer("❌ Not all settings are filled in!", show_alert=True)
            return

        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                "✅ <b>Autoposting settings saved!</b>\n\n"
                f"📺 <b>Channels:</b> {len(channels)}\n"
                f"📂 <b>Categories:</b> {len(categories)}\n"
                f"🎨 <b>Style:</b> {get_style_emoji_name(style)}\n"
                f"⏰ <b>Schedule:</b> {frequency} times per day\n\n"
                "🚀 Autoposting is now active and will work according to the schedule!"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Autoposting settings save error: {e}")
        await send_text_only(
            callback,
            "❌ An error occurred while saving settings",
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
        channels_text = '\n'.join([f"• {ch}" for ch in channels]) if channels else "❌ None yet"

        text = (
            "📺 <b>Step 1/4: Set up channels</b>\n\n"
            "📋 <b>Instructions:</b>\n"
            "1️⃣ Add the bot to your channel as an administrator\n"
            "2️⃣ Grant 'Post messages' rights\n"
            "3️⃣ Click 'Add channel' and send the username\n\n"
            "💡 You can add multiple channels\n\n"
            f"📺 <b>Added channels:</b>\n{channels_text}"
        )

        from bot.keyboards import get_autopost_step_keyboard
        await send_text_only(callback, text, get_autopost_step_keyboard("channels", False))

    elif current_step == 'style':
        await state.set_state(UserStates.selecting_categories)
        await state.update_data(current_step='categories', step_number=2)

        categories = data.get('categories', [])
        selected_text = ', '.join(
            [get_category_emoji_name(cat) for cat in categories]) if categories else "Not selected yet"

        text = (
            "📂 <b>Step 2/4: Select categories</b>\n\n"
            "Select news categories for autoposting:\n\n"
            "💡 <b>Tip:</b> Choose 2-4 categories for the best quality\n\n"
            f"🎯 <b>Selected categories:</b> {selected_text}"
        )

        from bot.keyboards import get_category_selection_keyboard_new
        await send_text_only(callback, text, get_category_selection_keyboard_new(categories))

    elif current_step == 'schedule':
        await state.set_state(UserStates.selecting_style)
        await state.update_data(current_step='style', step_number=3)

        style = data.get('style', '')
        style_text = get_style_emoji_name(style) if style else "Not selected"

        text = (
            "🎨 <b>Step 3/4: Select style</b>\n\n"
            "Select post style:\n\n"
            "🎩 <b>Formal</b> - business style\n"
            "😎 <b>Conversational</b> - friendly tone\n"
            "🤪 <b>Meme</b> - humorous style\n\n"
            f"🎯 <b>Selected style:</b> {style_text}"
        )

        from bot.keyboards import get_style_selection_keyboard_new
        await send_text_only(callback, text, get_style_selection_keyboard_new(style))

    elif current_step == 'confirm':
        await state.set_state(UserStates.selecting_schedule)
        await state.update_data(current_step='schedule', step_number=4)

        frequency = data.get('frequency', 0)
        schedule_names = {
            1: "1 time per day (09:00)",
            2: "2 times per day (09:00, 21:00)",
            3: "3 times per day (09:00, 15:00, 21:00)"
        }
        schedule_text = schedule_names.get(frequency, "Not set")

        text = (
            "⏰ <b>Step 4/4: Set schedule</b>\n\n"
            "Select post frequency:\n\n"
            "• 1️⃣ <b>1 time per day</b> - for small channels\n"
            "• 2️⃣ <b>2 times per day</b> - optimal\n"
            "• 3️⃣ <b>3 times per day</b> - for active channels\n\n"
            f"🎯 <b>Selected schedule:</b> {schedule_text}"
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
        "❌ <b>Autoposting setup canceled</b>\n\n"
        "You can return to setup anytime via your profile."
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
                await callback.answer("❌ User not found", show_alert=True)
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
                    "❌ <b>No settings to edit</b>\n\n"
                    "First, create a new autoposting setting."
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

            summary_text += "\n\n💡 Click 'Edit' to change the settings"

            from bot.keyboards import get_confirmation_keyboard_autopost
            await send_text_only(callback, summary_text, get_confirmation_keyboard_autopost())
            break

    except Exception as e:
        logging.error(f"Error loading settings for editing: {e}")
        text = "❌ An error occurred while loading settings"
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
                await callback.answer("❌ User not found", show_alert=True)
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
                    "✅ <b>Autoposting settings deleted</b>\n\n"
                    f"Deleted settings: {result.rowcount}\n\n"
                    "Autoposting stopped. You can create a new setting at any time."
                )
            else:
                text = (
                    "⚠️ <b>No autoposting settings found</b>\n\n"
                    "You have no active settings to delete."
                )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error deleting autoposting settings: {e}")
        text = "❌ An error occurred while deleting settings"
        await send_text_only(callback, text, get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "profile_back")
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    await show_profile(callback, state)

@router.callback_query(F.data == "manual_post")
async def show_manual_post_menu(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                    "📤 <b>Manual post sending</b>\n\n"
                    "❌ <b>Active subscription required</b>\n\n"
                    "An active subscription is required to send posts manually.\n\n"
                    "💎 Purchase a subscription to access this feature"
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
                    "📤 <b>Manual post sending</b>\n\n"
                    "❌ <b>Autoposting not configured</b>\n\n"
                    "First, configure autoposting in the 'Posting settings' section.\n\n"
                    "💡 After setup, manual post features will appear here"
                )
                await send_text_only(callback, text, get_profile_keyboard())
                await callback.answer()
                return

            text = (
                "📤 <b>Manual post sending</b>\n\n"
                "Choose an action:\n\n"
                "🚀 <b>Send now</b> - send a post immediately\n"
                "⏰ <b>Schedule</b> - send at a specified time\n"
                "📊 <b>Test post</b> - send a test message\n\n"
                f"📺 <b>Channel:</b> {setting.channel_id}\n"
                f"📂 <b>Category:</b> {get_category_emoji_name(setting.category)}\n"
                f"🎨 <b>Style:</b> {get_style_emoji_name(setting.style)}"
            )

            from bot.keyboards import get_manual_post_keyboard
            await send_text_only(callback, text, get_manual_post_keyboard())
            break

    except Exception as e:
        logging.error(f"Error showing manual post menu: {e}")
        await send_text_only(callback, "❌ An error occurred", get_profile_keyboard())

    await callback.answer()


@router.callback_query(F.data == "manual_send_now")
async def manual_send_now(callback: CallbackQuery, state: FSMContext):
    try:
        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ User not found", show_alert=True)
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
                await callback.answer("❌ Auto-posting settings not found", show_alert=True)
                return

            send_manual_post.delay(
                user_id=user.id,
                channel_id=setting.channel_id,
                category=setting.category,
                style=setting.style
            )

            text = (
                "🚀 <b>Post is being sent!</b>\n\n"
                f"📺 Channel: {setting.channel_id}\n"
                f"📂 Category: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Style: {get_style_emoji_name(setting.style)}\n\n"
                "⏳ The post will be published within a minute"
            )

            await send_text_only(callback, text, get_profile_keyboard())
            break

    except Exception as e:
        logging.error(f"Error sending manual post: {e}")
        await callback.answer("❌ Error sending post", show_alert=True)


@router.callback_query(F.data == "manual_schedule")
async def manual_schedule_setup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.scheduling_manual_post)

    text = (
        "⏰ <b>Schedule a post</b>\n\n"
        "Send the time in HH:MM format\n"
        "For example: <code>15:23</code> or <code>09:00</code>\n\n"
        "📅 If the time has already passed today, the post will be sent tomorrow\n\n"
        "💡 Enter the time:"
    )

    from bot.keyboards import get_manual_schedule_cancel_keyboard
    await send_text_only(callback, text, get_manual_schedule_cancel_keyboard())
    await callback.answer()


@router.message(UserStates.scheduling_manual_post)
async def process_schedule_time(message: Message, state: FSMContext):
    time_input = message.text.strip()

    try:
        hour, minute = map(int, time_input.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "❌ <b>Invalid time format!</b>\n\n"
            "Use the HH:MM format (for example: 15:23)",
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
                await message.answer("❌ User not found")
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
                await message.answer("❌ Autoposting settings not found")
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
                day_text = "tomorrow"
            else:
                day_text = "today"

            text = (
                "✅ <b>Post scheduled!</b>\n\n"
                f"⏰ Send time: {time_input} ({day_text})\n"
                f"📺 Channel: {setting.channel_id}\n"
                f"📂 Category: {get_category_emoji_name(setting.category)}\n"
                f"🎨 Style: {get_style_emoji_name(setting.style)}\n\n"
                "🔔 The post will be sent automatically at the specified time"
            )

            await message.answer(text, reply_markup=get_profile_keyboard(), parse_mode='HTML')
            await state.clear()
            break

    except Exception as e:
        logging.error(f"Error scheduling post: {e}")
        await message.answer("❌ Error scheduling post")
