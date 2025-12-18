"""
Django management command to generate order numbers for existing orders

Usage:
    python manage.py generate_order_numbers
"""

from django.core.management.base import BaseCommand
from apps.orders.models import Order
import uuid
from datetime import datetime


class Command(BaseCommand):
    help = 'Generate order numbers for existing orders that don\'t have one'

    def handle(self, *args, **options):
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS("Generating Order Numbers"))
        self.stdout.write("="*70)

        # Find orders without order numbers
        orders_without_numbers = Order.objects.filter(order_number__isnull=True)
        count = orders_without_numbers.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ All orders already have order numbers!"))
            return

        self.stdout.write(f"\nFound {count} orders without order numbers")
        self.stdout.write("Generating order numbers...\n")

        updated = 0
        for order in orders_without_numbers:
            # Use order creation date for the order number
            date_str = order.created_at.strftime('%Y%m%d')
            unique_id = str(uuid.uuid4())[:4].upper()
            order_number = f"ORD-{date_str}-{unique_id}"
            
            order.order_number = order_number
            order.save(update_fields=['order_number'])
            
            self.stdout.write(f"  ✓ Order {order.id} → {order_number}")
            updated += 1

        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS(f"✅ Updated {updated} orders with order numbers!"))
        self.stdout.write("="*70 + "\n")
