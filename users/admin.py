from django.contrib import admin
from .models import Business, UserProfile


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'location', 'created_at')
    search_fields = ('name', 'phone', 'location')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business', 'role', 'phone', 'updated_at')
    list_filter = ('role', 'business')
    search_fields = ('user__username', 'user__email', 'business__name', 'phone')
