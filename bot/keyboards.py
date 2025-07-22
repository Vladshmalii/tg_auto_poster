from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
        [
            InlineKeyboardButton(text="🧪 Тестовый постинг", callback_data="test_post"),
            InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription")
        ],
        [
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
        ]
    ])
    return keyboard


def get_profile_keyboard():
    """Клавиатура профиля пользователя"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Подписка", callback_data="profile_subscription")],
        [InlineKeyboardButton(text="💳 История платежей", callback_data="profile_payments")],
        [InlineKeyboardButton(text="🎁 Подарочные подписки", callback_data="profile_gifts")],
        [InlineKeyboardButton(text="⚙️ Настройки постинга", callback_data="profile_posting_settings")],
        [InlineKeyboardButton(text="🔧 Настройки", callback_data="profile_settings")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="profile_help")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
    ])
    return keyboard


def get_posting_settings_keyboard():
    """Клавиатура настроек постинга"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Мои каналы", callback_data="posting_channels")],
        [InlineKeyboardButton(text="📂 Выбрать категории", callback_data="posting_categories")],
        [InlineKeyboardButton(text="🎨 Стиль постов", callback_data="posting_style")],
        [InlineKeyboardButton(text="⏰ Расписание", callback_data="posting_schedule")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="posting_notifications")],
        [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="profile_back")]
    ])
    return keyboard


def get_style_selection_keyboard():
    """Клавиатура выбора стиля постов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎩 Формальный", callback_data="set_style_formal")],
        [InlineKeyboardButton(text="😎 Разговорный", callback_data="set_style_casual")],
        [InlineKeyboardButton(text="🤪 Мемный", callback_data="set_style_meme")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_posting_settings")]
    ])
    return keyboard


def get_schedule_keyboard():
    """Клавиатура настройки расписания"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ 1 раз в день", callback_data="schedule_1")],
        [InlineKeyboardButton(text="2️⃣ 2 раза в день", callback_data="schedule_2")],
        [InlineKeyboardButton(text="3️⃣ 3 раза в день", callback_data="schedule_3")],
        [InlineKeyboardButton(text="⏰ Настроить время", callback_data="schedule_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_posting_settings")]
    ])
    return keyboard


def get_subscription_keyboard() -> InlineKeyboardMarkup:
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
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Проверить", callback_data="check_bot_added")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="select_style")
    )

    return builder.as_markup()


def get_admin_keyboard():
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
    return keyboard


def get_admin_back_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_users_keyboard(page: int = 0, total_pages: int = 1):
    keyboard = []

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред", callback_data=f"admin_users_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="След ➡️", callback_data=f"admin_users_page_{page + 1}"))
        keyboard.append(nav_buttons)

    keyboard.extend([
        [InlineKeyboardButton(text="➕ Добавить подписку", callback_data="admin_add_subscription")],
        [InlineKeyboardButton(text="🗑 Отключить подписку", callback_data="admin_disable_subscription")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_sources_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список источников", callback_data="admin_list_sources")],
        [InlineKeyboardButton(text="➕ Добавить источник", callback_data="admin_add_source")],
        [InlineKeyboardButton(text="🗑 Удалить источник", callback_data="admin_delete_source")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_categories_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список категорий", callback_data="admin_list_categories")],
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="🗑 Удалить категорию", callback_data="admin_delete_category")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_tokens_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список токенов", callback_data="admin_list_tokens")],
        [InlineKeyboardButton(text="➕ Создать токен", callback_data="admin_create_token")],
        [InlineKeyboardButton(text="🗑 Удалить токен", callback_data="admin_delete_token")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_sites_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список сайтов", callback_data="admin_list_sites")],
        [InlineKeyboardButton(text="➕ Добавить сайт", callback_data="admin_add_site")],
        [InlineKeyboardButton(text="🗑 Удалить сайт", callback_data="admin_delete_site")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_logs_keyboard(page: int = 0, total_pages: int = 1):
    keyboard = []

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред", callback_data=f"admin_logs_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="След ➡️", callback_data=f"admin_logs_page_{page + 1}"))
        keyboard.append(nav_buttons)

    keyboard.extend([
        [InlineKeyboardButton(text="🔍 Фильтр по типу", callback_data="admin_filter_logs")],
        [InlineKeyboardButton(text="🗑 Очистить старые", callback_data="admin_clear_logs")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(action: str, item_id: str = ""):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")
        ]
    ])
    return keyboard


def get_admin_stats_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 За 7 дней", callback_data="admin_stats_7")],
        [InlineKeyboardButton(text="📊 За 30 дней", callback_data="admin_stats_30")],
        [InlineKeyboardButton(text="📊 За всё время", callback_data="admin_stats_all")],
        [InlineKeyboardButton(text="💾 Экспорт в CSV", callback_data="admin_export_stats")],
        [InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_back")]
    ])
    return keyboard


def get_autopost_setup_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Создать новую настройку", callback_data="autopost_new")],
        [InlineKeyboardButton(text="✏️ Редактировать существующую", callback_data="autopost_edit")],
        [InlineKeyboardButton(text="📤 Ручная отправка", callback_data="manual_post")],
        [InlineKeyboardButton(text="🗑 Удалить настройку", callback_data="autopost_delete")],
        [InlineKeyboardButton(text="⬅️ Назад к профилю", callback_data="profile_back")]
    ])
    return keyboard


