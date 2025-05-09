from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from identity.models import Author, Following, Friendship
from posts.models import Post,Comment,Like
from posts.serializers import PostSerializer, CommentSerializer,LikeSerializer
from django.contrib.auth.models import User
from identity.models import Following, FollowRequests, RemoteFollowRequests, Friendship, RemoteFollower, RemoteFollowee, RemoteFriendship
import json, urllib.parse, re, base64
from django.db.models import Q
from .id_mapping import get_uuid_for_numeric_id
from rest_framework.views import APIView
from django.utils.timezone import now
import uuid
from rest_framework.permissions import IsAuthenticated
from .authentication import NodeBasicAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
import requests
from urllib.parse import unquote
from rest_framework.authentication import SessionAuthentication
from django.conf import settings
from identity.id_mapping import get_uuid_for_numeric_id
from identity.models import RemoteAuthor

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([NodeBasicAuthentication, SessionAuthentication])

def author_posts(request, author_id):
    """
    GET: Returns paginated posts of a specific author with proper visibility rules.
    POST: Allows the author to create a new post.
    """

    # Retrieve author and their linked user
    author = get_object_or_404(Author, author_id=author_id)
    user = author.user

    if request.method == 'GET':


        if request.user.is_authenticated:
            is_follower = Following.objects.filter(follower=request.user, followee=user).exists()
            is_friend = Friendship.objects.filter(user1=request.user, user2=user).exists() or \
                    Friendship.objects.filter(user1=user, user2=request.user).exists()
        else:
            is_follower = False
            is_friend = False


        # Visibility filters based on authentication and relationships
        if not request.user.is_authenticated:
            visibility_filter = ["PUBLIC"]
        elif request.user == author.user:  # Author of the posts
            visibility_filter = ["PUBLIC", "FRIENDS", "UNLISTED"]
        elif is_friend:  # Mutual friendship
            visibility_filter = ["PUBLIC", "FRIENDS", "UNLISTED"]
        elif is_follower:  # Following but not friends
            visibility_filter = ["PUBLIC", "UNLISTED"]
        else:
            visibility_filter = ["PUBLIC"]

        # Fetch posts with applied filters
        posts = Post.objects.filter(
            author=user, visibility__in=visibility_filter
        ).order_by("-published")

        # Apply pagination
        paginator = CustomPagination()
        paginated_posts = paginator.paginate_queryset(posts, request)

        # Serialize posts
        serializer = PostSerializer(paginated_posts, many=True,context={'request': request})

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)

    elif request.method == 'POST':
        # Only allow authenticated authors to create posts
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication is required to create a post."}, status=status.HTTP_401_UNAUTHORIZED)

        if request.user != author.user:
            return Response({"detail": "You are not authorized to create posts for this author."}, status=status.HTTP_403_FORBIDDEN)

        # Debugging: Check if content exists in the request
        print("Received Content:", request.data.get("content"))

        required_fields = ["title", "description", "contentType", "content", "visibility"]
        missing_fields = [field for field in required_fields if field not in request.data or not request.data[field]]

        if missing_fields:
            return Response(
                {"detail": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Extract fields from request
        title = request.data["title"]
        description = request.data["description"]
        contentType = request.data["contentType"]
        content = request.data["content"]
        visibility = request.data["visibility"]
        image=request.data.get("image","")

        post = Post.objects.create(
            title=title,
            description=description,
            contentType=contentType,
            content=content,
            visibility=visibility,
            author=author.user,
            published=now(),
            image=image
        )

        # Serialize the created post and return response
        serializer = PostSerializer(post, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

# Custom Pagination class
class CustomPagination(PageNumberPagination):
    """
    Custom pagination response matching the required format.
    """
    page_size = 5  # Default number of posts per page
    page_size_query_param = 'size'  # Allows the client to set page size
    max_page_size = 50  # Limit the maximum page size

    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to set default page number and size if not provided.
        """
        request_query_params = request.query_params.copy()

        # Set default 'page' to 1 if not provided
        if 'page' not in request_query_params:
            request_query_params['page'] = '1'

        # Set default 'size' to 5 if not provided
        if 'size' not in request_query_params:
            request_query_params['size'] = str(self.page_size)

        request._request.GET = request_query_params  # Force request object to use new defaults

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        return Response({
            "type": "posts",
            "page_number": self.page.number,  # Current page number
            "size": self.page.paginator.per_page,  # Number of items per page
            "count": self.page.paginator.count,  # Total number of items
            "src": data  # Serialized list of posts
        })

@api_view(['GET', 'DELETE', 'PUT'])
@permission_classes([AllowAny])  # Allow unrestricted access initially
def author_post_detail(request, author_id, post_id):
    """
    Handles getting, deleting, and updating a specific post by an author 
    with proper visibility and authorization checks.
    """
    # Retrieve the author based on the author_id
    author = get_object_or_404(Author, author_id=author_id)
    user = author.user  # Get the User object linked to the Author

    # Retrieve the post
    post = get_object_or_404(Post, id=post_id)

    # Handle GET request
    if request.method == 'GET':
        if post.visibility == "PUBLIC":
            # Anyone can access public posts
            serializer = PostSerializer(post,context={'request': request})
            return Response(serializer.data)

        elif post.visibility == "FRIENDS":
            if request.user.is_authenticated and (
                request.user == user or request.user in author.friends.all()
            ):
                serializer = PostSerializer(post,context={'request': request})
                return Response(serializer.data)
            return Response({"detail": "Authentication required for friends-only posts."},
                            status=status.HTTP_403_FORBIDDEN)

        elif post.visibility == "UNLISTED":
            # Allow direct access without restrictions
            serializer = PostSerializer(post,context={'request': request})
            return Response(serializer.data)

        else:
            return Response({"detail": "You do not have permission to view this post."},
                            status=status.HTTP_403_FORBIDDEN)

    # Handle DELETE request (Only the author of the post can delete)
    elif request.method == 'DELETE':
        if request.user.is_authenticated and request.user == user:
            # post.delete()
            post.visibility = "DELETED"  
            post.save()
            return Response({"detail": "Post deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "You do not have permission to delete this post."},
                        status=status.HTTP_403_FORBIDDEN)

    # Handle PUT request (Only the author of the post can update)
    elif request.method == 'PUT':
        if request.user.is_authenticated and request.user == user:
            serializer = PostSerializer(post, data=request.data, partial=True,context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "You do not have permission to update this post."},
                        status=status.HTTP_403_FORBIDDEN)



@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Only authenticated users can access
def auth_test(request):
    """
    Simple endpoint to test authentication.
    """
    return Response({"message": f"Authentication successful for user {request.user.username}"})

def get_mutual_friend_list(user):
    # Get the followers of the current user / 获取当前用户的关注者（即用户关注的对象）（GJ）
    following_ids = Following.objects.filter(follower=user).values_list("followee_id", flat=True)  

    # Get users who follow the current user / 获取关注当前用户的用户（即谁关注了我）（GJ）
    followers_ids = Following.objects.filter(followee=user).values_list("follower_id", flat=True)  

    # Users who follow each other are friends/ 互相关注的用户即为好友（friends）（GJ）
    mutual_friends_ids = set(following_ids).intersection(set(followers_ids))
    return mutual_friends_ids

class CommentPagination(PageNumberPagination):
    """
    Custom pagination response matching the required format for comments.
    """
    page_size = 5  # Default number of comments per page
    page_size_query_param = 'size'
    max_page_size = 50

    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to set default page number and size if not provided.
        """
        request_query_params = request.query_params.copy()

        # Set default 'page' to 1 if not provided
        if 'page' not in request_query_params:
            request_query_params['page'] = '1'

        # Set default 'size' to 5 if not provided
        if 'size' not in request_query_params:
            request_query_params['size'] = str(self.page_size)

        request._request.GET = request_query_params  # Force request object to use new defaults

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data, post, request):
        """Returns paginated response with additional `page` and `id` fields, now with `request`."""
        base_url = f"https://{request.get_host()}" if request else "https://commenthost.com"
        post_author = post.author.author_profile

        if hasattr(self, 'page') and self.page is not None:
            page_number = self.page.number
            size = self.page.paginator.per_page
            count = self.page.paginator.count
        else:
            # Defaults if there is no pagination info (e.g., when there are no items)
            page_number = 1
            size = 0
            count = 0

        return Response({
            "type": "comments",
            "page": f"{base_url}/authors/{post_author.author_id}/posts/{post.id}",
            "id": f"{base_url}/api/authors/{post_author.author_id}/posts/{post.id}/comments",
            "page_number": page_number,
            "size": size,
            "count": count,
            "src": data  # Serialized list of comments
        })


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def author_commented(request, author_id):
    """
    GET: Get all comments made by an author.
    POST: Post a new comment on a post.
    """
    author = get_object_or_404(Author, author_id=author_id)
    # user = request.user if request.user.is_authenticated else Non
    user = author.user  # Convert Author to User 
    
    if request.method == "GET":
        comments = Comment.objects.filter(user=user).order_by('-created_at')
        if not comments.exists():
            return Response({
                "type": "comments",
                "page": "",
                "id": "",
                "page_number": 1,
                "size": 0,
                "count": 0,
                "src": []
            })
        filtered_comments = []
        for comment in comments:
            post = comment.post

            # PUBLIC: Always include
            if post.visibility == "PUBLIC":
                filtered_comments.append(comment)

            # UNLISTED: Include for any authenticated user (as it's accessible via direct link)
            elif post.visibility == "UNLISTED":
                filtered_comments.append(comment)

            # FRIENDS: Include only if the request user is a friend of the post author
            elif post.visibility == "FRIENDS":
                mutual_friends_ids= get_mutual_friend_list(post.author)
                #if user and (user == post.author or user in post.author.author_profile.friends.all()):
                if user and (user == post.author or user.id in mutual_friends_ids):
                    filtered_comments.append(comment)

        if not filtered_comments:
            return Response({
                "type": "comments",
                "page": "",
                "id": "",
                "page_number": 1,
                "size": 0,
                "count": 0,
                "src": []
            })

        paginator = CommentPagination()
        paginated_comments = paginator.paginate_queryset(filtered_comments, request)
        serializer = CommentSerializer(paginated_comments, many=True,context={"request": request})
        post = filtered_comments[0].post
        return paginator.get_paginated_response(serializer.data,post,request)

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        
        # Validate if the post exists
        post = get_object_or_404(Post, id=data.get("post"))

        comment = Comment.objects.create(
            user=user,
            post=post,
            content=data.get("comment", ""),
        )

        return Response(CommentSerializer(comment,context={"request": request}).data, status=status.HTTP_201_CREATED)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_comment(request, author_id, comment_id):
    """
    GET: Retrieve a specific comment made by an author.
    """
    author = get_object_or_404(Author, author_id=author_id)
    user = author.user  # Convert Author to User
    comment = get_object_or_404(Comment, id=comment_id, user=user)

    serializer = CommentSerializer(comment, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_comment(request, author_id, comment_id):
    """Allow an authenticated user to like/unlike a comment."""
    comment = get_object_or_404(Comment, id=comment_id)
    user = request.user

    if user in comment.likes.all():
        comment.likes.remove(user)
        comment.like_count -= 1
    else:
        comment.likes.add(user)
        comment.like_count += 1

    comment.save()

    return Response({"message": "Like status updated", "like_count": comment.like_count})

@api_view(['GET'])
@permission_classes([AllowAny])
def get_comment_likes(request, author_id, comment_id):
    """Retrieve all likes on a specific comment."""
    comment = get_object_or_404(Comment, id=comment_id)

    # Ensure `comment.likes.all()` exists and is not empty
    if not comment.likes.exists():
        return Response({
            "type": "likes",
            "id": f"https://{request.get_host()}/api/authors/{author_id}/comments/{comment_id}/likes",
            "page": f"https://{request.get_host()}/authors/{author_id}/comments/{comment_id}/likes",
            "page_number": 1,
            "size": 50,
            "count": 0,
            "src": []
        }, status=200)

    likes_list = []
    for user in comment.likes.all():
        # Ensure `author_profile` exists
        if hasattr(user, 'author_profile'):
            likes_list.append(user.author_profile.to_dict(request=request))
        else:
            print(f"Warning: User {user.id} has no author_profile!")

    # Ensure `get_like_url(request=request)` returns a valid URL
    like_url = comment.get_like_url(request=request)
    if like_url is None:
        like_url = f"https://{request.get_host()}/api/authors/{author_id}/comments/{comment_id}/likes"

    return Response({
        "type": "likes",
        "id": like_url,
        "page": f"{comment.get_absolute_url(request=request)}/likes",
        "page_number": 1,
        "size": 50,
        "count": comment.likes.count(),
        "src": likes_list,
    }, status=200)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_comment_by_id(request, comment_id):
    """
    GET: Retrieve a comment by its global ID.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    serializer = CommentSerializer(comment,context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)

class LikePagination(PageNumberPagination):
    """
    Custom pagination for Likes.
    Ensures proper structure with page number, size, and count.
    """
    page_size_query_param = "size"  # Allow dynamic page size via query parameters
    page_size = 5  # Default page size
    max_page_size = 50  # Limit max likes per request

    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to set default page number and size if not provided.
        """
        request_query_params = request.query_params.copy()

        # Set default 'page' to 1 if not provided
        if 'page' not in request_query_params:
            request_query_params['page'] = '1'

        # Set default 'size' to 5 if not provided
        if 'size' not in request_query_params:
            request_query_params['size'] = str(self.page_size)

        request._request.GET = request_query_params  # Force request object to use new defaults

        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data, post, request):
        """
        Returns a paginated response structured as per the spec.
        Now `request` is explicitly passed.
        """
        base_url = f"https://{request.get_host()}" if request else "https://Likehost.com"
        post_author = post.author.author_profile

        return Response({
            "type": "likes",
            "page": f"{base_url}/authors/{post_author.author_id}/posts/{post.id}",
            "id": f"{base_url}/api/authors/{post_author.author_id}/posts/{post.id}/likes",
            "page_number": self.page.number,
            "size": self.page.paginator.per_page,
            "count": self.page.paginator.count,
            "src": data,
        })

@api_view(['GET'])
@permission_classes([AllowAny])
def post_likes(request, author_id, post_id):
    """
    GET: Return all likes for a specific post, following visibility rules.
    """
    author = get_object_or_404(Author, author_id=author_id)
    post = get_object_or_404(Post, id=post_id, author=author.user)

    #if post.visibility not in ["PUBLIC", "UNLISTED"] and request.user != post.author
    if post.visibility not in ["PUBLIC", "UNLISTED"]:
        return Response({"detail": "You do not have permission to view likes on this post."},
                        status=status.HTTP_403_FORBIDDEN)

    likes = Like.objects.filter(post=post).exclude(user=post.author).order_by("-created_at")  
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True,context={"request": request})

    return paginator.get_paginated_response(serializer.data,post,request)

@api_view(['GET'])
@permission_classes([AllowAny])
def comment_likes(request, author_id, post_id, comment_id):
    """
    GET: Return all likes for a specific comment.
    """
    author = get_object_or_404(Author, author_id=author_id)
    post = get_object_or_404(Post, id=post_id, author=author.user)
    comment = get_object_or_404(Comment, id=comment_id, post__id=post_id, user=author.user)

    likes = Like.objects.filter(comment=comment).exclude(user=post.author).order_by("-created_at")
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,post,request)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_author_likes(request, author_id):
    """
    Retrieve a list of things an author has liked.
    """
    author = get_object_or_404(Author, author_id=author_id)
    
    # Retrieve all likes made by this author
    likes = Like.objects.filter(user=author.user).order_by('-created_at')

    # Get a post that this author has liked
    liked_post = Post.objects.filter(likes__user=author.user).distinct().order_by('-published')[0]

    # Paginate the likes using the custom LikePagination
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    # Serialize paginated data
    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,liked_post,request)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_single_like(request, author_id, like_id):
    """
    Retrieve a single like made by an author.
    """
    author = get_object_or_404(Author, author_id=author_id)
    like = get_object_or_404(Like, id=like_id, user=author.user)

    serializer = LikeSerializer(like)

    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_author_likes_by_fqid(request, author_fqid):
    """
    Retrieve a list of things an author has liked.
    """
    #TODO: may not work right now as author does not has fqid
    decoded_fqid = urllib.parse.unquote(author_fqid)
    author = get_object_or_404(Author, fqid=decoded_fqid)
    
    # Retrieve all likes made by this author
    likes = Like.objects.filter(user=author.user).order_by('-created_at')

    # Get a post that this author has liked
    liked_post = Post.objects.filter(likes__user=author.user).distinct().order_by('-published')[0]

    # Paginate the likes using the custom LikePagination
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    # Serialize paginated data
    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,liked_post,request)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_like_by_fqid(request, like_fqid):
    """
    Retrieve a single like by its Fully Qualified ID (FQID).
    """
    decoded_fqid = urllib.parse.unquote(like_fqid)
    #print("decoded_fqid:", decoded_fqid)
    
    #like = Like.objects.filter(Q(fqid=decoded_fqid))
    like = get_object_or_404(Like, fqid=decoded_fqid)
     
    serializer = LikeSerializer(like)

    return Response(serializer.data, status=status.HTTP_200_OK)

