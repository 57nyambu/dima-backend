from rest_framework import permissions


class IsSellerPermission(permissions.BasePermission):
    """
    Permission check for seller users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_seller


class IsAdminPermission(permissions.BasePermission):
    """
    Permission check for admin users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsBuyerPermission(permissions.BasePermission):
    """
    Permission check for buyer/customer users.
    Any authenticated user can access buyer dashboard (everyone can buy).
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
