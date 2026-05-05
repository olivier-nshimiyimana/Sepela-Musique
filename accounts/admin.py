from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile, User


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'username', 'first_name', 'last_name', 'user_type', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Artist promo (leaderboard)', {'fields': ('artist_promo_image', 'artist_promo_video')}),
    )


admin.site.register(Profile)
