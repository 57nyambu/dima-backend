"""
Quick Order SMS Test

This creates a test order and updates its status to verify SMS notifications work.

Usage: python quick_order_test.py <phone_number>
Example: python quick_order_test.py +254740620057
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Root.settings.base')
django.setup()

from apps.orders.models import Order, OrderItem
from apps.business.models import Business
from apps.products.models import Product
from apps.accounts.models import CustomUser
from decimal import Decimal
import time


def quick_test(phone_number):
    """Quick test of order SMS"""
    print(f"\n{'='*60}")
    print(f"QUICK ORDER SMS TEST")
    print(f"{'='*60}\n")
    print(f"Phone: {phone_number}\n")
    
    # Get test data
    user = CustomUser.objects.first()
    business = Business.objects.first()
    product = Product.objects.first()
    
    if not all([user, business, product]):
        print("❌ Missing required data (user, business, or product)")
        return False
    
    # Create order
    print("Creating order...")
    order = Order.objects.create(
        user=user,
        business=business,
        order_number=f"QUICKTEST-{int(time.time())}",
        status='pending',
        total=Decimal('1000.00'),
        customer_first_name='Quick',
        customer_last_name='Test',
        customer_phone=phone_number,
        customer_email='quicktest@example.com',
        payment_method='M-PESA'
    )
    
    # Add item
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=1,
        price=product.price
    )
    
    print(f"✅ Order created: {order.order_number}")
    print(f"📱 SMS #1 sent: Order confirmation\n")
    
    time.sleep(3)
    
    # Update to processing
    print("Updating to processing...")
    order.status = 'processing'
    order.save()
    print(f"✅ Status: processing")
    print(f"📱 SMS #2 sent: Processing\n")
    
    time.sleep(3)
    
    # Update to shipped
    print("Updating to shipped...")
    order.status = 'shipped'
    order.tracking_number = 'TEST123'
    order.save()
    print(f"✅ Status: shipped")
    print(f"📱 SMS #3 sent: Shipped (with tracking)\n")
    
    time.sleep(3)
    
    # Update to delivered
    print("Updating to delivered...")
    order.status = 'delivered'
    order.save()
    print(f"✅ Status: delivered")
    print(f"📱 SMS #4 sent: Delivered\n")
    
    print(f"{'='*60}")
    print(f"✅ TEST COMPLETE!")
    print(f"{'='*60}")
    print(f"Order: {order.order_number}")
    print(f"Phone: {phone_number}")
    print(f"SMS sent: 4 messages")
    print(f"\n📱 Check your phone for SMS messages!\n")
    
    # Cleanup
    cleanup = input("Delete test order? (y/n): ")
    if cleanup.lower() == 'y':
        order.delete()
        print("✓ Test order deleted")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python quick_order_test.py <phone_number>")
        print("Example: python quick_order_test.py +254740620057")
        sys.exit(1)
    
    phone = sys.argv[1]
    
    if not phone.startswith('+'):
        print("❌ Phone number must start with + (e.g., +254740620057)")
        sys.exit(1)
    
    print("\n⚠️  This will send 4 real SMS messages to", phone)
    proceed = input("Continue? (y/n): ")
    
    if proceed.lower() == 'y':
        quick_test(phone)
    else:
        print("Test cancelled.")
