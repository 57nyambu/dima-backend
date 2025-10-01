# marketplace/celery.py (if using Celery)
from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

app = Celery('marketplace')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'update-search-indexes': {
        'task': 'marketplace.utils.update_search_indexes',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'cleanup-abandoned-carts': {
        'task': 'marketplace.utils.cleanup_abandoned_carts',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
    },
}