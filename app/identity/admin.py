from django.contrib import admin
from .models import Following, FollowRequests, Friendship

admin.site.register(Following)
admin.site.register(FollowRequests)
admin.site.register(Friendship)