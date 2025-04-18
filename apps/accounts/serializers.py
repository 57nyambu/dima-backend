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
