from celery import Celery
from celery.schedules import crontab
from config.settings import settings

celery_app = Celery(
    'telegram_bot',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',  # Принудительно устанавливаем Moscow timezone
    enable_utc=False,          # Отключаем UTC

    task_always_eager=False,
    task_eager_propagates=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    broker_connection_retry_on_startup=True,
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    },

    result_expires=3600,
    result_persistent=True,

    beat_scheduler='celery.beat:PersistentScheduler',
    beat_schedule_filename='celerybeat-schedule',

    beat_schedule={
        'process-autoposts': {
            'task': 'tasks.process_autoposts',
            'schedule': 3600.0,
        },
        'send-scheduled-posts': {
            'task': 'tasks.send_scheduled_posts',
            'schedule': 300.0,
        },
        'cleanup-old-test-posts': {
            'task': 'tasks.cleanup_old_test_post_limits',
            'schedule': crontab(hour=2, minute=0),
        },
        'check-subscription-expiry': {
            'task': 'tasks.check_subscription_expiry',
            'schedule': crontab(hour='*/6', minute=0),
        },
        'cleanup-expired-subscriptions': {
            'task': 'tasks.cleanup_expired_subscriptions',
            'schedule': crontab(hour=1, minute=0),
        },
        'generate-daily-analytics': {
            'task': 'tasks.generate_analytics_report',
            'schedule': crontab(hour=9, minute=0),
        },
        'backup-database': {
            'task': 'tasks.backup_database',
            'schedule': crontab(hour=3, minute=0),
        },
        'health-check': {
            'task': 'tasks.health_check',
            'schedule': crontab(minute='*/30'),
        },
    },
)