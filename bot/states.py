from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    main_menu = State()
    viewing_profile = State()

    autopost_setup = State()
    adding_channel = State()
    selecting_categories = State()
    selecting_style = State()
    selecting_schedule = State()
    confirming_settings = State()
    scheduling_manual_post = State()
    selecting_category = State()
    selecting_style_test = State()
    waiting_channel_setup = State()
    checking_bot_permissions = State()

    selecting_subscription = State()
    waiting_payment = State()


class AdminStates(StatesGroup):
    main_menu = State()

    
    adding_subscription = State()
    disabling_subscription = State()
    searching_user = State()

    
    adding_source = State()
    deleting_source = State()

    
    adding_category = State()
    deleting_category = State()

    
    creating_token = State()
    deleting_token = State()

    
    adding_site = State()
    deleting_site = State()

    
    viewing_stats = State()
    viewing_users = State()
    viewing_logs = State()