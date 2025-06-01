from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    # Главное меню
    main_menu = State()

    # Тестовый постинг
    selecting_category = State()
    selecting_style = State()
    waiting_channel_setup = State()
    checking_bot_permissions = State()

    # Покупка подписки
    selecting_subscription = State()
    waiting_payment = State()

    # Настройки автопостинга
    configuring_autopost = State()

class AdminStates(StatesGroup):
    """Состояния для админ панели"""
    main_menu = State()
    adding_source = State()
    adding_category = State()
    viewing_stats = State()
    viewing_users = State()
