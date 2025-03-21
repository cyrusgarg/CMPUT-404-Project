from rest_framework import serializers
from .models import Post, Like, Comment
from identity.models import Author
from rest_framework.pagination import PageNumberPagination
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
    id = serializers.CharField(required=False)  # Allow writing existing IDs
    #id = serializers.SerializerMethodField()  # Full API URL for post
    author = serializers.SerializerMethodField()  # Full author details
    content = serializers.SerializerMethodField()  # Convert Markdown/Base64 images
    comments = serializers.SerializerMethodField()  # Include comments
    likes = serializers.SerializerMethodField()  # Include likes
    
    #author = serializers.CharField(source='author.username', read_only=True)  # Store author as username string / 将作者存储为用户名字符串（GJ）
     
    class Meta:
        model = Post  # Specify model / 指定模型（GJ）
        fields = [
            "type","title","id","description","page","contentType", "content", 
             "author", "comments", "likes","published", "visibility"
        ]  # Define the fields to be serialized / 定义需要序列化的字段（GJ）

    def get_id(self, obj):
        """Returns the full API URL for the post."""
        return f"{obj.author.author_profile.host}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}"

    def get_page(self, obj):
        """Returns the HTML page URL for the post."""
        return f"{obj.author.author_profile.host}/authors/{obj.author.author_profile.author_id}/posts/{obj.id}"

    def get_author(self, obj):
        """Returns the author details in the required format."""
        return obj.author.author_profile.to_dict()
          
    def get_comments(self, obj):
        """Fetches comments in the required format."""
        request = self.context.get("request")
        if request is None:
            return {"type": "Comments", "id": obj.id, "page": obj.id, "page_number": 1, "size": 0, "count": 0, "src": []}

        comments = Comment.objects.filter(post=obj).order_by("-created_at")  # Get likes for the comment
        
        paginator = CommentLikePagination()
        paginated_comments = paginator.paginate_queryset(comments, request)
        serializer = CommentSerializer(paginated_comments, many=True, context=self.context)
        
        return {
            "type": "comments",
            "id": f"{obj.author.author_profile.host}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
            "page": f"{obj.author.author_profile.host}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
            "page_number": paginator.page.number if paginator.page else 1,
            "size": paginator.page.paginator.per_page if paginator.page else 50,
            "count": comments.count(),
            "src": serializer.data  # Include paginated like objects
        }

    def get_likes(self, obj):
        """Fetches likes for the post."""
        request = self.context.get("request")
        if request is None:
            return {"type": "likes", "id": obj.id, "page": obj.id, "page_number": 1, "size": 0, "count": 0, "src": []}

        likes = Like.objects.filter(post=obj).order_by("-created_at")  # Get likes for the comment
        
        paginator = CommentLikePagination()
        paginated_likes = paginator.paginate_queryset(likes, request)
        serializer = LikeSerializer(paginated_likes, many=True, context=self.context)
        
        return {
            "type": "likes",
            "id": f"{obj.author.author_profile.host}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
            "page": f"{obj.author.author_profile.host}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
            "page_number": paginator.page.number if paginator.page else 1,
            "size": paginator.page.paginator.per_page if paginator.page else 50,
            "count": likes.count(),
            "src": serializer.data  # Include paginated like objects
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
        validated_data.pop('type', None)  # Remove 'type' if present
        post_id = validated_data.pop('id', None)  # Extract the ID from request data

        if post_id:
            # Ensure it doesn't already exist before creating
            existing_post = Post.objects.filter(id=post_id).first()
            if existing_post:
                raise serializers.ValidationError({"id": "Post with this ID already exists."})

            return Post.objects.create(id=post_id, **validated_data)  # Use provided ID

        return Post.objects.create(**validated_data)  # Default behavior

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
        #validated_data.pop('type', None)  # Remove 'type' if present
        if instance.author != request_user:
            raise serializers.ValidationError("You do not have permission to edit this post.")  # Prevent unauthorized edits / 防止未授权编辑（GJ）

        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.content = validated_data.get('content', instance.content)
        instance.contentType = validated_data.get('contentType', instance.contentType)
        instance.visibility = validated_data.get('visibility', instance.visibility)
        instance.save()
        return instance

class LikeSerializer(serializers.ModelSerializer):
    """
    Serializer for Like model, ensuring response matches API expectations.
    """
    type = serializers.CharField(default="like")
    id = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()
    published = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%S%z")

    class Meta:
        model = Like
        fields = ["type", "author", "published", "id","object"]

    def get_id(self, obj):
        """Returns the full API URL for the like."""
        return obj.get_id()

    def get_author(self, obj):
        """Returns the author details in the required format."""
        return obj.user.author_profile.to_dict()

    def get_object(self, obj):
        """Returns the liked object (post or comment)."""
        return obj.get_object_url()

class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model to convert data into JSON format."""
    
    type = serializers.CharField(default="comment", read_only=True)
    id = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()
    page = serializers.SerializerMethodField()
    published=serializers.SerializerMethodField()
    contentType = serializers.SerializerMethodField()
    comment=serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["type","author", "comment","contentType", "published","id", "post", "page","likes"]

    def get_id(self, obj):
        return obj.get_absolute_url()

    def get_post(self, obj):
        return f"{obj.post.author.author_profile.host}/api/authors/{obj.post.author.author_profile.author_id}/posts/{obj.post.id}"

    def get_page(self, obj):
        return f"{obj.post.author.author_profile.host}/authors/{obj.post.author.author_profile.author_id}/posts/{obj.post.id}"

    def get_author(self, obj):
        return obj.user.author_profile.to_dict()  # Use the `to_dict()` method
    
    def get_contentType(self,obj):
        return obj.post.contentType
    
    def get_published(self,obj):
        return obj.created_at.strftime("%Y-%m-%dT%H:%M:%S%z")

    def get_comment(self,obj):
        return obj.content

    def get_likes(self, obj):
        """Retrieve likes on this comment."""
        request = self.context.get("request")
        if request is None:
            return {"type": "likes", "id": obj.get_like_url(), "page": obj.get_like_url(), "page_number": 1, "size": 0, "count": 0, "src": []}

        likes = Like.objects.filter(comment=obj).order_by("-created_at")  # Get likes for the comment
        
        paginator = CommentLikePagination()
        paginated_likes = paginator.paginate_queryset(likes, request)
        serializer = LikeSerializer(paginated_likes, many=True, context=self.context)
        #print("count:",likes.count())
        return {
            "type": "likes",
            "id": f"{obj.post.author.author_profile.host}/api/authors/{obj.user.author_profile.author_id}/commented/{obj.id}/likes",
            "page": f"{obj.post.author.author_profile.host}/api/authors/{obj.user.author_profile.author_id}/commented/{obj.id}/likes",
            "page_number": paginator.page.number if paginator.page else 1,
            "size": paginator.page.paginator.per_page if paginator.page else 50,
            "count": likes.count(),
            "src": serializer.data  # Include paginated like objects
        }
    
    def create(self, validated_data):
        # Example: extract post id from the request data or context
        request = self.context.get("request")
        post_url = request.data.get("post")  # or use another key like "post_id"
        if not post_url:
            raise serializers.ValidationError("Post information is required.")
        
        # Extract the post id from the URL (adjust the logic as needed)
        post_id = post_url.rstrip("/").split("/")[-1]
        try:
            post_instance = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            raise serializers.ValidationError("Post not found.")

        validated_data["post"] = post_instance
        
        # Set the user (from remote author or context)
        remote_author_data = request.data.get("author", {})
        remote_author_id = remote_author_data.get("id")
        if remote_author_id:
            remote_author_serial = remote_author_id.rstrip("/").split("/")[-1]
            local_author = Author.objects.filter(author_id=remote_author_serial).first()
            if local_author:
                validated_data["user"] = local_author.user
            else:
                raise serializers.ValidationError("Remote author not found.")
        else:
            inbox_author = self.context.get("inbox_author")
            if inbox_author:
                validated_data["user"] = inbox_author.user
            else:
                raise serializers.ValidationError("Author information is missing.")
        
        return Comment.objects.create(**validated_data)

            

class CommentLikePagination(PageNumberPagination):
    """
    Custom pagination for Likes.
    Ensures proper structure with page number, size, and count.
    """
    page_size_query_param = "size"  # Allow dynamic page size via query parameters
    page_size = 5  # Default page size
    max_page_size = 50  # Limit max likes per request

#Not using it from 12 March 2025
# def get_content(self, obj):
    #     """Handles content formatting based on contentType (Markdown, Plain Text, Base64 Images)."""
    #     print("Line 58")
    #     if obj.contentType == 'text/markdown':
    #         return markdown.markdown(obj.content, extensions=['extra'])
        
    #     elif obj.contentType.startswith('image/'):
    #       if obj.image:  # Ensure there is an image
    #           file_path = obj.image.path
    #           content_type = obj.contentType  # Ensure it's in the correct format like "image/png;base64"
              
    #           try:
    #               with open(file_path, "rb") as image_file:
    #                   encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    #               return f"data:{content_type};base64,{encoded_string}"
    #           except FileNotFoundError:
    #               return None  # Handle missing files gracefully

    #     return obj.content    # Default to plain text content if no matching contentType