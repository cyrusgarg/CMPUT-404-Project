from rest_framework import serializers
from .models import Post
from identity.models import Author
import markdown
import base64
from django.contrib.auth.models import User  # Import Django User model / 导入Django用户模型（GJ）

class PostSerializer(serializers.ModelSerializer):
    """
    Serializer for the Post model.
    用于序列化 Post 模型的数据。（GJ）

    - Converts model instances to JSON format.
      将模型实例转换为 JSON 格式。（GJ）
    - Ensures visibility and content type choices are respected.
      确保可见性和内容类型的选择有效。（GJ）
    """
    type = serializers.CharField(default="post")
    page = serializers.SerializerMethodField()  # HTML Page URL
    id = serializers.SerializerMethodField()  # Full API URL for post
    author = serializers.SerializerMethodField()  # Full author details
    content = serializers.SerializerMethodField()  # Convert Markdown/Base64 images
    comments = serializers.SerializerMethodField()  # Include comments
    likes = serializers.SerializerMethodField()  # Include likes
    image = serializers.ImageField(required=False, allow_null=True)
    #author = serializers.CharField(source='author.username', read_only=True)  # Store author as username string / 将作者存储为用户名字符串（GJ）

    class Meta:
        model = Post  # Specify model / 指定模型（GJ）
        fields = [
            "type","title","id","description","page","contentType", "content", 
             "author", "comments", "likes","published", "visibility", "image" 
        ]  # Define the fields to be serialized / 定义需要序列化的字段（GJ）

    def get_id(self, obj):
        """Returns the full API URL for the post."""
        return f"{obj.author.host}/api/authors/{obj.author.author_id}/posts/{obj.id}"

    def get_page(self, obj):
        """Returns the HTML page URL for the post."""
        return f"{obj.author.host}/authors/{obj.author.author_id}/posts/{obj.id}"

    def get_author(self, obj):
        """Returns the author details in the required format."""
        return {
            "type": "author",
            "id": obj.author.author_id,
            "host": obj.author.host,
            "displayName": obj.author.display_name,
            "github": obj.author.github,
            "profileImage": obj.author.profile_image.url if obj.author.profile_image else "",
            "page": obj.author.page
        }
      
    def get_content(self, obj):
        """Handles content formatting based on contentType (Markdown, Plain Text, Base64 Images)."""
        if obj.contentType == 'text/markdown':
            return markdown.markdown(obj.content, extensions=['extra'])
        
        elif obj.contentType.startswith('image/'):
          if obj.image:  # Ensure there is an image
              file_path = obj.image.path
              content_type = obj.contentType  # Ensure it's in the correct format like "image/png;base64"
              
              try:
                  with open(file_path, "rb") as image_file:
                      encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                  return f"data:{content_type};base64,{encoded_string}"
              except FileNotFoundError:
                  return None  # Handle missing files gracefully

        return obj.content    # Default to plain text content if no matching contentType
      
    def get_comments(self, obj):
        """Fetches comments in the required format."""
        return ""
        comments = obj.comments.order_by('-published')[:5]  # Fetch latest 5 comments
        return {
            "type": "comments",
            "page": self.get_page(obj),
            "id": f"{self.get_id(obj)}/comments",
            "page_number": 1,
            "size": 5,
            "count": obj.comments.count(),
            "src": [
                {
                    "type": "comment",
                    "id": comment.get_id(),
                    "author": {
                        "type": "author",
                        "id": comment.author.id,
                        "page": comment.author.page,
                        "host": comment.author.host,
                        "displayName": comment.author.display_name,
                        "github": comment.author.github,
                        "profileImage": comment.author.profile_image.url if comment.author.profile_image else "",
                    },
                    "comment": comment.text,
                    "contentType": "text/markdown",
                    "published": comment.published.isoformat()
                }
                for comment in comments
            ]
        }

    def get_likes(self, obj):
        """Fetches likes for the post."""
        return ""
        likes = obj.likes.order_by('-published')[:5]  # Fetch latest 5 likes
        return {
            "type": "likes",
            "page": self.get_page(obj),
            "id": f"{self.get_id(obj)}/likes",
            "page_number": 1,
            "size": 5,
            "count": obj.likes.count(),
            "src": [
                {
                    "type": "like",
                    "id": like.get_id(),
                    "author": {
                        "type": "author",
                        "id": like.author.id,
                        "page": like.author.page,
                        "host": like.author.host,
                        "displayName": like.author.display_name,
                        "github": like.author.github,
                        "profileImage": like.author.profile_image.url if like.author.profile_image else "",
                    },
                    "published": like.published.isoformat(),
                    "object": self.get_id(obj)
                }
                for like in likes
            ]
        }
    
    def validate_visibility(self, value):
        """
        Validate that the visibility choice is valid.
        确保可见性字段的值有效。（GJ）
        """
        if value not in ["PUBLIC", "FRIENDS", "UNLISTED", "DELETED"]:
            raise serializers.ValidationError("Invalid visibility option.")  # Raise error if invalid / 如果无效，则抛出错误（GJ）
        return value

    def get_content(self, obj):
        """
        Convert Markdown content to HTML if applicable.
        如果帖子内容是Markdown格式，则转换为HTML。（GJ）
        """
        return obj.get_formatted_content()

    def create(self, validated_data):
        """
        Create a new Post instance.
        创建新的帖子实例。（GJ）
        """
        return Post.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Update an existing Post instance.
        更新已有的帖子实例。（GJ）

        - Only the post author can update the post.
          只有帖子作者可以更新帖子。（GJ）
        - Prevent changes to the author field.
          禁止更改作者字段。（GJ）
        """
        request_user = self.context['request'].user  # Get the current user / 获取当前用户（GJ）

        if instance.author != request_user:
            raise serializers.ValidationError("You do not have permission to edit this post.")  # Prevent unauthorized edits / 防止未授权编辑（GJ）

        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.content = validated_data.get('content', instance.content)
        instance.contentType = validated_data.get('contentType', instance.contentType)
        instance.visibility = validated_data.get('visibility', instance.visibility)
        instance.save()
        return instance

