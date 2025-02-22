from datetime import datetime
from django.db import models
from django.contrib.auth.models import User  # Use Django built-in User model / 使用Django内置用户模型（GJ）
import markdown
import uuid
from django.core.exceptions import ValidationError
from identity.models import Author

# for security issues sinec Django allows all file types by default.
def validate_image_file_extension(value):
    if not value.name.endswith((".jpg", ".jpeg", ".png")):
        raise ValidationError("Only JPG and PNG images are allowed.")


class Post(models.Model):
    """ 
    Post model storing post details such as content, visibility, and ownership.
    帖子模型，存储帖子内容、可见性和作者信息。（GJ）
    """

    CONTENT_TYPE_CHOICES = [
        ('text/plain', 'Plain Text'),  # Plain text format / 纯文本格式（GJ）
        ('text/markdown', 'Markdown'),  # Markdown format / Markdown格式（GJ）
    ]

    VISIBILITY_CHOICES = [
        ("PUBLIC", "Public"),  # Public post visible to everyone / 公开帖子，所有人可见（GJ）
        ("FRIENDS", "Friends Only"),  # Only visible to friends / 仅好友可见的帖子（GJ）
        ("UNLISTED", "Unlisted"),  # Unlisted post, visible only with a link / 未列出帖子，仅有链接的人可见（GJ）
        ("DELETED", "Deleted")  # Deleted post, only visible to admins / 已删除的帖子，仅管理员可见（GJ）
    ]

    #id = models.UUIDField(primary_key=True, editable=False)  # Unique identifier for the post / 帖子唯一标识符（GJ）
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  
    #author = models.ForeignKey(User, on_delete=models.CASCADE)  # Link post to Django user model / 关联到Django用户模型（GJ）
    author = models.ForeignKey(User, on_delete=models.CASCADE)  
    title = models.CharField(max_length=255, default="")  # Post title / 帖子标题（GJ）
    description = models.TextField(default="")  # Short description of the post / 帖子简要描述（GJ）
    content = models.TextField(blank=True, null=True)  # Post content / 帖子内容（GJ）
    contentType = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text/plain')  # Content type (plain or markdown) / 帖子内容类型（纯文本或Markdown）（GJ）
    published = models.DateTimeField("published", default=datetime.now)  # Timestamp of post creation / 帖子发布时间戳（GJ）
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='UNLISTED')  # Post visibility settings / 帖子可见性设置（GJ）
    image = models.TextField(blank=True, null=True)  # To store the base64 string (optional)


    def get_formatted_content(self):
        """ 
        Convert Markdown content to HTML if applicable.
        如果帖子内容是Markdown格式，则转换为HTML。（GJ）
        """
        if self.contentType == 'text/markdown':
            return markdown.markdown(self.content, extensions=['extra']) 
        return self.content

    @staticmethod
    def get_visible_posts(user):
        """
        Retrieve posts visible to the specified user.
        获取指定用户可见的帖子。（GJ）

        - Admin can see all posts including deleted ones.
          管理员可以看到所有帖子，包括已删除的帖子。（GJ）
        - Regular users can see:
          普通用户可以看到：
          - PUBLIC (Visible to everyone) / PUBLIC（公开，对所有人可见）
          - UNLISTED (Visible only via direct link) / UNLISTED（未列出，仅有链接的人可见）
          - FRIENDS (Visible only to friends) / FRIENDS（仅好友可见）
        - Deleted posts are excluded for regular users.
          普通用户无法看到已删除的帖子。（GJ）
        """
        if user.is_superuser:
            return Post.objects.all()  # Admin can view all posts / 管理员可以看到所有帖子（GJ）

        return Post.objects.filter(
            models.Q(visibility="PUBLIC") |  # Public posts visible to all / 公开帖子，所有人可见（GJ）
            models.Q(visibility="UNLISTED") |  # Unlisted posts accessible via direct link / 需要链接访问的未列出帖子（GJ）
            models.Q(visibility="FRIENDS", author__friends=user) # Friends-only posts visible to friends / 仅好友可见的帖子（GJ）
        ).exclude(visibility="DELETED")  # Exclude deleted posts for regular users / 普通用户无法看到已删除的帖子（GJ）

    def __str__(self):
        """
        Return the post title as its string representation.
        返回帖子标题作为字符串表示。（GJ）
        """
        return self.title
    
    def like_count(self):
        """
        Return the total number of likes for this post.
        """
        return self.likes.count()

    def comment_count(self):
        """
        Return the total number of comments for this post.
        """
        return self.comments.count()

class Like(models.Model):
    """Model to represent likes on a post."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)     # User who liked the post
    post = models.ForeignKey(Post, related_name="likes", on_delete=models.CASCADE)  # The liked post
    created_at = models.DateTimeField(auto_now_add=True)    # Timestamp for when the like was added

    class Meta:
        unique_together = ("user", "post")  # Ensures a user can only like a post once

class Comment(models.Model):
    """Model to represent comments on a post."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)   # User who wrote the comment
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)  # The commented post
    content = models.TextField()  # Comment text
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the comment was added

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post}"