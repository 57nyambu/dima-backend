# marketplace/permissions.py
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.user == request.user


class IsDisputeParty(permissions.BasePermission):
    """
    Permission for dispute access - only buyer or seller can view
    """
    
    def has_object_permission(self, request, view, obj):
        return (
            obj.buyer == request.user or 
            obj.seller.owner == request.user or
            request.user.is_staff
        )