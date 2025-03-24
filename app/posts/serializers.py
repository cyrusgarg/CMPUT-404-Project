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
    #author = serializers.JSONField(write_only=True, required=False)  # Accept author input
    author = serializers.SerializerMethodField()  # Full author details
    content = serializers.SerializerMethodField()  # Convert Markdown/Base64 images
    comments = serializers.SerializerMethodField()  # Include comments
    likes = serializers.SerializerMethodField()  # Include likes
    image = serializers.CharField(write_only=True, required=False)
    #author = obj.author.author_profile.host serializers.CharField(source='author.username', read_only=True)  # Store author as username string / 将作者存储为用户名字符串（GJ）
     
    class Meta:
        model = Post  # Specify model / 指定模型（GJ）
        fields = [
            "type","title","id","description","page","contentType", "content", 
             "author", "comments", "likes","published", "visibility", "image"
        ]  # Define the fields to be serialized / 定义需要序列化的字段（GJ）
        extra_kwargs = {"image": {"write_only": True}}  # Ensures image is input-only

    def to_representation(self, instance):
        """Customize the serialized output to dynamically override `id`."""
        data = super().to_representation(instance)
        data.pop("image", None)
        data["id"] = self.get_id(instance)  # Ensure `id` is dynamically generated
        data["author"] = self.get_author(instance)  # Use `get_author` for response
        return data

    def get_id(self, obj):
        """Returns the full API URL for the post."""
        request = self.context.get("request")
        base_url = f"https://{request.get_host()}" if request else obj.author.author_profile.host
        return f"{base_url}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}"

    def get_page(self, obj):
        """Returns the HTML page URL for the post."""
        request = self.context.get("request")  # Retrieve request safely
        base_url = f"https://{request.get_host()}" if request else obj.author.author_profile.host
        return f"{base_url}/authors/{obj.author.author_profile.author_id}/posts/{obj.id}"

    def get_author(self,obj,request=None):
        """Returns the author details in the required format."""
        request = self.context.get("request")
        return obj.author.author_profile.to_dict(request=request) if hasattr(obj.author, 'author_profile') else None
          
    def get_comments(self, obj):
        """Fetches comments in the required format."""
        request = self.context.get("request")
        if request is None:
            return {"type": "Comments", "id": obj.id, "page": obj.id, "page_number": 1, "size": 0, "count": 0, "src": []}

        base_url = f"https://{request.get_host()}" if request else obj.author.author_profile.host

        comments = Comment.objects.filter(post=obj).order_by("-created_at")

        paginator = CommentLikePagination()
        paginated_comments = paginator.paginate_queryset(comments, request)
        serializer = CommentSerializer(paginated_comments, many=True, context=self.context)

        return {
            "type": "comments",
            "id": f"{base_url}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/comments",
            "page": f"{base_url}/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/comments",
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

        base_url = f"https://{request.get_host()}" if request else obj.author.author_profile.host

        likes = Like.objects.filter(post=obj).order_by("-created_at")

        paginator = CommentLikePagination()
        paginated_likes = paginator.paginate_queryset(likes, request)
        serializer = LikeSerializer(paginated_likes, many=True, context=self.context)

        return {
            "type": "likes",
            "id": f"{base_url}/api/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
            "page": f"{base_url}/authors/{obj.author.author_profile.author_id}/posts/{obj.id}/likes",
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
        print("134")
        # author_data = validated_data.pop("author", None)  # Get author input
        validated_data.pop('type', None)  # Remove 'type' if present
        #validated_data.pop("author", None)

        # Convert image if provided
        image = validated_data.pop("image", None)
        if image:
            validated_data["image"] = self.image_to_base64(image)

        # Create post object
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
        request_user = self.context['request'].user
        # request_obj = self.context['request']
        # request_user = getattr(request_obj, 'node_user', request_obj.user)
        
        #validated_data.pop('type', None)  # Remove 'type' if present
        if instance.author != request_user:
            raise serializers.ValidationError("You do not have permission to edit this post.")  # Prevent unauthorized edits / 防止未授权编辑（GJ）
        image = validated_data.pop("image", None)
        # author_data = validated_data.pop("author", None)  # Ignore author updates
        validated_data.pop("author", None)  # Ignore author updates
        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get('description', instance.description)
        instance.content = validated_data.get('content', instance.content)
        instance.contentType = validated_data.get('contentType', instance.contentType)
        instance.visibility = validated_data.get('visibility', instance.visibility)
        if image:
            instance.image = self.image_to_base64(image)
        instance.save()
        return instance

    def image_to_base64(self, image_file):
        """
        Converts an uploaded image file to a base64 encoded string.
        """
        try:
            return f"data:image/jpeg;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

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
        request = self.context.get("request")
        return obj.get_id(request=request)

    def get_author(self, obj):
        """Returns the author details in the required format."""
        request = self.context.get("request")
        return obj.user.author_profile.to_dict(request=request)

    def get_object(self, obj):
        """Returns the liked object (post or comment)."""
        request = self.context.get("request")
        return obj.get_object_url(request=request)

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
        request = self.context.get("request")
        return obj.get_absolute_url(request=request)

    def get_post(self, obj):
        request = self.context.get("request")
        base_url = f"https://{request.get_host()}" if request else obj.post.author.author_profile.host
        return f"{base_url}/api/authors/{obj.post.author.author_profile.author_id}/posts/{obj.post.id}"

    def get_page(self, obj):
        request = self.context.get("request")
        base_url = f"https://{request.get_host()}" if request else obj.post.author.author_profile.host
        return f"{base_url}/authors/{obj.post.author.author_profile.author_id}/posts/{obj.post.id}"

    def get_author(self,obj):
        request = self.context.get("request")
        base_url = f"https://{request.get_host()}" if request else obj.post.author.author_profile.host
        return obj.user.author_profile.to_dict(request=request)  # Use the `to_dict()` method
    
    def get_contentType(self,obj):
        return obj.post.contentType
    
    def get_published(self,obj):
        return obj.created_at.strftime("%Y-%m-%dT%H:%M:%S%z")

    def get_comment(self,obj):
        return obj.content

    def get_likes(self, obj):
        """Retrieve likes on this comment dynamically using request.get_host()."""
        request = self.context.get("request")
        if request is None:
            return {
                "type": "likes",
                "id": obj.get_like_url(),
                "page": obj.get_like_url(),
                "page_number": 1,
                "size": 0,
                "count": 0,
                "src": []
            }

        base_url = f"https://{request.get_host()}" if request else "https://default-host.com"
        likes = Like.objects.filter(comment=obj).order_by("-created_at")

        paginator = CommentLikePagination()
        paginated_likes = paginator.paginate_queryset(likes, request)
        serializer = LikeSerializer(paginated_likes, many=True, context=self.context)

        return {
            "type": "likes",
            "id": f"{base_url}/api/authors/{obj.user.author_profile.author_id}/commented/{obj.id}/likes",
            "page": f"{base_url}/api/authors/{obj.user.author_profile.author_id}/commented/{obj.id}/likes",
            "page_number": paginator.page.number if paginator.page else 1,
            "size": paginator.page.paginator.per_page if paginator.page else 50,
            "count": likes.count(),
            "src": serializer.data
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



#if author_data:
        #     author_id = author_data.get("id", "").split("/")[-1]  # Extract author UUID
        #     author = Author.objects.filter(author_id=author_id).first()
        #     print("148")
        #     if not author:
        #         # Create new Author if author does not exist
        #         username = f"remote_{author_id[:8]}"
        #         user, created = User.objects.get_or_create(username=username)

        #         # Create the author
        #         author = Author.objects.create(
        #             user=user,
        #             author_id=author_id,
        #             display_name=author_data.get("displayName", "Unknown Author"),
        #             github=author_data.get("github", ""),
        #             host=author_data.get("host", settings.SITE_URL),
        #             profile_image=author_data.get("profileImage", ""),
        #         )

        #     validated_data["author"] = author.user  # Assign the user linked to the author    
        #     print("165")