from django.contrib.auth.models import BaseUserManager
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.apps import apps  # Import apps to dynamically get the model

class CustomUserManager(BaseUserManager):
    def email_validator(self, email):
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError(_("please enter a valid email"))

    def create_user(self, email, password, **extra_fields):
        if email:
            email = self.normalize_email(email)
            self.email_validator(email)
        
        else:
            raise ValueError("The Email field must be set")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # Hashes the password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_seller", True)
        extra_fields.setdefault("is_admin", True)
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("is staff must be true for admin user"))
        
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("is superuser must be true for admin user"))

        # Dynamically get the Role model to avoid circular import
        Role = apps.get_model('accounts', 'Role')
        
        # Check if the superuser role exists, create it if it does not
        superuser_role, created = Role.objects.get_or_create(
            name='superuser',
            defaults={'description': 'Has all permissions'}
        )
        
        extra_fields['role'] = superuser_role

        user = self.create_user(email, password, **extra_fields)
        user.save(using=self._db)
        return user