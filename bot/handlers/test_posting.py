from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.keyboards import (
    get_category_keyboard,
    get_style_keyboard,
    get_main_menu_keyboard,
    get_subscription_keyboard
)
from bot.states import UserStates
from services.news_service import NewsService
from services.content_generator import ContentGenerator
from services.test_post_service import TestPostService
from database.database import get_db
import logging
import html

router = Router()


def escape_html(text: str) -> str:
    if not text:
        return ""
    return html.escape(text)


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


@router.callback_query(F.data == "test_post")
async def start_test_posting(callback: CallbackQuery, state: FSMContext):
    async for db in get_db():
        can_create, error_message = await TestPostService.can_create_test_post(
            db, callback.from_user.id
        )

        if not can_create:
            error_text = f"🚫 <b>Test post limit exceeded</b>\n\n{error_message}"
            await send_text_only(callback, error_text, get_subscription_keyboard())
            await callback.answer()
            return

        break

    await state.set_state(UserStates.selecting_category)

    text = (
        "🧪 <b>Test Posting</b>\n\n"
        "Let's test how the bot will format posts for your channel!\n\n"
        "⚠️ <b>Attention:</b> Test post is available once every 24 hours.\n\n"
        "First, select a news category:"
    )

    await send_text_only(callback, text, get_category_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]

    await state.update_data(category=category)
    await state.set_state(UserStates.selecting_style)

    category_names = {
        'it': '💻 IT & Tech',
        'crypto': '₿ Cryptocurrency',
        'business': '💼 Business',
        'general': '🌍 General News',
        'esports': '🎮 Esports',
        'tech': '📱 Technology',
        'politics': '🏛️ Politics',
        'science': '🔬 Science',
        'auto': '🚗 Automotive',
        'health': '💊 Health',
        'entertainment': '🎭 Entertainment',
        'sport': '⚽ Sports'
    }

    category_name = category_names.get(category, 'Unknown')

    text = (
        f"✅ Selected category: <b>{category_name}</b>\n\n"
        "Now select the post formatting style:"
    )

    await send_text_only(callback, text, get_style_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("style_"))
async def select_style(callback: CallbackQuery, state: FSMContext):
    style = callback.data.split("_")[1]

    await state.update_data(style=style)
    await state.set_state(UserStates.waiting_channel_setup)

    style_names = {
        'formal': '🎩 Formal',
        'casual': '😎 Casual',
        'meme': '🤪 Meme'
    }

    style_name = style_names.get(style, 'Unknown')

    try:
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username if bot_info.username else "your_bot"
    except Exception:
        bot_username = "your_bot"

    text = (
        f"✅ Selected style: <b>{style_name}</b>\n\n"
        "📋 <b>Bot Setup Instructions:</b>\n\n"
        "1️⃣ Go to your channel settings\n"
        "2️⃣ Select \"Administrators\"\n"
        "3️⃣ Click \"Add Administrator\"\n"
        f"4️⃣ Find and add: @{bot_username}\n"
        "5️⃣ Make sure to grant <b>\"Post Messages\"</b> permission\n\n"
        "6️⃣ Then send me your <b>channel username</b> (e.g.: @my_channel)\n\n"
        "❓ <b>How to find channel username?</b>\n"
        "Go to channel → Settings → Channel Type → Public Link"
    )

    await send_text_only(callback, text)
    await callback.answer()