def get_autopost_step_keyboard(step: str, has_back: bool = True):
    keyboard = []

    if step == "channels":
        keyboard.extend([
            [InlineKeyboardButton(text="➕ Добавить канал", callback_data="autopost_add_channel")],
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")]
        ])
    elif step == "categories":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")]
        ])
    elif step == "style":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")]
        ])
    elif step == "schedule":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")]
        ])

    if has_back:
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="autopost_back_step")])

    keyboard.append([InlineKeyboardButton(text="❌ Отменить", callback_data="autopost_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_selection_keyboard_new(selected_categories: list = None):
    if selected_categories is None:
        selected_categories = []

    categories = [
        ("it", "💻 IT & Tech"),
        ("crypto", "₿ Криптовалюты"),
        ("business", "💼 Бизнес"),
        ("general", "🌍 Общие новости"),
        ("esports", "🎮 Киберспорт"),
        ("tech", "📱 Технологии"),
        ("politics", "🏛️ Политика"),
        ("science", "🔬 Наука"),
        ("auto", "🚗 Авто"),
        ("health", "💊 Здоровье"),
        ("entertainment", "🎭 Развлечения"),
        ("sport", "⚽ Спорт")
    ]

    keyboard = []
    row = []

    for cat_id, cat_name in categories:
        text = f"✅ {cat_name}" if cat_id in selected_categories else cat_name
        button = InlineKeyboardButton(text=text, callback_data=f"autopost_toggle_cat_{cat_id}")
        row.append(button)

        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.extend([
        [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_style_selection_keyboard_new(selected_style: str = None):
    styles = [
        ("formal", "🎩 Формальный"),
        ("casual", "😎 Разговорный"),
        ("meme", "🤪 Мемный")
    ]

    keyboard = []
    for style_id, style_name in styles:
        text = f"✅ {style_name}" if style_id == selected_style else style_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"autopost_set_style_{style_id}")])

    keyboard.extend([
        [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_selection_keyboard_new(selected_frequency: int = None):
    schedules = [
        (1, "1️⃣ 1 раз в день (09:00)"),
        (2, "2️⃣ 2 раза в день (09:00, 21:00)"),
        (3, "3️⃣ 3 раза в день (09:00, 15:00, 21:00)")
    ]

    keyboard = []
    for freq, freq_name in schedules:
        text = f"✅ {freq_name}" if freq == selected_frequency else freq_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"autopost_set_schedule_{freq}")])

    keyboard.extend([
        [InlineKeyboardButton(text="✅ Продолжить", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard_autopost():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить настройки", callback_data="autopost_save_all")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="autopost_edit_settings")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="autopost_cancel")]
    ])
    return keyboard


def get_manual_post_keyboard(limit_reached=False):

    buttons = []

    if not limit_reached:
        buttons.extend([
            [InlineKeyboardButton(text="🚀 Отправить сейчас", callback_data="manual_send_now")],
            [InlineKeyboardButton(text="⏰ Запланировать", callback_data="manual_schedule")]
        ])
    else:
        # Если лимит достигнут, показываем только планирование
        buttons.append([InlineKeyboardButton(text="⏰ Запланировать на завтра", callback_data="manual_schedule")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="my_profile")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_manual_schedule_cancel_keyboard():

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="my_profile")]
    ])
