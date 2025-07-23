from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 My Profile", callback_data="my_profile")],
        [
            InlineKeyboardButton(text="🧪 Test Posting", callback_data="test_post"),
            InlineKeyboardButton(text="💎 Buy Subscription", callback_data="buy_subscription")
        ],
        [
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            InlineKeyboardButton(text="🆘 Support", callback_data="support")
        ]
    ])
    return keyboard


def get_profile_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Subscription", callback_data="profile_subscription")],
        [InlineKeyboardButton(text="💳 Payment History", callback_data="profile_payments")],
        [InlineKeyboardButton(text="🎁 Gift Subscriptions", callback_data="profile_gifts")],
        [InlineKeyboardButton(text="⚙️ Posting Settings", callback_data="profile_posting_settings")],
        [InlineKeyboardButton(text="🔧 Settings", callback_data="profile_settings")],
        [InlineKeyboardButton(text="❓ Help", callback_data="profile_help")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="back_to_main")]
    ])
    return keyboard


def get_posting_settings_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 My Channels", callback_data="posting_channels")],
        [InlineKeyboardButton(text="📂 Select Categories", callback_data="posting_categories")],
        [InlineKeyboardButton(text="🎨 Post Style", callback_data="posting_style")],
        [InlineKeyboardButton(text="⏰ Schedule", callback_data="posting_schedule")],
        [InlineKeyboardButton(text="🔔 Notifications", callback_data="posting_notifications")],
        [InlineKeyboardButton(text="⬅️ Back to Profile", callback_data="profile_back")]
    ])
    return keyboard


def get_style_selection_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎩 Formal", callback_data="set_style_formal")],
        [InlineKeyboardButton(text="😎 Casual", callback_data="set_style_casual")],
        [InlineKeyboardButton(text="🤪 Meme", callback_data="set_style_meme")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="profile_posting_settings")]
    ])
    return keyboard


def get_schedule_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ 1 time per day", callback_data="schedule_1")],
        [InlineKeyboardButton(text="2️⃣ 2 times per day", callback_data="schedule_2")],
        [InlineKeyboardButton(text="3️⃣ 3 times per day", callback_data="schedule_3")],
        [InlineKeyboardButton(text="⏰ Set time", callback_data="schedule_custom")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="profile_posting_settings")]
    ])
    return keyboard


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="7 days - 100 ⭐", callback_data="sub_7"),
        InlineKeyboardButton(text="14 days - 180 ⭐", callback_data="sub_14")
    )
    builder.row(
        InlineKeyboardButton(text="30 days - 300 ⭐", callback_data="sub_30")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Back", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    categories = [
        ("💻 IT & Tech", "cat_it"),
        ("₿ Crypto", "cat_crypto"),
        ("💼 Business", "cat_business"),
        ("🌍 General News", "cat_general"),
        ("🎮 Esports", "cat_esports"),
        ("📱 Technology", "cat_tech"),
        ("🏛️ Politics", "cat_politics"),
        ("🔬 Science", "cat_science"),
        ("🚗 Auto", "cat_auto"),
        ("💊 Health", "cat_health"),
        ("🎭 Entertainment", "cat_entertainment"),
        ("⚽ Sport", "cat_sport")
    ]

    for text, callback in categories:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data="back_to_main"))

    return builder.as_markup()


def get_style_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    styles = [
        ("🎩 Formal", "style_formal"),
        ("😎 Casual", "style_casual"),
        ("🤪 Meme", "style_meme")
    ]

    for text, callback in styles:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    builder.row(InlineKeyboardButton(text="◀️ Back", callback_data="select_category"))

    return builder.as_markup()


def get_bot_check_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Check", callback_data="check_bot_added")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Back", callback_data="select_style")
    )

    return builder.as_markup()


def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📰 Sources", callback_data="admin_sources")],
        [InlineKeyboardButton(text="📂 Categories", callback_data="admin_categories")],
        [InlineKeyboardButton(text="🔐 API Tokens", callback_data="admin_tokens")],
        [InlineKeyboardButton(text="🌐 Sites", callback_data="admin_sites")],
        [InlineKeyboardButton(text="📜 Logs", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🏠 Exit Admin", callback_data="back_to_main")]
    ])
    return keyboard


