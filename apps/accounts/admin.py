from django.contrib import admin

from apps.accounts.models import Role, User, UserRole

admin.site.register(User)
admin.site.register(Role)
admin.site.register(UserRole)
