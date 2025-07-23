from aiogram import Router, F
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from database.models import User, Subscription, Transaction
from database.database import get_db
from bot.keyboards import get_subscription_keyboard, get_main_menu_keyboard
from bot.states import UserStates
from config.settings import settings
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


@router.callback_query(F.data == "buy_subscription")
async def show_subscription_plans(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.selecting_subscription)

    text = (
        "💎 <b>NewsBot Subscription Plans</b>\n\n"
        "🔥 <b>What you get:</b>\n"
        "• Automatic news posting\n"
        "• Category and style selection\n"
        "• Schedule customization\n"
        "• Up to 3 posts per day\n"
        "• 24/7 support\n\n"
        "Choose a plan:"
    )

    await send_text_only(callback, text, get_subscription_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("sub_"))
async def process_subscription_purchase(callback: CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[1])
    price = settings.SUBSCRIPTION_PRICES[days]

    await state.update_data(subscription_days=days, subscription_price=price)
    await state.set_state(UserStates.waiting_payment)

    descriptions = {
        7: "🚀 Starter plan\n📰 News autoposting\n⏰ 7 days access",
        14: "🔥 Popular plan\n📰 News autoposting\n⏰ 14 days access\n💡 Save 8%",
        30: "💎 Maximum plan\n📰 News autoposting\n⏰ 30 days access\n💡 Save 17%"
    }

    prices = [LabeledPrice(label=f"NewsBot Premium {days}d", amount=price)]

    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"NewsBot Premium - {days} days",
            description=descriptions.get(days, f"News autoposting for {days} days"),
            payload=f"subscription_{days}_{callback.from_user.id}_{int(datetime.now().timestamp())}",
            provider_token="",
            currency="XTR",
            prices=prices,
            photo_url=settings.SUBSCRIPTION_IMAGES.get(days),
            photo_width=512,
            photo_height=512,
            need_shipping_address=False,
            is_flexible=False
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to plans", callback_data="buy_subscription")],
            [InlineKeyboardButton(text="🏠 Main menu", callback_data="back_to_main")]
        ])

        await send_text_only(
            callback,
            f"💳 <b>Invoice created!</b>\n\n"
            f"📦 Plan: <b>NewsBot Premium {days} days</b>\n"
            f"💰 Price: <b>{price} ⭐</b>\n\n"
            "📱 The invoice has been sent to your private messages.\n"
            "Click the <b>\"Pay ⭐\"</b> button to complete the purchase.",
            back_keyboard
        )

    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        await send_text_only(
            callback,
            "❌ Error creating invoice. Please try again later.",
            get_subscription_keyboard()
        )

    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    try:
        payload_parts = pre_checkout_query.invoice_payload.split("_")

        if len(payload_parts) >= 3:
            days = int(payload_parts[1])
            user_telegram_id = int(payload_parts[2])

            if days in [7, 14, 30] and user_telegram_id > 0:
                await pre_checkout_query.answer(ok=True)
                logging.info(f"Pre-checkout approved for user {user_telegram_id}, {days} days")
            else:
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Invalid subscription parameters"
                )
                logging.warning(f"Pre-checkout declined: invalid params {payload_parts}")
        else:
            await pre_checkout_query.answer(
                ok=False,
                error_message="Payment processing error"
            )

    except Exception as e:
        logging.error(f"Pre-checkout error: {e}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="Technical error"
        )


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment

    logging.info(f"💰 ПОЛУЧЕН ПЛАТЕЖ!")
    logging.info(f"Сумма: {payment.total_amount} {payment.currency}")
    logging.info(f"ID платежа: {payment.telegram_payment_charge_id}")
    logging.info(f"Пользователь: {message.from_user.id}")

    try:
        payload_parts = payment.invoice_payload.split("_")
        days = int(payload_parts[1])
        user_telegram_id = int(payload_parts[2])

        async for db in get_db():
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_telegram_id)
            )
            user = user_result.scalar_one_or_none()

            if user:
                expires_at = datetime.utcnow() + timedelta(days=days)

                subscription = Subscription(
                    user_id=user.id,
                    plan_type=days,
                    expires_at=expires_at,
                    is_active=True
                )
                db.add(subscription)

                transaction = Transaction(
                    user_id=user.id,
                    amount=payment.total_amount,
                    currency=payment.currency,
                    payment_method="stars",
                    status="completed",
                    external_id=payment.telegram_payment_charge_id
                )
                db.add(transaction)

                await db.commit()

                success_text = (
                    "🎉 <b>Payment processed successfully!</b>\n\n"
                    f"✅ Subscription activated for <b>{days} days</b>\n"
                    f"📅 Valid until: <b>{expires_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                    "🚀 Now you can set up automatic posting!\n"
                    "Use the /start command to access all features."
                )

                await message.answer(success_text, parse_mode='HTML')

                await notify_admin_about_payment(message.bot, payment, user, days)

            break

    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        await message.answer(
            "❌ An error occurred while activating your subscription. "
            "Please contact support with your payment ID: "
            f"<code>{payment.telegram_payment_charge_id}</code>",
            parse_mode='HTML'
        )


