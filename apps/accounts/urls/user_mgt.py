from django.urls import path
from apps.accounts.views import (
    UpdateUserView,
    TestProtectedView,
    AdminUserViewSet,
    WelcomeView,
    UserDetailView,
    RoleApiView,
    CustomerProfileView,
    FullUserProfileView,
)


urlpatterns = [
    path('', WelcomeView.as_view(), name='welcome'),
    path('profile/', UpdateUserView.as_view(), name='update-profile'),
    path('customer-profile/', CustomerProfileView.as_view(), name='customer-profile'),
    path('full-profile/', FullUserProfileView.as_view(), name='full-profile'),
    path('protected/', TestProtectedView.as_view(), name='protected'),
    path('user-details/', AdminUserViewSet.as_view({'get': 'list'}), name='user-details'),
    path('user-info/', UserDetailView.as_view(), name='username'),
    path('role/', RoleApiView.as_view(), name='role')
]
