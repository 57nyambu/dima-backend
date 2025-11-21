from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from apps.accounts.views import (
    RegisterUserView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    GoogleAuthView,
    PasswordResetCodeRequestView,
    PasswordResetCodeVerifyView,
    GoogleAuthTestView,
)

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/logout/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Google OAuth
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    path('google/test/', GoogleAuthTestView.as_view(), name='google_auth_test'),
    
    # Code-based password reset
    path('password-reset-code/', PasswordResetCodeRequestView.as_view(), name='password_reset_code'),
    path('password-reset-code-verify/', PasswordResetCodeVerifyView.as_view(), name='password_reset_code_verify'),
]