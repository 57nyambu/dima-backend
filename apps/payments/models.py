from django.db import models
from orders.models import Order

class Payment(models.Model):
    """Core payment model with MPesa support"""
    MPESA = 'mpesa'
    CASH = 'cash'
    CARD = 'card'
    PAYMENT_METHODS = [
        (MPESA, 'M-Pesa'),
        (CASH, 'Cash on Delivery'),
        (CARD, 'Credit/Debit Card'),
    ]

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # M-Pesa Specific Fields
    mpesa_code = models.CharField(max_length=20, blank=True)  # e.g. NLJ7RT56
    mpesa_phone = models.CharField(max_length=15, blank=True)  # Format: 254722123456
    
    # Payment lifecycle
    is_confirmed = models.BooleanField(default=False)
    is_settled = models.BooleanField(default=False)  # Released to seller
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['mpesa_code']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"Payment #{self.id} for Order {self.order.id}"

class PaymentSettlement(models.Model):
    """Records when payments are released to businesses"""
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee = models.DecimalField(max_digits=10, decimal_places=2)  # Platform commission
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    settled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Payment Settlements"