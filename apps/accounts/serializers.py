from rest_framework import serializers
from .models import CustomUser, Role
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode 
from django.utils.encoding import force_bytes
from django.contrib.auth import authenticate


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(min_length=6, write_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'password']


    def create(self, validated_data):
        # Automatically hash passwords
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(read_only=True)  # Add the role field

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)

            if user:
                data['user'] = user
                data['role'] = user.role.name if user.role else None  # Include the role name
            else:
                raise serializers.ValidationError("Invalid credentials")
        else:
            raise serializers.ValidationError("Must include 'email' and 'password'")

        return data


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address.")
        return value

    def save(self):
        user = self.user
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return {
            'token': token,
            'uid': uid,
            'email': user.email,
        }


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, write_only=True)
    token = serializers.CharField()
    uid = serializers.CharField()

    def validate(self, data):
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            self.user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, CustomUser.DoesNotExist):
            raise serializers.ValidationError("Invalid reset link")

        if not default_token_generator.check_token(self.user, data['token']):
            raise serializers.ValidationError("Invalid or expired token")

        return data

    def save(self):
        self.user.set_password(self.validated_data['password'])
        self.user.save()
        return {'message': 'Password reset successful'} 
    

class UpdateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'email',  
            'password',
            'is_seller'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'is_seller': {'write_only': True}
        }

    def update(self, instance, validated_data):
        # Update user fields
        for attr, value in validated_data.items():
            if attr == 'password':  # Handle password separately
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance


class AdminUserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'date_joined', 'last_login', 'is_active', 'is_seller']


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'role', 'date_joined', 'last_login', 'is_active', 'is_seller']
        read_only_fields = fields


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer for Google OAuth authentication"""
    id_token = serializers.CharField(required=True, help_text="Google ID token from frontend")
    
    def validate(self, data):
        from google.oauth2 import id_token
        from google.auth.transport import requests
        from django.conf import settings
        
        token = data.get('id_token')
        
        try:
            # Verify the token with Google
            # You need to set GOOGLE_CLIENT_ID in your settings
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                getattr(settings, 'GOOGLE_CLIENT_ID', None)
            )
            
            # Verify the token is for your app
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise serializers.ValidationError('Invalid token issuer')
            
            # Extract user info from token
            email = idinfo.get('email')
            google_id = idinfo.get('sub')
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            
            if not email:
                raise serializers.ValidationError('Email not provided by Google')
            
            # Check if user exists
            try:
                user = CustomUser.objects.get(email=email)
                is_new_user = False
                
                # Update Google ID if not set
                if not user.google_id:
                    user.google_id = google_id
                    user.auth_provider = 'google'
                    user.save(update_fields=['google_id', 'auth_provider'])
                    
            except CustomUser.DoesNotExist:
                # Create new user
                user = CustomUser.objects.create(
                    email=email,
                    google_id=google_id,
                    first_name=first_name,
                    last_name=last_name,
                    username=email.split('@')[0],
                    auth_provider='google',
                    is_verified=True,  # Google emails are verified
                    is_active=True
                )
                # Set unusable password for OAuth users
                user.set_unusable_password()
                user.save()
                is_new_user = True
            
            data['user'] = user
            data['role'] = user.role.name if user.role else 'customer'
            data['is_new_user'] = is_new_user
            
        except ValueError as e:
            # Invalid token
            raise serializers.ValidationError(f'Invalid Google token: {str(e)}')
        except Exception as e:
            raise serializers.ValidationError(f'Authentication failed: {str(e)}')
        
        return data


class PasswordResetCodeRequestSerializer(serializers.Serializer):
    """Request password reset code via email or SMS"""
    email = serializers.EmailField(required=True)
    method = serializers.ChoiceField(choices=['email', 'sms'], default='email')
    
    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
            self.user = user
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")
        return value
    
    def validate(self, data):
        data['user'] = self.user
        return data


class PasswordResetCodeVerifySerializer(serializers.Serializer):
    """Verify reset code and set new password"""
    email = serializers.EmailField(required=True)
    reset_code = serializers.CharField(required=True, max_length=6, min_length=6)
    new_password = serializers.CharField(required=True, min_length=6, write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        reset_code = data.get('reset_code')
        new_password = data.get('new_password')
        
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found")
        
        # Verify the reset code
        if not user.verify_reset_code(reset_code):
            raise serializers.ValidationError("Invalid or expired reset code")
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        data['user'] = user
        return data


class CustomerProfileSerializer(serializers.ModelSerializer):
    """Serializer for customer profile information used in checkout"""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        read_only_fields = ['email']
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            # Remove any spaces or special characters
            phone = value.replace(' ', '').replace('-', '').replace('+', '')
            
            # Check if it's a valid Kenyan number (254XXXXXXXXX or 07XXXXXXXX or 01XXXXXXXX)
            if phone.startswith('254'):
                if len(phone) != 12:
                    raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX")
            elif phone.startswith('0'):
                if len(phone) != 10:
                    raise serializers.ValidationError("Invalid phone number format. Use 07XXXXXXXX or 01XXXXXXXX")
            else:
                raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX or 07XXXXXXXX")
            
        return value


class FullUserProfileSerializer(serializers.ModelSerializer):
    """Comprehensive user profile serializer with all user data"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    is_business_owner = serializers.BooleanField(read_only=True)
    is_business_member = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'phone_number',
            'date_joined',
            'last_login',
            'is_active',
            'is_seller',
            'is_verified',
            'role_name',
            'auth_provider',
            'is_business_owner',
            'is_business_member'
        ]
        read_only_fields = [
            'id',
            'email',
            'date_joined',
            'last_login',
            'is_verified',
            'role_name',
            'auth_provider',
            'is_business_owner',
            'is_business_member'
        ]
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            phone = value.replace(' ', '').replace('-', '').replace('+', '')
            if phone.startswith('254'):
                if len(phone) != 12:
                    raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX")
            elif phone.startswith('0'):
                if len(phone) != 10:
                    raise serializers.ValidationError("Invalid phone number format. Use 07XXXXXXXX or 01XXXXXXXX")
            else:
                raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX or 07XXXXXXXX")
        return value
