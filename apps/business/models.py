from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from apps.accounts.models import CustomUser
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
from .constants import BUSINESS_PERMISSIONS


class Business(models.Model):
    CATEGORY_TYPE = [
            ('fashion', 'Fashion & Clothing'),
            ('electronics', 'Electronics'),
            ('agriculture', 'Agriculture & Farm Produce'),
            ('food', 'Food & Groceries'),
            ('health', 'Health & Pharmacy'),
            ('logistics', 'Logistics & Transport Services'),
            ('enterteinment', 'Enterteinment & Events'),
            ('manufacture', 'Manufacture & Processing'),
            ('sme', 'Small/Medium Enterprise'),
            ('second-hand', 'SecondHand Dealer'),
            ('others', 'Others')
    ]
    VERIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='businesses')
    name = models.CharField(max_length=225)
    slug = models.SlugField(unique=True)
    business_type = models.CharField(max_length=30, choices=CATEGORY_TYPE)
    description = models.CharField(max_length=225, blank=True)
    kra_pin = models.CharField(max_length=30, blank=True)
    business_reg_no = models.CharField(max_length=30, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUS, default='pending'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Businesses"
        indexes = [models.Index(fields=['owner'])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner} - {self.name} - ({self.get_business_type_display()})"


class BusinessPermission(models.Model):
    """
    Granular permissions for business operations
    """
    PERMISSION_CHOICES = [
        (value, key.replace('_', ' ').title()) 
        for key, value in BUSINESS_PERMISSIONS.items()
    ]

    codename = models.CharField(max_length=50, choices=PERMISSION_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Business Permission'
        verbose_name_plural = 'Business Permissions'
        ordering = ['codename']

    def __str__(self):
        return self.name

    @classmethod
    def get_all_codenames(cls):
        """Returns all available permission codenames"""
        return list(BUSINESS_PERMISSIONS.values())


class BusinessRole(models.Model):
    """
    Predefined roles with sets of permissions
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(BusinessPermission)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @classmethod
    def create_default_roles(cls):
        # Map of default roles and their permissions
        default_roles = {
            'Owner': [
                'product.add', 'product.edit', 'product.delete', 'product.view',
                'order.view', 'order.process', 'order.cancel', 'order.refund',
                'business.edit_profile', 'business.manage_team', 'business.manage_settings',
                'analytics.view_sales', 'analytics.view_customers',
                'financial.view_earnings', 'financial.request_payout'
            ],
            'Manager': [
                'product.add', 'product.edit', 'product.view',
                'order.view', 'order.process', 'order.cancel',
                'analytics.view_sales', 'analytics.view_customers',
                'financial.view_earnings'
            ],
            'Product Specialist': [
                'product.add', 'product.edit', 'product.view',
                'product.manage_inventory'
            ],
            'Customer Support': [
                'order.view', 'order.process', 'order.refund'
            ],
            'Analyst': [
                'analytics.view_sales', 'analytics.view_customers',
                'financial.view_earnings'
            ]
        }
        
        for role_name, permissions in default_roles.items():
            role, created = cls.objects.get_or_create(
                name=role_name,
                defaults={'is_default': True}
            )
            if created:
                perms = BusinessPermission.objects.filter(
                    codename__in=permissions
                )
                role.permissions.set(perms)

class BusinessTeamMember(models.Model):
    """
    Associates users with businesses and assigns roles
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='team_members')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='business_memberships')
    roles = models.ManyToManyField(BusinessRole)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('business', 'user')
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.email} at {self.business.name}"
    
    def has_permission(self, permission_codename):
        """
        Check if this team member has a specific permission
        """
        if self.business.owner == self.user:
            return True
            
        return self.roles.filter(
            permissions__codename=permission_codename
        ).exists()
    
    def get_permissions(self):
        """
        Returns all permissions this team member has
        """
        if self.business.owner == self.user:
            return BusinessPermission.get_all_codenames()
            
        return list(self.roles.values_list(
            'permissions__codename',
            flat=True
        ).distinct())
    

class BusinessTeamInvitation(models.Model):
    """
    Tracks invitations to join business teams
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    roles = models.ManyToManyField(BusinessRole)
    invited_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_invitations')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation to {self.email} for {self.business.name}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def clean(self):
        if self.status == 'pending' and self.is_expired:
            self.status = 'expired'
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('mpesa_till', 'M-Pesa Till'),
        ('mpesa_paybill', 'M-Pesa Paybill'),
        ('mpesa_send_money', 'M-Pesa Send Money'),
        ('airtel_send_money', 'Airtel Send Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Credit/Debit Card')
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payment_methods')
    type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    till_number = models.CharField(max_length=20, blank=True, null=True)
    business_number = models.CharField(max_length=25, blank=True, null=True)
    paybill_account_number = models.CharField(max_length=25, blank=True, null=True)
    bank_account_number = models.CharField(max_length=25, blank=True, null=True)
    bank_name = models.CharField(max_length=70, blank=True, null=True)
    card_number = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'

    def clean(self):
        if self.type == 'mpesa_till' and not self.till_number:
            raise ValidationError("Till number is required for M-Pesa Till.")
        elif self.type == 'mpesa_paybill':
            if not self.business_number or not self.paybill_account_number:
                raise ValidationError("Paybill and account number are required for mpesa Paybill.")
        elif self.type == 'bank_transfer':
            if not self.bank_name or not self.bank_account_number:
                raise ValidationError('Bank name and account number are required for bank transfers.')
        elif self.type == 'card' and not self.card_number:
            raise ValidationError("Card number is required for card payment.")
        
    def __str__(self):
        return f"{self.business.name}: {self.type} - {self.till_number}"


class BusinessReview(models.Model):
    product = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='business_reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    orders_complete = models.IntegerField(default=0)
    orders_pending = models.IntegerField(default=0)
    canceled_orders = models.IntegerField(default=0)
    comment = models.TextField(blank=True)
    mpesa_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Business Review'
        verbose_name_plural = 'Business Reviews'
        unique_together = ['product', 'user']

    def clean(self):
        if self.product.owner == self.user:
            raise ValidationError("You cannot review your own business.")

    def __str__(self):
        return f"{self.user.username}"