from celery import Celery
from config.settings import settings

# Создаем приложение Celery
celery_app = Celery(
    'telegram_bot',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Настройки Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'process-autoposts': {
            'task': 'tasks.process_autoposts',
            'schedule': 3600.0,
        },
        'cleanup-old-test-posts': {
            'task': 'tasks.cleanup_old_test_post_limits',
            'schedule': 86400.0,
        },
    },
)

