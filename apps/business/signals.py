from django.db.models.signals import post_save, pre_save, post_migrate
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Business, BusinessPermission, BusinessRole, BusinessTeamInvitation
from .permissions import BusinessPermissions
from apps.notifications.tasks import send_business_verification_notification
from django.utils import timezone

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

@receiver(post_save, sender=Business)
def handle_business_verification(sender, instance, created, **kwargs):
    """
    Handles verification status changes and notifications
    """
    if not created:
        # Check if verification status changed
        try:
            old = Business.objects.get(pk=instance.pk)
            if old.verification_status != instance.verification_status:
                from notifications.tasks import send_business_verification_notification
                send_business_verification_notification.delay(
                    business_id=instance.id,
                    old_status=old.verification_status,
                    new_status=instance.verification_status
                )
                
                # Update verification timestamp if newly verified
                if instance.verification_status == 'verified' and not instance.verified_at:
                    instance.verified_at = timezone.now()
                    instance.save(update_fields=['verified_at'])
        except Business.DoesNotExist:
            pass

@receiver(post_save, sender=BusinessTeamInvitation)
def handle_team_invitation(sender, instance, created, **kwargs):
    """
    Sends invitation email when new invitation is created
    """
    if created:
        from notifications.tasks import send_team_invitation_email
        send_team_invitation_email.delay(invitation_id=instance.id)

@receiver(post_migrate)
def sync_permissions(sender, **kwargs):
    """
    Ensures all permissions defined in BusinessPermissions exist in the database
    and removes obsolete ones.
    """
    if sender.name != 'business':  # Only run for business app
        return

    # Create/update permissions
    db_permissions = set()
    for codename, name in BusinessPermission.PERMISSION_CHOICES:
        permission, created = BusinessPermission.objects.get_or_create(
            codename=codename,
            defaults={'name': dict(BusinessPermission.PERMISSION_CHOICES)[codename]}
        )
        db_permissions.add(codename)

    # Remove obsolete permissions
    valid_codenames = set(BusinessPermissions.PERMISSIONS.values())
    BusinessPermission.objects.exclude(codename__in=valid_codenames).delete()

    # Update roles with valid permissions
    for role in BusinessRole.objects.all():
        # Remove any invalid permissions from roles
        role.permissions.remove(
            *role.permissions.exclude(codename__in=valid_codenames)
        )

@receiver(pre_save, sender=BusinessRole)
def validate_role_permissions(sender, instance, **kwargs):
    """
    Validates that all permissions assigned to a role are valid according to
    BusinessPermissions system.
    """
    if instance.pk:  # Only for existing roles
        valid_codenames = set(BusinessPermissions.PERMISSIONS.values())
        current_permissions = set(
            instance.permissions.values_list('codename', flat=True)
        )
        
        # Remove invalid permissions
        invalid_permissions = current_permissions - valid_codenames
        if invalid_permissions:
            instance.permissions.remove(
                *BusinessPermission.objects.filter(codename__in=invalid_permissions)
            )