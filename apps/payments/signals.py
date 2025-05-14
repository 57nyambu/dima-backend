from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import Payment, PaymentSettlement

@receiver(post_save, sender=Order)
def handle_order_delivery(sender, instance, **kwargs):
    """Release payment to seller when order is delivered"""
    if instance.status == 'delivered' and hasattr(instance, 'payment'):
        payment = instance.payment
        
        if payment.is_confirmed and not payment.is_settled:
            # Calculate platform fee (e.g., 5%)
            platform_fee = payment.amount * 0.05
            net_amount = payment.amount - platform_fee
            
            # Create settlement record
            PaymentSettlement.objects.create(
                payment=payment,
                business=instance.business,
                amount=payment.amount,
                fee=platform_fee,
                net_amount=net_amount
            )
            
            # Update business wallet balance
            wallet = instance.business.wallet
            wallet.balance += net_amount
            wallet.save()
            
            # Mark payment as settled
            payment.is_settled = True
            payment.save()
            
            # TODO: Send settlement notification to business