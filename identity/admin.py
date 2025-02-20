from django.contrib import admin
from .models import Following, FollowRequests

admin.site.register(Following)
admin.site.register(FollowRequests)