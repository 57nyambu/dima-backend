from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'role', 'is_active', 'is_seller', 'is_admin', 'is_verified', 'date_joined')
    list_filter = ('is_active', 'is_seller', 'is_admin', 'is_verified', 'role')
    search_fields = ('email', 'username')
    ordering = ('-date_joined',)
    filter_horizontal = ()
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_seller', 'is_admin', 
                                  'is_verified', 'is_staff', 'is_superuser', 'role')}),
        ('Important dates', {'fields': ('last_login',)}),  # Removed date_joined from here
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'role'),
        }),
    )
    
    readonly_fields = ('last_login',)  # Add readonly fields