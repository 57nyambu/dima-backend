from django.db import models
from apps.accounts.models import CustomUser
from apps.products.models import Product
from apps.business.models import Business

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_code = models.CharField(max_length=20, blank=True)
    shipping_method = models.CharField(max_length=50, blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_delivery = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(max_length=30, blank=True, null=True)
    qsetent_status = models.CharField(max_length=30, blank=True, null=True)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)
    courier = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:
            orig = Order.objects.get(pk=self.pk)
            self._previous_status = orig.status
        else:
            self._previous_status = None
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

    def __str__(self):
        return f"Order {self.id} - {self.user.username} - {self.business.name} - {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # price at order time