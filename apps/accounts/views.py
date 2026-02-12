from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    RoleSerializer,
    CustomUserSerializer, 
    LoginSerializer, 
    PasswordResetSerializer, 
    AdminUserDetailSerializer,
    PasswordResetConfirmSerializer,
    UserDetailSerializer,
    GoogleAuthSerializer,
    PasswordResetCodeRequestSerializer,
    PasswordResetCodeVerifySerializer)
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import InvalidToken
from apps.utils.emailService import welcomeEmail
from django.views.generic.base import TemplateView
import logging
from .models import CustomUser, Role
from apps.utils.emailService import forgotPassEmail, send_reset_code_email, send_reset_code_sms

logger = logging.getLogger(__name__)


class WelcomeView(TemplateView):
    template_name = "default.html"


class GoogleAuthTestView(TemplateView):
    """Test page for Google OAuth authentication"""
    template_name = "accounts/google_auth_test.html"
    
    def get_context_data(self, **kwargs):
        from django.conf import settings
        context = super().get_context_data(**kwargs)
        context['GOOGLE_CLIENT_ID'] = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        return context


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff or request.user.is_admin
    

class RoleApiView(APIView):
    permission_classes = [IsAdminUser]
    serializer_class = RoleSerializer
    
    def post(self, request):
        role = request.data
        serializer = RoleSerializer(data=role)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Role created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        roles = Role.objects.all()
        serializer = RoleSerializer(roles, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        role = Role.objects.get(id=pk)
        serializer = RoleSerializer(instance=role, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Role updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    

class RegisterUserView(APIView): 
    def post(self, request): 
        user_data = request.data 
        
        serializer = CustomUserSerializer(data=user_data) 
        if serializer.is_valid(): 
            user = serializer.save()
            
            # Send welcome email using new EmailService
            try:
                from apps.notifications.emails import EmailService
                email_service = EmailService()
                email_service.send_signup_welcome(user)
                logger.info(f"✓ Welcome email sent to {user.email}")
            except Exception as e:
                logger.error(f"✗ Failed to send welcome email: {e}")
            
            # Send welcome SMS if phone number is provided
            if user.phone_number:
                try:
                    from apps.notifications.sms import SMSService
                    sms_service = SMSService()
                    sms_service.send_signup_welcome(user)
                    logger.info(f"✓ Welcome SMS sent to {user.phone_number}")
                except Exception as e:
                    logger.error(f"✗ Failed to send welcome SMS: {e}")
            
            response = Response({ 
                'success': True,
                'message': "User created!", 
                'data': serializer.data
                }, status=status.HTTP_201_CREATED) 
            response['Content-Type'] = 'application/json' 
            return response 
        response = Response({'success': False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST) 
        response['Content-Type'] = 'application/json' 
        return response

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer  # Reference the class properly

    def post(self, request):
        user_data = request.data
        # Use self.serializer_class to correctly refer to the serializer class
        serializer = self.serializer_class(data=user_data, context={'request': request})

        if serializer.is_valid():
            user = serializer.validated_data['user']
            role = serializer.validated_data['role']
            # Generate tokens using the authenticated user
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Login successful',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'role': role,  # Include the role in the response
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class=None

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token", None)

            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({
                "message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except InvalidToken as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        try:
            if serializer.is_valid():
                data = serializer.save()
                forgotPassEmail(data)
                return Response({
                    'success': True,
                    'data': {
                        'token': data['token'],
                        'uid': data['uid'],
                        'email': data['email'],
                    }
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        try:
            if serializer.is_valid():
                data = serializer.save()
                return Response({
                    'success': True,
                    'data': data
                }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class GoogleAuthView(APIView):
    """Handle Google OAuth authentication"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            role = serializer.validated_data['role']
            is_new_user = serializer.validated_data['is_new_user']
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'success': True,
                'message': 'Google authentication successful',
                'is_new_user': is_new_user,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'role': role,
                'user': {
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username,
                }
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetCodeRequestView(APIView):
    """Request password reset code via email or SMS"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = PasswordResetCodeRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            method = serializer.validated_data['method']
            reset_code = user.generate_reset_code(expiry_minutes=10)
            
            try:
                if method == 'email':
                    # Send reset code via email using new EmailService
                    from apps.notifications.emails import EmailService
                    email_service = EmailService()
                    result = email_service.send_password_reset(user, reset_code)
                    
                    if not result.get('success'):
                        return Response({
                            'success': False,
                            'error': 'Failed to send reset email'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                    logger.info(f"✓ Password reset email sent to {user.email}")
                    
                elif method == 'sms':
                    # Send reset code via SMS
                    if not user.phone_number:
                        return Response({
                            'success': False,
                            'error': 'Phone number not found for this user'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Use new SMSService with logging
                    from apps.notifications.sms import SMSService
                    sms_service = SMSService()
                    result = sms_service.send_password_reset_code(user, reset_code)
                    
                    if not result.get('success'):
                        return Response({
                            'success': False,
                            'error': 'Failed to send reset SMS'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                    logger.info(f"✓ Password reset SMS sent to {user.phone_number}")
                
                return Response({
                    'success': True,
                    'message': f'Reset code sent via {method}',
                    'method': method,
                    'destination': user.email if method == 'email' else user.phone_number
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Failed to send reset code: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Failed to send reset code via {method}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetCodeVerifyView(APIView):
    """Verify reset code and set new password"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = PasswordResetCodeVerifySerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.clear_reset_code()
            
            # Send confirmation notifications
            try:
                # Send confirmation email
                from apps.notifications.emails import EmailService
                email_service = EmailService()
                email_result = email_service.send_password_reset_success(user)
                
                if email_result.get('success'):
                    logger.info(f"✓ Password reset confirmation email sent to {user.email}")
                else:
                    logger.warning(f"Failed to send confirmation email: {email_result.get('error')}")
                
                # Send confirmation SMS if user has phone number
                if user.phone_number:
                    from apps.notifications.sms import SMSService
                    sms_service = SMSService()
                    sms_result = sms_service.send_password_reset_success(user)
                    
                    if sms_result.get('success'):
                        logger.info(f"✓ Password reset confirmation SMS sent to {user.phone_number}")
                    else:
                        logger.warning(f"Failed to send confirmation SMS: {sms_result.get('error')}")
                        
            except Exception as e:
                # Don't fail the password reset if notifications fail
                logger.error(f"Error sending password reset confirmations: {str(e)}")
            
            return Response({
                'success': True,
                'message': 'Password reset successful'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    

class UpdateUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # Ensure that only authenticated users can access this view
    serializer_class = CustomUserSerializer

    def get(self, request):
        user = request.user  # Get the currently authenticated user
        serializer = CustomUserSerializer(user)
        # Exclude the 'id' from the response
        data = serializer.data
        data.pop('id', None)
        return Response({
            "success": True,
            "message": "User data retrieved successfully.",
            "data": data
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        """
        Update current user data.
        """
        user = request.user  # Get the currently authenticated user
        serializer = CustomUserSerializer(user, data=request.data, partial=True)  # Allow partial updates

        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "User data updated successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": "Failed to update user data.",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TestProtectedView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomUserSerializer  # For schema generation

    def get(self, request):
        return Response({'message': "Protected endpoint accessible to authenticated users."})


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserDetailSerializer
    #permission_classes = [IsAdminUser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'role']
    ordering_fields = ['email']


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserDetailSerializer
    def get(self, request):
        try:
            serializer = self.serializer_class(request.user)
            return Response({'success': True, 'data': serializer.data
                    }, status=status.HTTP_200_OK)
        except: return Response({'success': False, 'error': 'User not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerProfileView(APIView):
    """Get and update customer profile information for checkout pre-fill"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get customer profile data"""
        from .serializers import CustomerProfileSerializer
        self.serializer_class = CustomerProfileSerializer
        
        user = request.user
        serializer = CustomerProfileSerializer(user)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Update customer profile data"""
        from .serializers import CustomerProfileSerializer
        
        user = request.user
        serializer = CustomerProfileSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class FullUserProfileView(APIView):
    """Get and update comprehensive user profile data"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get complete user profile data"""
        from .serializers import FullUserProfileSerializer
        self.serializer_class = FullUserProfileSerializer
        
        user = request.user
        serializer = FullUserProfileSerializer(user)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Update user profile data (partial update)"""
        from .serializers import FullUserProfileSerializer
        
        user = request.user
        serializer = FullUserProfileSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request):
        """Create/update profile data (handles missing fields)"""
        from .serializers import FullUserProfileSerializer
        
        user = request.user
        serializer = FullUserProfileSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Profile saved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)