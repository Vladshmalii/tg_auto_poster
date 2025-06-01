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


@router.callback_query(F.data == "test_post")
async def start_test_posting(callback: CallbackQuery, state: FSMContext):
    async for db in get_db():
        can_create, error_message = await TestPostService.can_create_test_post(
            db, callback.from_user.id
        )

        if not can_create:
            error_text = f"🚫 <b>Лимит тестовых постов исчерпан</b>\n\n{error_message}"
            await send_text_only(callback, error_text, get_subscription_keyboard())
            await callback.answer()
            return

        break

    await state.set_state(UserStates.selecting_category)

    text = (
        "🧪 <b>Тестовый постинг</b>\n\n"
        "Давайте протестируем, как бот будет оформлять посты в вашем канале!\n\n"
        "⚠️ <b>Внимание:</b> Тестовый пост доступен 1 раз в 24 часа.\n\n"
        "Сначала выберите категорию новостей:"
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

    category_name = category_names.get(category, 'Неизвестно')

    text = (
        f"✅ Выбрана категория: <b>{category_name}</b>\n\n"
        "Теперь выберите стиль оформления постов:"
    )

    await send_text_only(callback, text, get_style_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("style_"))
async def select_style(callback: CallbackQuery, state: FSMContext):
    style = callback.data.split("_")[1]

    await state.update_data(style=style)
    await state.set_state(UserStates.waiting_channel_setup)

    style_names = {
        'formal': '🎩 Формальный',
        'casual': '😎 Разговорный',
        'meme': '🤪 Мемный'
    }

    style_name = style_names.get(style, 'Неизвестно')

    try:
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username if bot_info.username else "вашего_бота"
    except Exception:
        bot_username = "вашего_бота"

    text = (
        f"✅ Выбран стиль: <b>{style_name}</b>\n\n"
        "📋 <b>Инструкция по добавлению бота:</b>\n\n"
        "1️⃣ Перейдите в настройки вашего канала\n"
        "2️⃣ Выберите «Администраторы»\n"
        "3️⃣ Нажмите «Добавить администратора»\n"
        f"4️⃣ Найдите и добавьте: @{bot_username}\n"
        "5️⃣ Обязательно дайте права на <b>«Публикация сообщений»</b>\n\n"
        "6️⃣ Затем отправьте мне <b>username канала</b> (например: @my_channel)\n\n"
        "❓ <b>Как узнать username канала?</b>\n"
        "Зайдите в канал → Настройки → Тип канала → Публичная ссылка"
    )

    await send_text_only(callback, text)
    await callback.answer()


@router.message(UserStates.waiting_channel_setup)
async def receive_channel_info(message: Message, state: FSMContext):
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

    await state.update_data(channel_username=channel_username)
    await state.set_state(UserStates.checking_bot_permissions)

    await check_bot_permissions_real(message, state, channel_username)


async def check_bot_permissions_real(message: Message, state: FSMContext, channel_username: str):
    try:
        safe_channel_name = escape_html(channel_username)

        checking_msg = await message.answer(
            f"🔍 <b>Проверяю права бота в канале {safe_channel_name}...</b>",
            parse_mode='HTML'
        )

        try:
            chat = await message.bot.get_chat(channel_username)
            chat_member = await message.bot.get_chat_member(channel_username, message.bot.id)

            if chat_member.status not in ['administrator']:
                await checking_msg.edit_text(
                    f"❌ <b>Бот не является администратором в канале {safe_channel_name}</b>\n\n"
                    "Пожалуйста, добавьте бота как администратора с правами на публикацию сообщений.",
                    parse_mode='HTML'
                )
                return

            if not chat_member.can_post_messages:
                await checking_msg.edit_text(
                    f"❌ <b>У бота нет прав на публикацию в канале {safe_channel_name}</b>\n\n"
                    "Пожалуйста, дайте боту права на публикацию сообщений.",
                    parse_mode='HTML'
                )
                return

            await checking_msg.edit_text(
                "✅ <b>Права проверены успешно!</b>\n\n"
                "⏳ Генерирую тестовый пост...",
                parse_mode='HTML'
            )

            await generate_and_send_test_post(message, state, channel_username)

        except Exception as e:
            error_msg = str(e)
            safe_error = escape_html(error_msg[:200])

            if "chat not found" in error_msg.lower():
                await checking_msg.edit_text(
                    f"❌ <b>Канал {safe_channel_name} не найден</b>\n\n"
                    "Проверьте правильность username канала. "
                    "Убедитесь, что канал публичный или бот добавлен в него.",
                    parse_mode='HTML'
                )
            elif "not enough rights" in error_msg.lower() or "forbidden" in error_msg.lower():
                await checking_msg.edit_text(
                    f"❌ <b>Недостаточно прав для доступа к каналу {safe_channel_name}</b>\n\n"
                    "Добавьте бота в канал как администратора.",
                    parse_mode='HTML'
                )
            else:
                await checking_msg.edit_text(
                    f"❌ <b>Ошибка при проверке канала:</b>\n\n"
                    f"{safe_error}\n\n"
                    "Убедитесь, что бот добавлен в канал как администратор.",
                    parse_mode='HTML'
                )

    except Exception as e:
        logging.error(f"Ошибка при проверке прав: {e}")
        await message.answer(
            "❌ Произошла ошибка при проверке. Попробуйте еще раз.",
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
                title="Тестовая новость для демонстрации",
                description="Это пример того, как будут выглядеть ваши посты. "
                            "Бот автоматически находит актуальные новости и оформляет их в выбранном стиле.",
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
                "🎉 <b>Тестовый пост успешно опубликован!</b>\n\n"
                "📊 <b>Параметры поста:</b>\n"
                f"• Канал: {safe_channel}\n"
                f"• Категория: {safe_category}\n"
                f"• Стиль: {safe_style}\n\n"
                "✨ <b>Проверьте ваш канал!</b>\n\n"
                "⚠️ <b>Помните:</b> Следующий тестовый пост будет доступен через 24 часа.\n\n"
                "💎 <b>Хотите больше постов?</b> Приобретите подписку "
                "для автоматического постинга 3 раза в день!"
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
                    f"❌ <b>Не удалось отправить пост в {safe_channel}</b>\n\n"
                    "Возможные причины:\n"
                    "• Неверный username канала\n"
                    "• Бот не добавлен в канал\n"
                    "• Недостаточно прав у бота",
                    parse_mode='HTML'
                )
            elif "forbidden" in error_msg.lower():
                await message.answer(
                    f"❌ <b>Доступ запрещен к каналу {safe_channel}</b>\n\n"
                    "Убедитесь, что:\n"
                    "• Бот добавлен как администратор\n"
                    "• У бота есть права на публикацию",
                    parse_mode='HTML'
                )
            else:
                await message.answer(
                    f"❌ <b>Ошибка при отправке поста:</b>\n\n"
                    f"{safe_error}",
                    parse_mode='HTML'
                )

    except Exception as e:
        logging.error(f"Ошибка генерации тестового поста: {e}")
        await message.answer(
            "❌ Произошла ошибка при генерации поста. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(F.data == "select_category")
async def back_to_category_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.selecting_category)

    text = (
        "🧪 <b>Тестовый постинг</b>\n\n"
        "Выберите категорию новостей:"
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

    category_name = category_names.get(category, 'Неизвестно')

    text = (
        f"✅ Выбрана категория: <b>{category_name}</b>\n\n"
        "Выберите стиль оформления постов:"
    )

    await send_text_only(callback, text, get_style_keyboard())
    await callback.answer()