class AuthorPagination(PageNumberPagination):
    """
    Custom pagination response matching the required format for authors.
    """
    page_size_query_param = 'size'
    page_size = 200  # Default page size set to 3
    max_page_size = 100  # Maximum allowed page size

    def get_paginated_response(self, data):
        return Response({
            "type": "authors",
            "page_number": self.page.number,
            "size": self.page.paginator.per_page,
            "count": self.page.paginator.count,
            "next": self.get_next_link(),  # Link to next page
            "previous": self.get_previous_link(),  # Link to previous page
            "authors": data  # Serialized list of authors
        })
    

class AuthorListView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Return a paginated list of all authors"""
        #authors = Author.objects.all()
        authors = Author.objects.exclude(display_name__istartswith="remote_")
        
        # Apply pagination
        paginator = AuthorPagination()
        paginated_authors = paginator.paginate_queryset(authors, request)
        
        # Serialize the paginated queryset
        serialized_authors = [author.to_dict(request) for author in paginated_authors]
        
        # Return the paginated response
        return paginator.get_paginated_response(serialized_authors)

class AuthorDetailView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, pk):
        """
        Return details of a specific author
        
        The pk parameter can be a numeric ID instead of a UUID
        """
        # Convert numeric ID to UUID if it's a numeric ID
        try:
            # Check if pk is numeric
            if isinstance(pk, int):
                numeric_id = pk
                uuid_str = get_uuid_for_numeric_id(numeric_id)
                
                if uuid_str is None:
                    return Response({"error": "Author not found"}, status=404)
                    
                # Find the author using the UUID
                author = get_object_or_404(Author, author_id=uuid_str)
            else:
                # If pk is not an integer, it should be a UUID
                try:
                    # Try to validate the UUID
                    uuid_obj = uuid.UUID(str(pk))
                    author = get_object_or_404(Author, author_id=uuid_obj)
                except ValueError:
                    # Not a valid UUID format
                    return Response({"error": "Invalid UUID format"}, status=400)
        except Exception as e:
            return Response({"error": f"Author lookup failed: {str(e)}"}, status=404)
        
        return Response(author.to_dict(request))

@api_view(['GET'])
@permission_classes([AllowAny])
def author_list(request):
    """Return a paginated list of all authors"""
    #authors = Author.objects.all()
    authors = Author.objects.exclude(display_name__istartswith="remote_")
    # Apply pagination
    paginator = AuthorPagination()
    paginated_authors = paginator.paginate_queryset(authors, request)
    
    # Return paginated response
    return paginator.get_paginated_response([author.to_dict(request) for author in paginated_authors])
@api_view(['GET'])
@permission_classes([AllowAny])
def image_post(request, author_id, post_id):
    """
    Retrieve the image from an author's post.

    - Checks post.image field (base64 or URL).
    - If not found, extracts from post.content (HTML <img> tag or markdown).
    - Redirects to the image URL or returns 404.
    """
    author = get_object_or_404(Author, author_id=author_id)
    post = get_object_or_404(Post, id=post_id, author=author.user)

    # Check if there's a direct image field
    if post.image:
        if post.image.startswith("data:image/"):
            try:
                header, encoded = post.image.split(',', 1)
                content_type = header.split(':')[1].split(';')[0]
                missing_padding = len(encoded) % 4
                if missing_padding:
                    encoded += '=' * (4 - missing_padding)
                image_data = base64.b64decode(encoded)
                return HttpResponse(image_data, content_type=content_type)
            except Exception as e:
                print("Error decoding image:", e)
                return Response({"detail": "Invalid image data"}, status=status.HTTP_404_NOT_FOUND)
        elif post.image.startswith("http://") or post.image.startswith("https://"):
            return redirect(post.image)

    # Extract from post content
    img_src = None
    if post.content:
        if BS4_AVAILABLE:
            soup = BeautifulSoup(post.content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag:
                img_src = img_tag.get('src')
        if not img_src:
            match = re.search(r'<img\s+[^>]*src=["\']([^"\']+)["\']', post.content)
            if match:
                img_src = match.group(1)
        if not img_src:
            match_md = re.search(r'!\[.*?\]\((.*?)\)', post.content)
            if match_md:
                img_src = match_md.group(1)

    if img_src:
        return redirect(img_src)

    return Response({"detail": "Not an image"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def post_comment(request, author_id, post_id):
    """
    GET: Retrieve a paginated list of comments for the specified post under a specific author.
         Visibility rules:
           - PUBLIC and UNLISTED posts are accessible to everyone.
           - FRIENDS posts require the request user to be authenticated and either the post's author 
             or in the author's friends list.
    """
    author = get_object_or_404(Author, author_id=author_id)
    post = get_object_or_404(Post, id=post_id, author=author.user)

    # Check visibility before returning comments.
    if post.visibility in ["PUBLIC", "UNLISTED"]:
        pass  # These posts are accessible
    elif post.visibility == "FRIENDS":
        if request.user.is_authenticated:
            if request.user != post.author and request.user not in post.author.author_profile.friends.all():
                return Response(
                    {"detail": "You do not have permission to view comments on this post."},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {"detail": "Authentication is required to view comments on this post."},
                status=status.HTTP_401_UNAUTHORIZED
            )
    else:
        return Response(
            {"detail": "You do not have permission to view comments on this post."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Retrieve and paginate comments
    comments = post.comments.all().order_by("-created_at")
    paginator = CommentPagination()
    paginated_comments = paginator.paginate_queryset(comments, request)
    serializer = CommentSerializer(paginated_comments, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data, post,request)


def extract_uuid_from_url(url):
    """
    Extracts the last path segment from a URL and returns it.
    """
    if not url:
        return None
    parsed = urlparse(url)
    # Remove trailing slash and split the path
    segments = parsed.path.rstrip('/').split('/')
    return segments[-1] if segments else None

def is_integer(value):
    """Check if the value is an integer."""
    return isinstance(value, int) or (isinstance(value, str) and value.isdigit())

def is_uuid(value):
    """Check if the value is a valid UUID."""
    try:
        uuid.UUID(str(value), version=4)
        return True
    except ValueError:
        return False

@api_view(['POST','PUT'])
@authentication_classes([NodeBasicAuthentication])
@permission_classes([IsAuthenticated])
#@permission_classes([AllowAny])
def inbox(request, author_id):
    """
    POST: Accepts remote objects (posts, follow requests, likes, comments)
    and processes them. When sending/updating:
      - posts: the body is a post object (processed with PostSerializer)
      - follow requests: the body is a follow object (added to the inbox for later approval)
      - likes: the body is a like object (processed with LikeSerializer)
      - comments: the body is a comment object (processed with CommentSerializer)
    """
    print("insideinboxview")
    # Get the target author (the owner of this inbox)
    author = get_object_or_404(Author, author_id=author_id)
    data = request.data
    obj_type = data.get("type", "").lower()

    if obj_type == "post":
        print("post data\n",data)
        post_id = data.get("id", "").split("/")[-1]
        print("Line 842: post id:",post_id)
        if is_integer(post_id):
            post_id = get_uuid_for_numeric_id(int(post_id))
        # Extract remote author data
        author_data = data.get("author", {})
        remote_author_id = author_data.get("id", "").split("/")[-1]
        if is_integer(remote_author_id):
            remote_author_id = get_uuid_for_numeric_id(int(remote_author_id))
        remote_host=author_data.get("host","")
        print("Line 851: remote_host:",remote_host)
        print("Line 852: remote_author_id:",remote_author_id)
        # Try to fetch the existing remote author
        remote_author = RemoteAuthor.objects.filter(author_id=remote_author_id,host=remote_host).first()
        if remote_host != "http://[2605:fd00:4:1001:f816:3eff:fecd:2b99]:8000/api/":
            print("Remote author display name:", remote_author.display_name)
            remote_author_display_name=remote_author.display_name
        if not remote_author:
            print("Line 857: Remote author does not exits")
            # Create the Author first
            remote_author, created = Author.objects.get_or_create(
                author_id=remote_author_id,
                host=remote_host,
                defaults={  # Only set these values if creating a new author
                    "display_name": author_data.get("displayName", "Unknown Author"),
                    "github": author_data.get("github", ""),
                    "profile_image": author_data.get("profileImage", ""),
                }
            )

        if remote_author.user is None:
            print("Line 870: Remote author does not has associated user")
            username = f"remote_{remote_author_id}"  # Unique username
            
            # Check if a user with this username already exists
            user = User.objects.filter(username=username).first()

            if user:
                print("Line 877: New user created is already present in db")
                # If the user exists, ensure it isn't already linked to another author
                existing_author = Author.objects.filter(user=user).first()

                if existing_author:
                    print(f"User {username} is already linked to an existing Author. Using existing author and attaching the current author with remote author")
                    #existing_author=remote_author
                    remote_author=existing_author
                    remote_author.display_name = "ahmer"
                    remote_author_display_name = "ahmer"
                    #remote_author.host=remote_host
                else:
                    # Assign the existing user to the remote_author
                    print("Line 888: user does not has associated with author")
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])
            else:
                # Create a new User and assign it to the Author
                print("Line 893: creating new user")
                user = User.objects.create(username=username)
                # Now, double-check if an Author already exists for this user
                existing_author = Author.objects.filter(user=user).first()
                
                if existing_author:
                    print(f"Line 899: Warning: An Author already exists for {username}. Using existing Author.")
                    remote_author = existing_author
                else:
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])  # Ensure only the user field is updated
                # remote_author.user = user
                # remote_author.save(update_fields=["user"])

        #could be add more parameters
        #remote_author.author_id = remote_author_id #shouldn't do it
        remote_author.host=remote_host
        remote_author.save()
        # Attach the correct author to the post data
        #data["author"] = remote_author.user.id  # Ensure it's the linked user
        #print("Inside the post inbox, printing remote_author host",author_data.get("host", settings.SITE_URL))
        # Check if post exists
        is_image_post = False
        content_type = data.get("contentType", "text/plain")
        if content_type.startswith("image/") or "base64" in content_type:
            is_image_post = True
        
        # Check if post exists
        existing_post = Post.objects.filter(id=post_id, author=remote_author.user).first()

        if existing_post:
            # Update existing post manually
            existing_post.title = data.get("title", existing_post.title)
            existing_post.description = data.get("description", existing_post.description)
            
            # Handle image content
            if is_image_post:
                # If it's an image post, store the content as the image
                # Add the data:image/ prefix if not present
                content = data.get("content", "")
                if content and not content.startswith("data:image/"):
                    content_type_prefix = content_type.split(";")[0]  # Get just "image/png" part
                    existing_post.image = f"data:{content_type_prefix};base64,{content}"
                else:
                    existing_post.image = content
                # Keep minimal content
                existing_post.content = data.get("content", "")
            else:
                # Regular text post
                existing_post.content = data.get("content", existing_post.content)
            
            existing_post.contentType = content_type
            existing_post.visibility = data.get("visibility", existing_post.visibility)
            existing_post.remote_url = data.get("id", existing_post.remote_url)
            existing_post.save()
            print("existing post data\n:", existing_post.title,existing_post.visibility)
            return Response(PostSerializer(existing_post, context={'request': request}).data, status=200)

        # Create a new post
        post_data = {
            "id": post_id,
            "author": remote_author.user,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "contentType": content_type,
            "visibility": data.get("visibility", "PUBLIC"),
            "remote_url": data.get("id", ""),
        }
        post_data["author"].author_profile.display_name=remote_author_display_name
        # Handle content based on content type
        if is_image_post:
            # This is an image post
            content = data.get("content", "")
            if content and not content.startswith("data:image/"):
                content_type_prefix = content_type.split(";")[0]  # Get just "image/png" part
                post_data["image"] = f"data:{content_type_prefix};base64,{content}"
            else:
                post_data["image"] = content
            post_data["content"] = ""  # Empty or minimal content for image posts
        else:
            # Regular text post
            post_data["content"] = data.get("content", "")
            post_data["image"] = data.get("image", None)
        
        # Create the post
        print("Author name:",post_data["author"].author_profile.display_name )
        new_post = Post.objects.create(**post_data)
        new_post.author.author_profile.display_name=remote_author_display_name
        new_post.author.author_profile.save(update_fields=["display_name"])
        serializer = PostSerializer(new_post, context={'request': request})
        post_data = serializer.data
        print("newly created post\n",post_data)
        return Response(PostSerializer(new_post, context={'request': request}).data, status=201)

    elif obj_type == "like":
        print("like body\n",data)
        #print("Like object\n",data)

        #return Response(status=200)
        # Process a like object.
        liker_author_url = data.get("author", {}).get("id")
        if not liker_author_url:
            return Response({"error": "Missing liker author information."}, status=status.HTTP_400_BAD_REQUEST)
        # Extract the author_id from the URL
        # liker = Author.objects.filter(author_id=liker_author_url.rstrip("/").split("/")[-1]).first()
        # Extract the liker (author) data
        author_data = data.get("author", {})
        remote_author_id = author_data.get("id", "").split("/")[-1]
        if is_integer(remote_author_id):
            remote_author_id = get_uuid_for_numeric_id(int(remote_author_id))
        remote_host = author_data.get("host", "")

        # Try to fetch the existing remote author
        #remote_author = Author.objects.filter(author_id=remote_author_id, host=remote_host).first()
        remote_author = RemoteAuthor.objects.filter(author_id=remote_author_id,host=remote_host).first()

        if not remote_author:
            # Create the Author if it doesn't exist
            remote_author, created = Author.objects.get_or_create(
                author_id=remote_author_id,
                host=remote_host,
                defaults={
                    "display_name": author_data.get("displayName", "Unknown Author"),
                    "github": author_data.get("github", ""),
                    "profile_image": author_data.get("profileImage", ""),
                }
            )

        if remote_author.user is None:
            username = f"remote_{remote_author_id}"  # Unique username

            user = User.objects.filter(username=username).first()
            if user:
                existing_author = Author.objects.filter(user=user).first()
                if existing_author:
                    remote_author = existing_author
                else:
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])
            else:
                user = User.objects.create(username=username)
                existing_author = Author.objects.filter(user=user).first()
                if existing_author:
                    remote_author = existing_author
                else:
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])

        remote_author.host = remote_host
        remote_author.save()
        # if not liker:
        #     #create it 
        #     return Response({"error": "Liker author not found."}, status=status.HTTP_400_BAD_REQUEST)

        # Determine whether this is a like for a post or a comment.
        object_url = data.get("object")
        if not object_url:
            return Response({"error": "Missing object URL in like."}, status=status.HTTP_400_BAD_REQUEST)
        parts = object_url.strip("/").split("/")
        if len(parts) < 2:
            return Response({"error": "Invalid object URL."}, status=status.HTTP_400_BAD_REQUEST)
        ref_type = parts[-2].lower()
        ref_id = parts[-1]
        if is_integer(ref_id):
            ref_id = get_uuid_for_numeric_id(int(ref_id))
        if ref_type in ["posts", "post"]:
            post = Post.objects.filter(id=ref_id).first()
            if not post:
                return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)
            # if Like.objects.filter(user=liker.user, post=post).exists():
            if Like.objects.filter(user=remote_author.user, post=post).exists():
                like=Like.objects.filter(user=remote_author.user, post=post)
                like.delete()
                return Response({"Successfully unliked it"}, status=200)
                #return Response({"error": "You have already liked this post."}, status=status.HTTP_400_BAD_REQUEST)
            like_instance = Like.objects.create(user=remote_author.user, post=post)
            # like_instance = Like.objects.create(user=liker.user, post=post)
        elif ref_type in ["comments", "comment","commented"]:
            print("Line 998")
            comment = Comment.objects.filter(id=ref_id).first()
            if not comment:
                return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)
            # if Like.objects.filter(user=liker.user, comment=comment).exists():
            #     return Response({"error": "You have already liked this comment."}, status=status.HTTP_400_BAD_REQUEST)
            # like_instance = Like.objects.create(user=liker.user, comment=comment)
            if Like.objects.filter(user=remote_author.user, comment=comment).exists():
                like=Like.objects.filter(user=remote_author.user, comment=comment)
                like.delete()
                comment.likes.remove(remote_author.user)
                comment.like_count = comment.likes.count()
                comment.save()
                return Response({"you successful deleted the like"}, status=204)
            like_instance = Like.objects.create(user=remote_author.user, comment=comment)
            comment.likes.add(remote_author.user)
            comment.like_count = comment.likes.count()
            comment.save()
        else:
            return Response({"error": "Invalid object reference."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = LikeSerializer(like_instance, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    elif obj_type == "comment":
        """
        Process a comment received in the inbox.
        """
        comment_id = data.get("id", "").split("/")[-1]
        if is_integer(comment_id):
            comment_id = get_uuid_for_numeric_id(int(comment_id))
        # Extract remote author data
        author_data = data.get("author", {})
        remote_author_id = author_data.get("id", "").split("/")[-1]
        if is_integer(remote_author_id):
            remote_author_id= get_uuid_for_numeric_id(int(remote_author_id))
        remote_host = author_data.get("host", "")

        # Try to fetch the existing remote author
        #remote_author = Author.objects.filter(author_id=remote_author_id, host=remote_host).first()
        remote_author = RemoteAuthor.objects.filter(author_id=remote_author_id,host=remote_host).first()

        if not remote_author:
            # Create the Author if it doesn't exist
            remote_author, created = Author.objects.get_or_create(
                author_id=remote_author_id,
                host=remote_host,
                defaults={
                    "display_name": author_data.get("displayName", "Unknown Author"),
                    "github": author_data.get("github", ""),
                    "profile_image": author_data.get("profileImage", ""),
                }
            )

        if remote_author.user is None:
            username = f"remote_{remote_author_id}"  # Unique username
            
            user = User.objects.filter(username=username).first()
            if user:
                existing_author = Author.objects.filter(user=user).first()
                if existing_author:
                    remote_author = existing_author
                else:
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])
            else:
                user = User.objects.create(username=username)
                existing_author = Author.objects.filter(user=user).first()
                if existing_author:
                    remote_author = existing_author
                else:
                    remote_author.user = user
                    remote_author.save(update_fields=["user"])

        remote_author.host = remote_host
        remote_author.save()
        new_display_name = author_data.get("displayName")
        if new_display_name and remote_author.display_name != new_display_name:
            remote_author.display_name = new_display_name
            remote_author.save(update_fields=["display_name"])
        # Ensure post exists before adding the comment
        post_url = data.get("post", "")
        post_id = post_url.split("/")[-1]
        if is_integer(post_id):
            remote_author_id= get_uuid_for_numeric_id(int(post_id))
        post = Post.objects.filter(id=post_id).first()

        if not post:
            return Response({"error": "Referenced post not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the comment exists
        existing_comment = Comment.objects.filter(id=comment_id, user=remote_author.user, post=post).first()

        if existing_comment:
            # Update existing comment manually
            existing_comment.content = data.get("comment", existing_comment.content)
            existing_comment.save()
            return Response(CommentSerializer(existing_comment, context={'request': request}).data, status=status.HTTP_200_OK)

        # **Manually create the comment (without serializer)**
        new_comment = Comment.objects.create(
            id=comment_id,
            user=remote_author.user,
            post=post,
            content=data.get("comment", ""),
        )

        return Response(CommentSerializer(new_comment, context={'request': request}).data, status=status.HTTP_201_CREATED)
        # Process a comment object using CommentSerializer.
        # data = dict(request.data)
        # data.pop("type", None)  # Remove the extra "type" field if present
        # serializer = CommentSerializer(data=data, context={'request': request, 'inbox_author': author})
        # if serializer.is_valid():
        #     comment_instance = serializer.save()
        #     # Optionally, re-serialize the saved comment if we need any changes
        #     response_serializer = CommentSerializer(comment_instance, context={'request': request})
        #     return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    elif obj_type == "follow":
        # Process a follow request.
        # Extract the sender's URL from the incoming follow object.
        actor_data = data.get("actor")
        if not actor_data:
            return Response({"error": "Missing actor data in follow request."}, status=status.HTTP_400_BAD_REQUEST)
        sender_author_url = actor_data.get("id")
        if not sender_author_url:
            return Response({"error": "Missing sender author id in follow request."}, status=status.HTTP_400_BAD_REQUEST)
        sender_name = actor_data.get("displayName")

        object_data = data.get("object")
        if not object_data:
            return Response({"error": "Missing object data in follow request."}, status=status.HTTP_400_BAD_REQUEST)
        target_author_url = object_data.get("id")
        if not target_author_url:
            return Response({"error": "Missing target author id in follow request."}, status=status.HTTP_400_BAD_REQUEST)
        # Ensure that the target in the request matches the inbox owner.
        if target_author_url.rstrip("/").split("/")[-1] != str(author.author_id):
            return Response({"error": "Target author does not match inbox author."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a follow request already exists or the sender is already following.
        if RemoteFollowRequests.objects.filter(sender_name=sender_name, sender_id=sender_author_url, receiver=author.user).exists() or \
        RemoteFollower.objects.filter(follower_id=sender_author_url, followee=author.user).exists():
            return Response({"error": "Follow request already exists or sender is already following."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create the follow request.
        RemoteFollowRequests.objects.create(sender_name=sender_name, sender_id=sender_author_url, receiver=author.user)

        return Response("Follow request sent", status=status.HTTP_201_CREATED)

    return Response({"error": "Unsupported object type"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def followers(request, author_id):
    """
    GET: Return a list of followers for the author with given author_id
    """
    # get author, it's followers and then convert it into a json response
    author = get_object_or_404(Author, author_id=author_id)
    local_follows = Following.objects.filter(followee=author.user).order_by('-created_at')
    local_followers = [get_object_or_404(Author, user=follow.follower).to_dict() for follow in local_follows]

    remote_follows = RemoteFollower.objects.filter(followee=author.user).order_by('-created_at')
    remote_followers = []
    for follow in remote_follows:
        response = requests.get(follow.follower_id)
        if(response.status_code == 200):
            remote_followers.append(response.json())

    return Response({
        "type":"followers",
        "authors": local_followers + remote_followers
    })

@api_view(['DELETE', 'PUT','GET'])
@permission_classes([AllowAny])
def follower(request, author_id, follower_id):
    """
    DELETE: Remove author with folllower_id as a follower of author with author_id
    PUT: Add author with follower_id as a follower of author with author_id
    GET: Return if author with follower_id is following author with author_id
    """
    # if delete and put then ensure user is authenticated
    if request.method in ['DELETE', 'PUT'] and not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=403)

    # get follower and followee
    author = get_object_or_404(Author, author_id=author_id)
    decoded_follower_id = follower_id
    follow = RemoteFollower.objects.filter(follower_id=decoded_follower_id, followee=author.user)
        
    # handle appropriate methods
    if request.method == 'GET':

        # send follower's author object if follow exists, 404 otherwise
        if follow.exists() :
            response = requests.get(decoded_follower_id)
            if(response.status_code == 200):
                return Response(response.json(), status=200)
            else:
                return Response({"detail":"remote user not found"}, status=404)
        return Response({"detail": "Follow relationship does not exist"}, status=404)

    elif request.method == 'PUT':

        if follow.exists():
            return Response({"detail":"Follow relationship already exists"}, status=200)

        RemoteFollower.objects.create(follower_id=decoded_follower_id, followee=author.user)

        # check if a corresponding friendship relationship needs to be created
        if(RemoteFollowee.objects.filter(follower=author.user, followee_id=decoded_follower_id).exists() and not RemoteFriendship.objects.filter(local=author.user, remote=decoded_follower_id)):
            RemoteFriendship.objects.create(local=author.user, remote=decoded_follower_id)
            
        return Response({"detail":"Follow relationship created"}, status=200)

    elif request.method == 'DELETE':

        # if follow relationship exists then delete, 404 otherwise
        if follow.exists():
            follow.delete()

            # remove the corresponding friendship if it exists
            friendship = RemoteFriendship.objects.filter(local=author.user, remote=decoded_follower_id)
            if(friendship.exists()):
                friendship.delete()
                
            return Response({"detail":"Follow relationship deleted"}, status=200)
        else:
            return Response({"detail":"Follow relationship does not exist"}, status=404)

#Seems like no one use this function
# def commentLikes(likes,post):
#     paginator = LikePagination()
#     # paginated_likes = paginator.paginate_queryset(likes, request)

#     #serializer = LikeSerializer(paginated_likes, many=True)

#     #return paginator.get_paginated_response(serializer.data,post)
        
class NodeAPIView(APIView):
    """
    API View that can be accessed by authenticated nodes.
    """
    authentication_classes = [NodeBasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # The requesting node is available in request.auth
        node = request.auth
        return Response({
            "message": f"Hello {node.name}, you are authenticated!",
            "node_url": node.host_url
        })

class NodeAuthTestView(APIView):
    authentication_classes = [NodeBasicAuthentication]
    
    def get(self, request):
        return Response({
            "message": "Authentication successful",
            "node": getattr(request.auth, 'name', 'Unknown') if request.auth else "No Auth"
        })

# if not hasattr(user, "author_profile"):
#                 remote_author = Author.objects.create(
#                     user=user,
#                     author_id=remote_author_id,
#                     display_name=author_data.get("displayName", "Unknown Author"),
#                     github=author_data.get("github", ""),
#                     host=remote_host,
#                     profile_image=author_data.get("profileImage", ""),
#                 )
#             else:
#                 remote_author = user.author_profile

# if not remote_author:
#             # Ensure we get a unique username for this remote author
#             username = f"remote_{remote_author_id}"  # Unique username prefix
#             print("inside Post inbox, line 837")
#             user, created = User.objects.get_or_create(username=username)

#             # Create the Author object only if it doesn't already exist
#             remote_author, author_created = Author.objects.get_or_create(
#                 user=user,
#                 defaults={
#                     "author_id": remote_author_id,
#                     "display_name": author_data.get("displayName", "Unknown Author"),
#                     "github": author_data.get("github", ""),
#                     "host": remote_host,
#                     "profile_image": author_data.get("profileImage", ""),
#                 },
#             )

