from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserProfile, PagePermission, ActionPermission

# Inline for the UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('full_name', 'profile_image', 'profile_image_preview')
    readonly_fields = ('profile_image_preview',)

    def profile_image_preview(self, instance):
        if instance.profile_image:
            return format_html(
                '<img src="{}" width="80" height="80" style="border-radius:50%; object-fit:cover;" />',
                instance.profile_image.url
            )
        return "-"
    profile_image_preview.short_description = 'Profile Image Preview'

# Custom User Admin
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('email', 'name', 'role', 'is_active', 'profile_image_tag')
    list_filter = ('is_active', 'role', 'is_staff', 'is_superuser')
    ordering = ('email',)
    search_fields = ('email', 'name')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

    def profile_image_tag(self, obj):
        if hasattr(obj, 'profile') and obj.profile.profile_image:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%; object-fit:cover;" />',
                obj.profile.profile_image.url
            )
        return "-"
    profile_image_tag.short_description = 'Profile Image'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)


@admin.register(PagePermission)
class PagePermissionAdmin(admin.ModelAdmin):
    list_display = ("page_name", "min_role")
    list_filter = ("min_role",)
    search_fields = ("page_name",)


@admin.register(ActionPermission)
class ActionPermissionAdmin(admin.ModelAdmin):
    list_display = ("action_name", "min_role")
    list_filter = ("min_role",)
    search_fields = ("action_name",)



# Register models
admin.site.register(User, CustomUserAdmin)
