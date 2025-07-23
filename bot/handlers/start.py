from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from database.database import get_db
from bot.keyboards import get_main_menu_keyboard
from bot.states import UserStates
from config.settings import settings
import logging

router = Router()


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.warning(f"Failed to edit message: {e}")
        try:
            await callback.message.delete()
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception:
            
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )


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


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    try:
        async for db in get_db():
            result = await db.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            if not user:
                new_user = User(
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    language='en'
                )
                db.add(new_user)
                await db.commit()

                welcome_text = (
                    f"🎉 <b>Welcome to NewsBot, {message.from_user.first_name}!</b>\n\n"
                    "🤖 I will help you automatically post news to your Telegram channel.\n\n"
                    "🔥 <b>Features:</b>\n"
                    "• 📰 Autopost news by category\n"
                    "• 🎨 Various post styles\n"
                    "• ⏰ Customizable posting schedule\n"
                    "• 🧪 Free trial\n\n"
                    "Choose an action:"
                )
                is_new_user = True
            else:
                welcome_text = (
                    f"👋 <b>Welcome back, {message.from_user.first_name}!</b>\n\n"
                    "🚀 Ready to work with news?\n\n"
                    "Choose an action:"
                )
                is_new_user = False

            await state.set_state(UserStates.main_menu)

            try:
                if settings.WELCOME_IMAGE_URL:
                    await message.answer_photo(
                        photo=settings.WELCOME_IMAGE_URL,
                        caption=welcome_text,
                        reply_markup=get_main_menu_keyboard(),
                        parse_mode='HTML'
                    )
                else:
                    await message.answer(
                        welcome_text,
                        reply_markup=get_main_menu_keyboard(),
                        parse_mode='HTML'
                    )
            except Exception as photo_error:
                logging.warning(f"Failed to load welcome image: {photo_error}")
                await message.answer(
                    welcome_text,
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode='HTML'
                )

            break

    except Exception as e:
        logging.error(f"Error in start_command: {e}")
        await message.answer(
            "❌ An error occurred. Please try again later.",
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.main_menu)

    text = "🏠 <b>Main menu</b>\n\nChoose an action:"

    await send_text_only(callback, text, get_main_menu_keyboard())
    await callback.answer()