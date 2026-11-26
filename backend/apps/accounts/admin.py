from django.contrib import admin

from .models import CustomerProfile, SocialAccount, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "phone", "passport_number")
    search_fields = ("user__email", "passport_number")


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("provider", "provider_uid", "user", "linked_at")
    list_filter = ("provider",)
    search_fields = ("provider_uid", "user__email")
