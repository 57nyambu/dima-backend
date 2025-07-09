from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from .models import Business, BusinessTeamMember
from .constants import BUSINESS_PERMISSIONS, PERMISSION_GROUPS

User = get_user_model()

class BusinessPermissions:
    """
    Centralized permission system for business operations
    """
    
    PERMISSIONS = BUSINESS_PERMISSIONS
    PERMISSION_GROUPS = PERMISSION_GROUPS
    
    @classmethod
    def get_permission_codenames(cls):
        """Returns all available permission codenames"""
        return list(cls.PERMISSIONS.values())
    
    @classmethod
    def get_permission_group(cls, group_name):
        """Returns permissions in a specific group"""
        return [cls.PERMISSIONS[perm] for perm in cls.PERMISSION_GROUPS.get(group_name, [])]
    
    @classmethod
    def user_has_permission(cls, user, business, permission_codename):
        """
        Check if user has specific permission for a business
        """
        # Business owners have all permissions
        if business.owner == user:
            return True
            
        # Check team membership and roles
        try:
            team_member = BusinessTeamMember.objects.get(
                user=user,
                business=business,
                is_active=True
            )
            return team_member.roles.filter(
                permissions__codename=permission_codename
            ).exists()
        except BusinessTeamMember.DoesNotExist:
            return False
    
    @classmethod
    def get_user_permissions(cls, user, business):
        """
        Returns all permissions a user has for a specific business
        """
        if business.owner == user:
            return cls.get_permission_codenames()
            
        try:
            team_member = BusinessTeamMember.objects.get(
                user=user,
                business=business,
                is_active=True
            )
            return list(team_member.roles.values_list(
                'permissions__codename',
                flat=True
            ).distinct())
        except BusinessTeamMember.DoesNotExist:
            return []
    
    @classmethod
    def get_users_with_permission(cls, business, permission_codename):
        """
        Returns all users who have a specific permission for a business
        """
        # Include the owner
        users = User.objects.filter(pk=business.owner.pk)
        
        # Add team members with the permission
        team_members = BusinessTeamMember.objects.filter(
            business=business,
            is_active=True,
            roles__permissions__codename=permission_codename
        ).exclude(user=business.owner)
        
        return users.union(
            User.objects.filter(
                pk__in=team_members.values_list('user', flat=True)
            )
        )


# Permission decorators and mixins
def business_permission_required(permission_codename):
    """
    Decorator to check if user has specific business permission
    """
    def decorator(view_func):
        from functools import wraps
        
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            business_id = kwargs.get('business_id')
            if not business_id:
                raise PermissionDenied("Business ID not provided")
                
            try:
                business = Business.objects.get(pk=business_id)
            except Business.DoesNotExist:
                raise PermissionDenied("Business not found")
                
            if not BusinessPermissions.user_has_permission(
                request.user, business, permission_codename
            ):
                raise PermissionDenied
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


class BusinessPermissionMixin:
    """
    Class-based view mixin for permission checking
    """
    permission_codename = None
    business_lookup_field = 'pk'
    business_lookup_url_kwarg = 'business_id'
    
    def dispatch(self, request, *args, **kwargs):
        if not self.permission_codename:
            raise ValueError(
                "BusinessPermissionMixin requires permission_codename to be set"
            )
            
        business_id = kwargs.get(self.business_lookup_url_kwarg)
        if not business_id:
            raise PermissionDenied("Business ID not provided")
            
        try:
            business = Business.objects.get(pk=business_id)
        except Business.DoesNotExist:
            raise PermissionDenied("Business not found")
            
        if not BusinessPermissions.user_has_permission(
            request.user, business, self.permission_codename
        ):
            raise PermissionDenied
            
        return super().dispatch(request, *args, **kwargs)