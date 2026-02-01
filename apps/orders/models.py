from django.db import models
from apps.accounts.models import CustomUser
from apps.products.models import Product
from apps.business.models import Business

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Core order fields
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Customer information (stored at order time)
    customer_first_name = models.CharField(max_length=225, blank=True)
    customer_last_name = models.CharField(max_length=225, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    
    # Delivery information
    delivery_county = models.CharField(max_length=100, blank=True)
    delivery_town = models.CharField(max_length=100, blank=True)
    delivery_location = models.CharField(max_length=255, blank=True)
    delivery_notes = models.TextField(blank=True)
    
    # Shipping details
    shipping_method = models.CharField(max_length=50, blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=200)
    estimated_delivery = models.DateTimeField(blank=True, null=True)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)
    courier = models.CharField(max_length=50, blank=True, null=True)
    
    # Payment information
    payment_method = models.CharField(max_length=30, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    mpesa_code = models.CharField(max_length=50, blank=True)
    qsetent_status = models.CharField(max_length=30, blank=True, null=True)  # Legacy field
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Store previous status for signal detection
        if self.pk:
            orig = Order.objects.get(pk=self.pk)
            self._previous_status = orig.status
        else:
            self._previous_status = None
        
        # Generate order number if not set
        if not self.order_number:
            import uuid
            from datetime import datetime
            # Format: ORD-YYYYMMDD-XXXX (e.g., ORD-20251218-A1B2)
            date_str = datetime.now().strftime('%Y%m%d')
            unique_id = str(uuid.uuid4())[:4].upper()
            self.order_number = f"ORD-{date_str}-{unique_id}"
        
        super().save(*args, **kwargs)

    def total_amount(self):
        return sum(item.price * item.quantity for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    def vendors_summary(self):
        summary = {}
        for item in self.items.all():
            vendor = item.product.business
            if vendor not in summary:
                summary[vendor] = {
                    'total_sales': 0,
                    'total_items': 0
                }
            summary[vendor]['total_sales'] += item.price * item.quantity
            summary[vendor]['total_items'] += item.quantity
        return summary

    def get_customer_name(self):
        """Returns the full name of the customer at order time."""
        return f"{self.customer_first_name} {self.customer_last_name}".strip()
    
    def get_delivery_address(self):
        """Returns the formatted delivery address."""
        parts = [self.delivery_location, self.delivery_town, self.delivery_county]
        return ", ".join([p for p in parts if p])

    def __str__(self):
        return f"Order {self.id} - {self.user.username} - {self.business.name} - {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # price at order time