from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from .models import Business, UserProfile


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'registration_number', 'phone', 'location', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(read_only=True)
    capabilities = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = UserProfile
        fields = ['role', 'phone', 'business', 'capabilities']


class CurrentUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'profile']


class RegisterSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=150)
    business_phone = serializers.CharField(max_length=30, allow_blank=True, required=False)
    business_location = serializers.CharField(max_length=150, allow_blank=True, required=False)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('That username is already in use.')
        return value

    @transaction.atomic
    def create(self, validated_data):
        business = Business.objects.create(
            name=validated_data['business_name'],
            phone=validated_data.get('business_phone', ''),
            location=validated_data.get('business_location', ''),
        )
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        UserProfile.objects.create(
            user=user,
            business=business,
            role=UserProfile.ROLE_OWNER,
            phone=validated_data.get('phone', ''),
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs['username'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account is disabled.')
        if not hasattr(user, 'profile'):
            raise serializers.ValidationError('This user is not attached to a business.')
        attrs['user'] = user
        return attrs


class ManagedUserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, write_only=True)
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False, write_only=True)
    password = serializers.CharField(min_length=8, write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'role',
            'phone',
            'password',
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, 'profile', None)
        data['role'] = profile.role if profile else ''
        data['phone'] = profile.phone if profile else ''
        return data

    def validate_username(self, value):
        queryset = User.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('That username is already in use.')
        return value

    def validate_role(self, value):
        request = self.context.get('request')
        current_role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if value == UserProfile.ROLE_OWNER and current_role != UserProfile.ROLE_OWNER:
            raise serializers.ValidationError('Only owners can create or assign owners.')
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Password is required for new users.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data.pop('role')
        phone = validated_data.pop('phone', '')
        password = validated_data.pop('password')
        business = self.context['business']
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, business=business, role=role, phone=phone)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        phone = validated_data.pop('phone', None)
        password = validated_data.pop('password', None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if password:
            instance.set_password(password)
        instance.save()

        profile = instance.profile
        if role is not None:
            profile.role = role
        if phone is not None:
            profile.phone = phone
        profile.save()
        return instance
