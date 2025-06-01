from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription"),
        InlineKeyboardButton(text="🧪 Тест пост", callback_data="test_post")
    )
    builder.row(
        InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
    )

    return builder.as_markup()


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора тарифа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="7 дней - 100 ⭐", callback_data="sub_7"),
        InlineKeyboardButton(text="14 дней - 180 ⭐", callback_data="sub_14")
    )
    builder.row(
        InlineKeyboardButton(text="30 дней - 300 ⭐", callback_data="sub_30")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_category_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора категории новостей"""
    builder = InlineKeyboardBuilder()

    categories = [
        ("💻 IT & Tech", "cat_it"),
        ("₿ Криптовалюты", "cat_crypto"),
        ("💼 Бизнес", "cat_business"),
        ("🌍 Общие новости", "cat_general"),
        ("🎮 Киберспорт", "cat_esports"),
        ("📱 Технологии", "cat_tech"),
        ("🏛️ Политика", "cat_politics"),
        ("🔬 Наука", "cat_science"),
        ("🚗 Авто", "cat_auto"),
        ("💊 Здоровье", "cat_health"),
        ("🎭 Развлечения", "cat_entertainment"),
        ("⚽ Спорт", "cat_sport")
    ]

    for text, callback in categories:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))

    return builder.as_markup()


def get_style_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора стиля оформления"""
    builder = InlineKeyboardBuilder()

    styles = [
        ("🎩 Формальный", "style_formal"),
        ("😎 Разговорный", "style_casual"),
        ("🤪 Мемный", "style_meme")
    ]

    for text, callback in styles:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="select_category"))

    return builder.as_markup()


def get_bot_check_keyboard() -> InlineKeyboardMarkup:
    """Кнопка проверки добавления бота"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Проверить", callback_data="check_bot_added")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="select_style")
    )

    return builder.as_markup()

def get_admin_keyboard():
    """Клавиатура админ панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 Добавить источник", callback_data="admin_add_source")],
        [InlineKeyboardButton(text="📂 Добавить категорию", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="📊 Статистика покупок", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Список подписчиков", callback_data="admin_users")],
        [InlineKeyboardButton(text="🏠 Выйти из админки", callback_data="back_to_main")]
    ])
    return keyboard


def get_admin_back_keyboard():
    """Клавиатура с кнопкой назад для админки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard