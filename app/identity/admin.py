from django.contrib import admin
from .models import Following, FollowRequests, Friendship, RemoteNode

admin.site.register(Following)
admin.site.register(FollowRequests)
admin.site.register(Friendship)


@admin.register(RemoteNode)
class RemoteNodeAdmin(admin.ModelAdmin):
    list_display = ['name', 'host_url', 'is_active', 'added_at']
    list_filter = ['is_active']
    search_fields = ['name', 'host_url']
    actions = ['activate_nodes', 'deactivate_nodes']
    
    def activate_nodes(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} nodes have been activated.")
    activate_nodes.short_description = "Activate selected nodes"
    
    def deactivate_nodes(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} nodes have been deactivated.")
    deactivate_nodes.short_description = "Deactivate selected nodes"