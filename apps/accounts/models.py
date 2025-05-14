from django.contrib.auth.models import AbstractBaseUser, PermissionManager
from django.db import models
from .managers import CustomUserManager
from django.db.models import PROTECT
from django.utils.text import slugify

class Role(models.Model):
    name = models.CharField(max_length=255, default='customer')
    description = models.TextField(default='Can only buy goods')

    def __str__(self):
        return f"{self.name} - {self.description}"


class CustomUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=225, unique=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    role = models.ForeignKey('Role', on_delete=PROTECT, null=True)
    is_seller = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

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

    def has_module_perms(self, app_label):
        "Returns True if the user has permissions to view the app `app_label`"
        return self.is_superuser

    def tokens(self):
        pass
