from rest_framework import permissions

class IsAuthorOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow only authors or admins to edit/delete posts.
    自定义权限，仅允许作者或管理员编辑/删除帖子。（GJ）

    - Authors can edit or delete their own posts.
      作者可以编辑或删除自己的帖子。（GJ）
    - Admins can edit or delete any post.
      管理员可以编辑或删除任何帖子。（GJ）
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if the user is the author or an admin.
        检查用户是否是帖子作者或管理员。（GJ）
        """
        if request.user.is_superuser:  
            return True  # Admins have full access / 管理员具有完全访问权限（GJ）
        
        return obj.author == request.user  # Only authors can modify their own posts / 仅作者可以修改自己的帖子（GJ） 


class IsPostVisibleToUser(permissions.BasePermission):
    """
    Custom permission to determine if a user can view a post based on its visibility setting.
    自定义权限，根据可见性设置决定用户是否可以查看帖子。（GJ）

    - PUBLIC posts are visible to everyone.
      PUBLIC（公开）帖子对所有人可见。（GJ）
    - UNLISTED posts are visible via direct link.
      UNLISTED（未列出）帖子仅可通过直接链接访问。（GJ）
    - FRIENDS posts are visible only to friends.
      FRIENDS（仅好友可见）帖子仅对好友可见。（GJ）
    - DELETED posts are visible only to admins.
      DELETED（已删除）帖子仅管理员可见。（GJ）
    """

    def has_object_permission(self, request, view, obj):
        """
        Check visibility permissions for viewing posts.
        检查查看帖子时的可见性权限。（GJ）
        """
        if obj.visibility == "PUBLIC":
            return True  # Public posts are accessible by anyone / 公开帖子对所有人可见（GJ）

        if obj.visibility == "UNLISTED":
            return True  # Unlisted posts are accessible via link / 未列出帖子可以通过链接访问（GJ）

        if obj.visibility == "FRIENDS":
            return obj.author == request.user or request.user in obj.author.friends.all()  
            # Friends-only posts are visible only to the author and their friends
            # 仅作者和其好友可以查看好友可见帖子（GJ）

        if obj.visibility == "DELETED":
            return request.user.is_superuser  # Only admins can see deleted posts / 仅管理员可以查看已删除帖子（GJ）

        return False  # Default to no access / 默认拒绝访问（GJ）
