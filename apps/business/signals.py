from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Business

@receiver(post_save, sender=Business)
def business_post_save(sender, instance, created, **kwargs):
    if created:
        # Notify admin for verification
        send_mail(
            'New Business Pending Verification',
            f'Business "{instance.name}" requires verification.',
            'no-reply@example.com',
            ['admin@example.com'],
        )
    else:
        # Notify owner if verification status changed
        if 'verification_status' in instance.get_deferred_fields():
            send_mail(
                'Business Verification Status Changed',
                f'Your business "{instance.name}" is now {instance.verification_status}.',
                'no-reply@example.com',
                [instance.owner.email],
            )