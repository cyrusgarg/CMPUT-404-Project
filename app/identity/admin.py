from django.contrib import admin
from .models import Following, FollowRequests, Friendship, RemoteNode, RemoteAuthor


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

@admin.register(RemoteAuthor)
class RemoteAuthorAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'node', 'host', 'last_updated']
    list_filter = ['node', 'last_updated']
    search_fields = ['display_name', 'author_id', 'github']