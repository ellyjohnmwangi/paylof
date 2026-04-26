from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .permissions import CanManageUsers, HasBusinessProfile
from .serializers import (
    CurrentUserSerializer,
    LoginSerializer,
    ManagedUserSerializer,
    RegisterSerializer,
)


def auth_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {
        'token': token.key,
        'user': CurrentUserSerializer(user).data,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(auth_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(auth_payload(serializer.validated_data['user']))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated, HasBusinessProfile]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class ManagedUserViewSet(viewsets.ModelViewSet):
    serializer_class = ManagedUserSerializer
    permission_classes = [IsAuthenticated, HasBusinessProfile, CanManageUsers]

    def get_queryset(self):
        business = self.request.user.profile.business
        return User.objects.select_related('profile').filter(profile__business=business).order_by('username')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['business'] = self.request.user.profile.business
        return context

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError({'detail': 'You cannot remove your own account.'})

        profile = instance.profile
        current_role = self.request.user.profile.role
        if profile.role == UserProfile.ROLE_OWNER and current_role != UserProfile.ROLE_OWNER:
            raise PermissionDenied('Only owners can remove another owner.')

        owner_count = self.get_queryset().filter(profile__role=UserProfile.ROLE_OWNER, is_active=True).count()
        if profile.role == UserProfile.ROLE_OWNER and owner_count <= 1:
            raise ValidationError({'detail': 'A business must keep at least one active owner.'})

        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=True, methods=['post'])
    def send_password_reset(self, request, pk=None):
        user = self.get_object()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"/reset-password/{uid}/{token}/"

        return Response({
            'detail': f'Password reset link generated for {user.username}.',
            'reset_link': reset_link,
        })
