from django.contrib.auth.models import AbstractBaseUser, PermissionManager
from django.db import models
from .managers import CustomUserManager
from django.db.models import PROTECT
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
import random
import string

class Role(models.Model):
    name = models.CharField(max_length=255, default='customer')
    description = models.TextField(default='Can only buy goods')

    def __str__(self):
        return f"{self.name} - {self.description}"


class CustomUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=225, unique=False,  null=True, blank=True)
    first_name = models.CharField(max_length=225, null=True, blank=True)
    last_name = models.CharField(max_length=225, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    role = models.ForeignKey(Role, on_delete=PROTECT, default=1, related_name='users')
    is_seller = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Google OAuth fields
    google_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    auth_provider = models.CharField(max_length=50, default='email')  # 'email' or 'google'
    
    # Password reset code fields
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_created_at = models.DateTimeField(null=True, blank=True)
    reset_code_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [
            ("delete_customer", "Can delete users"),
        ]

    USERNAME_FIELD = 'email' 

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Returns True if the user has the specified permission"
        return self.is_superuser
    
    def has_business_permission(self, business_id, codename):
        return self.business_memberships.filter(
            business_id=business_id,
            is_active=True,
            roles__permissions__codename=codename
        ).exists()

    @property
    def is_business_owner(self):
        return self.businesses.exists()

    @property
    def is_business_member(self):
        return self.business_memberships.filter(is_active=True).exists()

    def has_module_perms(self, app_label):
        "Returns True if the user has permissions to view the app `app_label`"
        return self.is_superuser

    def tokens(self):
        pass
    
    def generate_reset_code(self, expiry_minutes=10):
        """Generate a 6-digit reset code that expires in specified minutes"""
        self.reset_code = ''.join(random.choices(string.digits, k=6))
        self.reset_code_created_at = timezone.now()
        self.reset_code_expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        self.save(update_fields=['reset_code', 'reset_code_created_at', 'reset_code_expires_at'])
        return self.reset_code
    
    def verify_reset_code(self, code):
        """Verify if the reset code is valid and not expired"""
        if not self.reset_code or not self.reset_code_expires_at:
            return False
        
        if self.reset_code != code:
            return False
        
        if timezone.now() > self.reset_code_expires_at:
            return False
        
        return True
    
    def clear_reset_code(self):
        """Clear reset code after successful password reset"""
        self.reset_code = None
        self.reset_code_created_at = None
        self.reset_code_expires_at = None
        self.save(update_fields=['reset_code', 'reset_code_created_at', 'reset_code_expires_at'])