@router.message(UserStates.waiting_channel_setup)
async def receive_channel_info(message: Message, state: FSMContext):
    channel_input = message.text.strip()

    if not (channel_input.startswith('@') or 'telegram.me/' in channel_input or 't.me/' in channel_input):
        await message.answer(
            "❌ <b>Invalid format!</b>\n\n"
            "Send channel username (e.g.: @my_channel) or channel link.",
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

    await state.update_data(channel_username=channel_username)
    await state.set_state(UserStates.checking_bot_permissions)

    await check_bot_permissions_real(message, state, channel_username)


async def check_bot_permissions_real(message: Message, state: FSMContext, channel_username: str):
    try:
        safe_channel_name = escape_html(channel_username)

        checking_msg = await message.answer(
            f"🔍 <b>Checking bot permissions in channel {safe_channel_name}...</b>",
            parse_mode='HTML'
        )

        try:
            chat = await message.bot.get_chat(channel_username)
            chat_member = await message.bot.get_chat_member(channel_username, message.bot.id)

            if chat_member.status not in ['administrator']:
                await checking_msg.edit_text(
                    f"❌ <b>Bot is not an administrator in channel {safe_channel_name}</b>\n\n"
                    "Please add the bot as an administrator with message posting permissions.",
                    parse_mode='HTML'
                )
                return

            if not chat_member.can_post_messages:
                await checking_msg.edit_text(
                    f"❌ <b>Bot doesn't have posting permissions in channel {safe_channel_name}</b>\n\n"
                    "Please grant the bot message posting permissions.",
                    parse_mode='HTML'
                )
                return

            await checking_msg.edit_text(
                "✅ <b>Permissions verified successfully!</b>\n\n"
                "⏳ Generating test post...",
                parse_mode='HTML'
            )

            await generate_and_send_test_post(message, state, channel_username)

        except Exception as e:
            error_msg = str(e)
            safe_error = escape_html(error_msg[:200])

            if "chat not found" in error_msg.lower():
                await checking_msg.edit_text(
                    f"❌ <b>Channel {safe_channel_name} not found</b>\n\n"
                    "Check that the channel username is correct. "
                    "Make sure the channel is public or the bot is added to it.",
                    parse_mode='HTML'
                )
            elif "not enough rights" in error_msg.lower() or "forbidden" in error_msg.lower():
                await checking_msg.edit_text(
                    f"❌ <b>Insufficient permissions to access channel {safe_channel_name}</b>\n\n"
                    "Add the bot to the channel as an administrator.",
                    parse_mode='HTML'
                )
            else:
                await checking_msg.edit_text(
                    f"❌ <b>Error checking channel:</b>\n\n"
                    f"{safe_error}\n\n"
                    "Make sure the bot is added to the channel as an administrator.",
                    parse_mode='HTML'
                )

    except Exception as e:
        logging.error(f"Error checking permissions: {e}")
        await message.answer(
            "❌ An error occurred during verification. Please try again.",
            reply_markup=get_main_menu_keyboard()
        )


async def generate_and_send_test_post(message: Message, state: FSMContext, channel_username: str):
    try:
        user_data = await state.get_data()
        category = user_data.get('category', 'general')
        style = user_data.get('style', 'formal')

        news_service = NewsService()
        content_generator = ContentGenerator()

        news_item = await news_service.get_random_news(category)

        if not news_item:
            from services.news_service import NewsItem
            news_item = NewsItem(
                title="Test news for demonstration",
                description="This is an example of how your posts will look. "
                            "The bot automatically finds current news and formats it in your selected style.",
                url="https://example.com",
                published_at="2024-01-01T12:00:00Z"
            )

        formatted_content = await content_generator.generate_post(news_item, style, category)

        try:
            sent_message = await message.bot.send_message(
                chat_id=channel_username,
                text=formatted_content,
                parse_mode='HTML',
                disable_web_page_preview=False
            )

            async for db in get_db():
                await TestPostService.record_test_post(
                    db,
                    message.from_user.id,
                    channel_username,
                    category,
                    style
                )
                break

            safe_channel = escape_html(channel_username)
            safe_category = escape_html(category)
            safe_style = escape_html(style)

            success_text = (
                "🎉 <b>Test post published successfully!</b>\n\n"
                "📊 <b>Post parameters:</b>\n"
                f"• Channel: {safe_channel}\n"
                f"• Category: {safe_category}\n"
                f"• Style: {safe_style}\n\n"
                "✨ <b>Check your channel!</b>\n\n"
                "⚠️ <b>Remember:</b> Next test post will be available in 24 hours.\n\n"
                "💎 <b>Want more posts?</b> Purchase a subscription "
                "for automatic posting 3 times per day!"
            )

            await message.answer(
                success_text,
                reply_markup=get_subscription_keyboard(),
                parse_mode='HTML'
            )

            await state.set_state(UserStates.main_menu)

        except Exception as e:
            error_msg = str(e)
            safe_channel = escape_html(channel_username)
            safe_error = escape_html(error_msg[:200])

            if "chat not found" in error_msg.lower():
                await message.answer(
                    f"❌ <b>Failed to send post to {safe_channel}</b>\n\n"
                    "Possible reasons:\n"
                    "• Incorrect channel username\n"
                    "• Bot not added to channel\n"
                    "• Insufficient bot permissions",
                    parse_mode='HTML'
                )
            elif "forbidden" in error_msg.lower():
                await message.answer(
                    f"❌ <b>Access denied to channel {safe_channel}</b>\n\n"
                    "Make sure that:\n"
                    "• Bot is added as administrator\n"
                    "• Bot has posting permissions",
                    parse_mode='HTML'
                )
            else:
                await message.answer(
                    f"❌ <b>Error sending post:</b>\n\n"
                    f"{safe_error}",
                    parse_mode='HTML'
                )

    except Exception as e:
        logging.error(f"Error generating test post: {e}")
        await message.answer(
            "❌ An error occurred while generating the post. Please try later.",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(F.data == "select_category")
async def back_to_category_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.selecting_category)

    text = (
        "🧪 <b>Test Posting</b>\n\n"
        "Select news category:"
    )

    await send_text_only(callback, text, get_category_keyboard())
    await callback.answer()


@router.callback_query(F.data == "select_style")
async def back_to_style_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.selecting_style)
    user_data = await state.get_data()
    category = user_data.get('category', 'general')

    category_names = {
        'it': '💻 IT & Tech',
        'crypto': '₿ Cryptocurrency',
        'business': '💼 Business',
        'general': '🌍 General News',
        'esports': '🎮 Esports',
        'tech': '📱 Technology',
        'politics': '🏛️ Politics',
        'science': '🔬 Science',
        'auto': '🚗 Automotive',
        'health': '💊 Health',
        'entertainment': '🎭 Entertainment',
        'sport': '⚽ Sports'
    }

    category_name = category_names.get(category, 'Unknown')

    text = (
        f"✅ Selected category: <b>{category_name}</b>\n\n"
        "Select post formatting style:"
    )

    await send_text_only(callback, text, get_style_keyboard())
    await callback.answer()