from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.keyboards import get_main_menu_keyboard
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
        # Если не удалось удалить, просто отправляем новое
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )


@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery):
    """Показ FAQ"""

    faq_text = (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"

        "<b>🤖 Как работает бот?</b>\n"
        "Бот автоматически парсит новости из проверенных источников, "
        "обрабатывает их в выбранном вами стиле и публикует в ваш канал.\n\n"

        "<b>📰 Какие категории новостей доступны?</b>\n"
        "• 💻 IT & Tech - программирование, разработка\n"
        "• ₿ Криптовалюты - блокчейн, DeFi, NFT\n"
        "• 💼 Бизнес - стартапы, инвестиции, экономика\n"
        "• 🌍 Общие новости - события, общество\n"
        "• 🎮 Киберспорт - турниры, команды, игры\n"
        "• 📱 Технологии - гаджеты, инновации\n"
        "• 🏛️ Политика - украинская и мировая политика\n"
        "• 🔬 Наука - исследования, открытия\n"
        "• 🚗 Авто - автомобили, тесты, новинки\n"
        "• 💊 Здоровье - медицина, здоровый образ жизни\n"
        "• 🎭 Развлечения - кино, музыка, шоу-бизнес\n"
        "• ⚽ Спорт - футбол, теннис, олимпиада\n\n"

        "<b>🎨 Какие стили оформления есть?</b>\n"
        "• 🎩 Формальный - классическое оформление\n"
        "• 😎 Разговорный - дружелюбный тон\n"
        "• 🤪 Мемный - юмористическое оформление\n\n"

        "<b>⚙️ Как настроить автопостинг?</b>\n"
        "1. Купите подписку\n"
        "2. Добавьте бота в канал как администратора\n"
        "3. Дайте права на публикацию сообщений\n"
        "4. Выберите категорию и стиль\n"
        "5. Настройте расписание (до 3 постов в день)\n\n"

        "<b>💰 Сколько это стоит?</b>\n"
        "• 7 дней - 100 ⭐\n"
        "• 14 дней - 180 ⭐\n"
        "• 30 дней - 300 ⭐\n\n"

        "<b>🔒 Безопасность</b>\n"
        "Бот не имеет доступа к личным сообщениям. "
        "Он может только публиковать посты в канале, где добавлен как админ.\n\n"

        "<b>🆘 Нужна помощь?</b>\n"
        "Обратитесь в поддержку через главное меню."
    )

    await send_text_only(callback, faq_text, get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    """Показ контактов поддержки"""

    support_text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы, "
        "обратитесь к нам любым удобным способом:\n\n"

        "📧 Email: support@newsbot.com\n"
        "💬 Telegram: @newsbot_support\n"
        "🕐 Время работы: 24/7\n\n"

        "📝 <b>При обращении укажите:</b>\n"
        "• Ваш Telegram ID\n"
        "• Описание проблемы\n"
        "• Скриншоты (если есть)\n\n"

        "Мы ответим в течение 1-2 часов!"
    )

    await send_text_only(callback, support_text, get_main_menu_keyboard())
    await callback.answer()