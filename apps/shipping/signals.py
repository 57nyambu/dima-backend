from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Shipment

@receiver(post_save, sender=Shipment)
def update_order_status_on_delivery(sender, instance, **kwargs):
    if instance.status == 'delivered':
        order = instance.order
        if order.status != 'delivered':
            order.status = 'delivered'
            order.save()