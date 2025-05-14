from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from apps.business.models import BusinessReview

@receiver(post_save, sender=Order)
def update_business_review_order_counts(sender, instance, created, **kwargs):
    if not created and hasattr(instance, '_previous_status'):
        prev = instance._previous_status
        curr = instance.status
        if prev != curr:
            review, _ = BusinessReview.objects.get_or_create(
                user=instance.user,
                product=instance.business,
                defaults={'rating': 1}
            )
            if curr == 'delivered':
                review.orders_complete += 1
            elif curr == 'pending':
                review.orders_pending += 1
            elif curr == 'cancelled':
                review.canceled_orders += 1
            review.save()