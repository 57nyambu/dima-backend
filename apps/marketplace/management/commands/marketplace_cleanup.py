# marketplace/management/commands/marketplace_cleanup.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from marketplace.models import Cart, MarketplaceNotification


class Command(BaseCommand):
    help = 'Clean up old marketplace data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=10,
            help='Number of days to keep data (default: 10)'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f'Cleaning up data older than {days} days...')
        
        # Clean up abandoned carts
        abandoned_carts = Cart.objects.filter(
            updated_at__lt=cutoff_date,
            items__isnull=True
        )
        cart_count = abandoned_carts.count()
        abandoned_carts.delete()
        
        # Clean up old read notifications
        old_notifications = MarketplaceNotification.objects.filter(
            created_at__lt=cutoff_date,
            is_read=True
        )
        notification_count = old_notifications.count()
        old_notifications.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned up {cart_count} carts and {notification_count} notifications'
            )
        )


