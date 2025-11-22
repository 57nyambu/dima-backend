from django.db import models
from apps.orders.models import Order
from apps.accounts.models import CustomUser

class CustomerDeliveryAddress(models.Model):
    """Stores customer's saved delivery addresses for quick checkout"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='delivery_addresses')
    county = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    specific_location = models.CharField(max_length=255)
    delivery_notes = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name = "Customer Delivery Address"
        verbose_name_plural = "Customer Delivery Addresses"

    def __str__(self):
        return f"{self.user.email} - {self.town}, {self.county}"

    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for this user
        if self.is_default:
            CustomerDeliveryAddress.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class ShippingAddress(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_address')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name}, {self.address}, {self.city}"

class ShippingOption(models.Model):
    pass
class ShippingMethod(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    estimated_days = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.name} ({self.estimated_days} days)"

class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    method = models.ForeignKey(ShippingMethod, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=30, choices=[
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
    ], default='pending')
    tracking_number = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shipment for Order {self.order.id} - {self.status}"