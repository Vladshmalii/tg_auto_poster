from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.keyboards import get_main_menu_keyboard
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


@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery):

    faq_text = (
        "❓ <b>Frequently Asked Questions</b>\n\n"

        "<b>🤖 How does the bot work?</b>\n"
        "The bot automatically parses news from trusted sources, "
        "processes them in your chosen style, and publishes them to your channel.\n\n"

        "<b>📰 What news categories are available?</b>\n"
        "• 💻 IT & Tech - programming, development\n"
        "• ₿ Crypto - blockchain, DeFi, NFT\n"
        "• 💼 Business - startups, investment, economy\n"
        "• 🌍 General news - events, society\n"
        "• 🎮 Esports - tournaments, teams, games\n"
        "• 📱 Technology - gadgets, innovation\n"
        "• 🏛️ Politics - Ukrainian and world politics\n"
        "• 🔬 Science - research, discoveries\n"
        "• 🚗 Auto - cars, tests, new models\n"
        "• 💊 Health - medicine, healthy lifestyle\n"
        "• 🎭 Entertainment - movies, music, showbiz\n"
        "• ⚽ Sports - football, tennis, olympics\n\n"

        "<b>🎨 What styles are there?</b>\n"
        "• 🎩 Formal - classic style\n"
        "• 😎 Conversational - friendly tone\n"
        "• 🤪 Meme - humorous style\n\n"

        "<b>⚙️ How to set up autoposting?</b>\n"
        "1. Purchase a subscription\n"
        "2. Add the bot to your channel as an admin\n"
        "3. Grant posting rights\n"
        "4. Choose category and style\n"
        "5. Set up the schedule (up to 3 posts per day)\n\n"

        "<b>💰 How much does it cost?</b>\n"
        "• 7 days - 100 ⭐\n"
        "• 14 days - 180 ⭐\n"
        "• 30 days - 300 ⭐\n\n"

        "<b>🔒 Security</b>\n"
        "The bot does not have access to private messages. "
        "It can only post in the channel where it is added as admin.\n\n"

        "<b>🆘 Need help?</b>\n"
        "Contact support via the main menu."
    )

    await send_text_only(callback, faq_text, get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):

    support_text = (
        "🆘 <b>Support</b>\n\n"
        "If you have any questions or issues, "
        "reach out to us in any convenient way:\n\n"

        "📧 Email: support@newsbot.com\n"
        "💬 Telegram: @newsbot_support\n"
        "🕐 Working hours: 24/7\n\n"

        "📝 <b>When contacting us, please provide:</b>\n"
        "• Your Telegram ID\n"
        "• Problem description\n"
        "• Screenshots (if any)\n\n"

        "We will respond within 1-2 hours!"
    )

    await send_text_only(callback, support_text, get_main_menu_keyboard())
    await callback.answer()