async def notify_admin_about_payment(bot, payment, user, days):
    try:
        if settings.ADMIN_IDS:
            admin_text = (
                "💰 <b>NEW PAYMENT!</b>\n\n"
                f"👤 User: @{user.username or 'Unknown'} (ID: {user.telegram_id})\n"
                f"📦 Plan: {days} days\n"
                f"💳 Amount: {payment.total_amount} {payment.currency}\n"
                f"🆔 Payment ID: <code>{payment.telegram_payment_charge_id}</code>\n"
                f"📅 Time: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logging.error(f"Failed to send notification to admin {admin_id}: {e}")

    except Exception as e:
        logging.error(f"Error notifying administrator: {e}")


async def get_payment_statistics(db: AsyncSession, period_days: int = 30):
    try:
        start_date = datetime.utcnow() - timedelta(days=period_days)

        result = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.status == 'completed',
                    Transaction.created_at >= start_date
                )
            )
        )
        transactions = result.scalars().all()

        total_amount = sum(t.amount for t in transactions)
        total_count = len(transactions)

        subscription_stats = {}
        for transaction in transactions:
            if transaction.amount == 100:
                subscription_stats['7_days'] = subscription_stats.get('7_days', 0) + 1
            elif transaction.amount == 180:
                subscription_stats['14_days'] = subscription_stats.get('14_days', 0) + 1
            elif transaction.amount == 300:
                subscription_stats['30_days'] = subscription_stats.get('30_days', 0) + 1

        return {
            'total_amount': total_amount,
            'total_count': total_count,
            'period_days': period_days,
            'subscription_stats': subscription_stats,
            'average_amount': total_amount / total_count if total_count > 0 else 0
        }

    except Exception as e:
        logging.error(f"Error retrieving statistics: {e}")
        return None


@router.message(F.text == "/payment_stats")
async def show_payment_stats(message: Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    try:
        async for db in get_db():
            stats = await get_payment_statistics(db, 30)

            if stats:
                stats_text = (
                    f"📊 <b>Payment statistics for 30 days</b>\n\n"
                    f"💰 Total amount: <b>{stats['total_amount']} Stars</b>\n"
                    f"📦 Number of payments: <b>{stats['total_count']}</b>\n"
                    f"📈 Average payment: <b>{stats['average_amount']:.1f} Stars</b>\n\n"
                    f"<b>By plan:</b>\n"
                    f"• 7 days: {stats['subscription_stats'].get('7_days', 0)} pcs\n"
                    f"• 14 days: {stats['subscription_stats'].get('14_days', 0)} pcs\n"
                    f"• 30 days: {stats['subscription_stats'].get('30_days', 0)} pcs"
                )

                await message.answer(stats_text, parse_mode='HTML')
            else:
                await message.answer("❌ Error retrieving statistics")

            break

    except Exception as e:
        logging.error(f"Error displaying statistics: {e}")
        await message.answer("❌ Error retrieving statistics")