def get_admin_back_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_users_keyboard(page: int = 0, total_pages: int = 1):
    keyboard = []

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"admin_users_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_users_page_{page + 1}"))
        keyboard.append(nav_buttons)

    keyboard.extend([
        [InlineKeyboardButton(text="➕ Add Subscription", callback_data="admin_add_subscription")],
        [InlineKeyboardButton(text="🗑 Disable Subscription", callback_data="admin_disable_subscription")],
        [InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_sources_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Source List", callback_data="admin_list_sources")],
        [InlineKeyboardButton(text="➕ Add Source", callback_data="admin_add_source")],
        [InlineKeyboardButton(text="🗑 Delete Source", callback_data="admin_delete_source")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_categories_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Category List", callback_data="admin_list_categories")],
        [InlineKeyboardButton(text="➕ Add Category", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="🗑 Delete Category", callback_data="admin_delete_category")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_tokens_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Token List", callback_data="admin_list_tokens")],
        [InlineKeyboardButton(text="➕ Create Token", callback_data="admin_create_token")],
        [InlineKeyboardButton(text="🗑 Delete Token", callback_data="admin_delete_token")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_sites_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Site List", callback_data="admin_list_sites")],
        [InlineKeyboardButton(text="➕ Add Site", callback_data="admin_add_site")],
        [InlineKeyboardButton(text="🗑 Delete Site", callback_data="admin_delete_site")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_admin_logs_keyboard(page: int = 0, total_pages: int = 1):
    keyboard = []

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"admin_logs_page_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_logs_page_{page + 1}"))
        keyboard.append(nav_buttons)

    keyboard.extend([
        [InlineKeyboardButton(text="🔍 Filter by Type", callback_data="admin_filter_logs")],
        [InlineKeyboardButton(text="🗑 Clear Old", callback_data="admin_clear_logs")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(action: str, item_id: str = ""):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back")
        ]
    ])
    return keyboard


def get_admin_stats_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Last 7 days", callback_data="admin_stats_7")],
        [InlineKeyboardButton(text="📊 Last 30 days", callback_data="admin_stats_30")],
        [InlineKeyboardButton(text="📊 All time", callback_data="admin_stats_all")],
        [InlineKeyboardButton(text="💾 Export to CSV", callback_data="admin_export_stats")],
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_back")]
    ])
    return keyboard


def get_autopost_setup_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Create New Setup", callback_data="autopost_new")],
        [InlineKeyboardButton(text="✏️ Edit Existing", callback_data="autopost_edit")],
        [InlineKeyboardButton(text="📤 Manual Post", callback_data="manual_post")],
        [InlineKeyboardButton(text="🗑 Delete Setup", callback_data="autopost_delete")],
        [InlineKeyboardButton(text="⬅️ Back to Profile", callback_data="profile_back")]
    ])
    return keyboard


def get_autopost_step_keyboard(step: str, has_back: bool = True):
    keyboard = []

    if step == "channels":
        keyboard.extend([
            [InlineKeyboardButton(text="➕ Add Channel", callback_data="autopost_add_channel")],
            [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")]
        ])
    elif step == "categories":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")]
        ])
    elif step == "style":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")]
        ])
    elif step == "schedule":
        keyboard.extend([
            [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")]
        ])

    if has_back:
        keyboard.append([InlineKeyboardButton(text="⬅️ Back", callback_data="autopost_back_step")])

    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="autopost_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_selection_keyboard_new(selected_categories: list = None):
    if selected_categories is None:
        selected_categories = []

    categories = [
        ("it", "💻 IT & Tech"),
        ("crypto", "₿ Crypto"),
        ("business", "💼 Business"),
        ("general", "🌍 General News"),
        ("esports", "🎮 Esports"),
        ("tech", "📱 Technology"),
        ("politics", "🏛️ Politics"),
        ("science", "🔬 Science"),
        ("auto", "🚗 Auto"),
        ("health", "💊 Health"),
        ("entertainment", "🎭 Entertainment"),
        ("sport", "⚽ Sport")
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
        [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_style_selection_keyboard_new(selected_style: str = None):
    styles = [
        ("formal", "🎩 Formal"),
        ("casual", "😎 Casual"),
        ("meme", "🤪 Meme")
    ]

    keyboard = []
    for style_id, style_name in styles:
        text = f"✅ {style_name}" if style_id == selected_style else style_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"autopost_set_style_{style_id}")])

    keyboard.extend([
        [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_selection_keyboard_new(selected_frequency: int = None):
    schedules = [
        (1, "1️⃣ 1 time per day (09:00)"),
        (2, "2️⃣ 2 times per day (09:00, 21:00)"),
        (3, "3️⃣ 3 times per day (09:00, 15:00, 21:00)")
    ]

    keyboard = []
    for freq, freq_name in schedules:
        text = f"✅ {freq_name}" if freq == selected_frequency else freq_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=f"autopost_set_schedule_{freq}")])

    keyboard.extend([
        [InlineKeyboardButton(text="✅ Continue", callback_data="autopost_next_step")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="autopost_back_step")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="autopost_cancel")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard_autopost():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Save Settings", callback_data="autopost_save_all")],
        [InlineKeyboardButton(text="✏️ Edit", callback_data="autopost_edit_settings")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="autopost_cancel")]
    ])
    return keyboard


def get_manual_post_keyboard(limit_reached=False):

    buttons = []

    if not limit_reached:
        buttons.extend([
            [InlineKeyboardButton(text="🚀 Send Now", callback_data="manual_send_now")],
            [InlineKeyboardButton(text="⏰ Schedule", callback_data="manual_schedule")]
        ])
    else:
        buttons.append([InlineKeyboardButton(text="⏰ Schedule for Tomorrow", callback_data="manual_schedule")])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="my_profile")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_manual_schedule_cancel_keyboard():

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="my_profile")]
    ])
