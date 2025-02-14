from rest_framework import serializers
from .models import Post
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
    author = serializers.CharField(source='author.username', read_only=True)  # Store author as username string / 将作者存储为用户名字符串（GJ）

    class Meta:
        model = Post  # Specify model / 指定模型（GJ）
        fields = [
            "id", "author", "title", "description", "content", 
            "contentType", "published", "visibility"
        ]  # Define the fields to be serialized / 定义需要序列化的字段（GJ）

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
