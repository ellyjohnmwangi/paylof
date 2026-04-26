from django.urls import path, include
from rest_framework.routers import DefaultRouter
from products.views import DistributorViewSet, ProductViewSet
from sales.views import SaleViewSet
from users.views import LoginView, LogoutView, ManagedUserViewSet, MeView, RegisterView

router = DefaultRouter()
router.register(r'distributors', DistributorViewSet, basename='distributor')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'users', ManagedUserViewSet, basename='user')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('', include('payments.urls')),
    path('', include(router.urls)),
]
