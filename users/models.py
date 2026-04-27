from django.db import models
from django.contrib.auth.models import User


class Business(models.Model):
    name = models.CharField(max_length=150)
    registration_number = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'businesses'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_MANAGER = 'manager'
    ROLE_CASHIER = 'cashier'

    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_CASHIER, 'Cashier'),
    ]

    ROLE_CAPABILITIES = {
        ROLE_OWNER: {
            'inventory',
            'reports',
            'users',
            'distributors',
            'sales',
        },
        ROLE_MANAGER: {
            'inventory',
            'reports',
            'users',
            'distributors',
            'sales',
        },
        ROLE_CASHIER: {
            'sales',
        },
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    phone = models.CharField(max_length=30, blank=True)
    branch_shop = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    @property
    def capabilities(self):
        return sorted(self.ROLE_CAPABILITIES.get(self.role, set()))

    def can(self, capability):
        return capability in self.ROLE_CAPABILITIES.get(self.role, set())

    def __str__(self):
        return f"{self.user.username} ({self.role})"
