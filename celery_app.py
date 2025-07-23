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
    timezone='Europe/Moscow',
    enable_utc=False,

    task_always_eager=False,
    task_eager_propagates=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_ignore_result=True,

    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            'TCP_KEEPIDLE': 1,
            'TCP_KEEPINTVL': 3,
            'TCP_KEEPCNT': 5,
        },
    },

    result_expires=3600,
    result_persistent=True,
    result_backend_transport_options={
        'socket_keepalive': True,
        'socket_keepalive_options': {
            'TCP_KEEPIDLE': 1,
            'TCP_KEEPINTVL': 3,
            'TCP_KEEPCNT': 5,
        },
    },

    beat_scheduler='celery.beat:PersistentScheduler',
    beat_schedule_filename='celerybeat-schedule',

    worker_disable_rate_limits=True,
    worker_max_tasks_per_child=1000,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',

    beat_schedule={
        'process-autoposts': {
            'task': 'tasks.process_autoposts',
            'schedule': 3600.0,
            'options': {
                'expires': 3500,
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 60,
                    'interval_max': 300,
                }
            }
        },
        'send-scheduled-posts': {
            'task': 'tasks.send_scheduled_posts',
            'schedule': 300.0,
            'options': {
                'expires': 250,
                'retry': True,
                'retry_policy': {
                    'max_retries': 2,
                    'interval_start': 0,
                    'interval_step': 30,
                    'interval_max': 120,
                }
            }
        },
        'cleanup-old-test-posts': {
            'task': 'tasks.cleanup_old_test_post_limits',
            'schedule': crontab(hour=2, minute=0),
            'options': {
                'expires': 3600,
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 300,
                }
            }
        },
        'check-subscription-expiry': {
            'task': 'tasks.check_subscription_expiry',
            'schedule': crontab(hour='*/6', minute=0),
            'options': {
                'expires': 3600,
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 300,
                }
            }
        },
        'cleanup-expired-subscriptions': {
            'task': 'tasks.cleanup_expired_subscriptions',
            'schedule': crontab(hour=1, minute=0),
            'options': {
                'expires': 3600,
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 300,
                }
            }
        },
        'generate-daily-analytics': {
            'task': 'tasks.generate_analytics_report',
            'schedule': crontab(hour=9, minute=0),
            'options': {
                'expires': 3600,
                'retry': True,
                'retry_policy': {
                    'max_retries': 2,
                    'interval_start': 0,
                    'interval_step': 300,
                }
            }
        },
        'backup-database': {
            'task': 'tasks.backup_database',
            'schedule': crontab(hour=3, minute=0),
            'options': {
                'expires': 3600,
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 600,
                }
            }
        },
        'health-check': {
            'task': 'tasks.health_check',
            'schedule': crontab(minute='*/30'),
            'options': {
                'expires': 1800,
                'retry': False,
            }
        },
    },
)