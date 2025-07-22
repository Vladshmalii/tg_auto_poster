import logging
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv('BOT_TOKEN', ''))

    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/telegram_bot'))

    REDIS_URL: str = field(default_factory=lambda: os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

    CRYPTOBOT_TOKEN: str = field(default_factory=lambda: os.getenv('CRYPTOBOT_TOKEN', ''))

    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))

    TIMEZONE: str = field(default_factory=lambda: os.getenv('TIMEZONE', 'Europe/Moscow'))
    CELERY_ENABLE_UTC: bool = field(default_factory=lambda: os.getenv('CELERY_ENABLE_UTC', 'False').lower() == 'true')

    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',')
        if x.strip() and x.strip().isdigit()
    ])

    SUBSCRIPTION_PRICES: dict = field(default_factory=lambda: {
        7: 100,
        14: 180,
        30: 300
    })

    SUBSCRIPTION_IMAGES: dict = field(default_factory=lambda: {
        7: "https://imgpx.com/cg81JcyyUmN4.png",
        14: "https://imgpx.com/OinSqPAjYwfH.png",
        30: "https://imgpx.com/yEDBwNV81aL6.png"
    })

    WELCOME_IMAGE_URL: str = field(default='https://imgpx.com/JkQSWcWjA2IL.png')


settings = Settings()
