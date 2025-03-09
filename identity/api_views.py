from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from identity.models import Author
from posts.models import Post,Comment,Like
from posts.serializers import PostSerializer, CommentSerializer,LikeSerializer
from django.contrib.auth.models import User
from identity.models import Following
import json

@api_view(['GET'])
@permission_classes([AllowAny])
def author_list(request):
    """Return a list of all authors"""
    authors = Author.objects.all()
    return Response([author.to_dict() for author in authors])

@api_view(['GET'])
def author_detail(request, author_id):
    """Return details of a specific author"""
    author = get_object_or_404(Author, author_id=author_id)
    return Response(author.to_dict())

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # Allow any user to access, then control with logic
def author_posts(request, author_id):
    """
    GET: Returns paginated posts of a specific author with proper visibility rules.
    POST: Allows the author to create a new post.
    """

    # Retrieve author and their linked user
    author = get_object_or_404(Author, author_id=author_id)
    user = author.user

    if request.method == 'GET':
        # Visibility filters based on authentication and relationships
        if not request.user.is_authenticated:
            visibility_filter = ["PUBLIC"]
        elif request.user == author.user:  # Author of the posts
            visibility_filter = ["PUBLIC", "FRIENDS", "UNLISTED"]
        elif request.user in author.friends.all():  # Friend
            visibility_filter = ["PUBLIC", "FRIENDS", "UNLISTED"]
        elif request.user in author.followers.all():  # Follower
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
        serializer = PostSerializer(paginated_posts, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)

    elif request.method == 'POST':
        # Only allow authenticated authors to create posts
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication is required to create a post."},
                            status=status.HTTP_401_UNAUTHORIZED)

        if request.user != author.user:
            return Response({"detail": "You are not authorized to create posts for this author."},
                            status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the post data
        serializer = PostSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(author=request.user)  # Save post with author set
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Custom Pagination class
class CustomPagination(PageNumberPagination):
    """
    Custom pagination response matching the required format.
    """
    page_size_query_param = 'size'  # Allows client to set page size via query parameter

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
            serializer = PostSerializer(post)
            return Response(serializer.data)

        elif post.visibility == "FRIENDS":
            if request.user.is_authenticated and (
                request.user == user or request.user in author.friends.all()
            ):
                serializer = PostSerializer(post)
                return Response(serializer.data)
            return Response({"detail": "Authentication required for friends-only posts."},
                            status=status.HTTP_403_FORBIDDEN)

        elif post.visibility == "UNLISTED":
            # Allow direct access without restrictions
            serializer = PostSerializer(post)
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
    page_size_query_param = 'size'

    def get_paginated_response(self, data,post):
        """Returns paginated response with additional `page` and `id` fields."""
        post_author = post.author.author_profile
        return Response({
            "type": "comments",
            "page": f"{post_author.host}/authors/{post_author.author_id}/posts/{post.id}",
            "id": f"{post_author.host}/api/authors/{post_author.author_id}/posts/{post.id}/comments",
            "page_number": self.page.number,
            "size": self.page.paginator.per_page,
            "count": self.page.paginator.count,
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
        serializer = CommentSerializer(paginated_comments, many=True)
        post = filtered_comments[0].post
        return paginator.get_paginated_response(serializer.data,post)

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

        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_comment(request, author_id, comment_id):
    """
    GET: Retrieve a specific comment made by an author.
    """
    author = get_object_or_404(Author, author_id=author_id)
    user = author.user  # Convert Author to User
    comment = get_object_or_404(Comment, id=comment_id, user=user)

    serializer = CommentSerializer(comment)
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
    likes = [like.author_profile.to_dict() for like in comment.likes.all()]

    return Response({
        "type": "likes",
        "id": f"{comment.get_like_url()}",
        "page": f"{comment.get_absolute_url()}/likes",
        "page_number": 1,
        "size": 50,
        "count": comment.likes.count(),
        "src": likes,
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def get_comment_by_id(request, comment_id):
    """
    GET: Retrieve a comment by its global ID.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    serializer = CommentSerializer(comment)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def inbox_like(request, author_id):
    """
    POST: Accepts a remote like object and processes it.
    """
    author = get_object_or_404(Author, author_id=author_id)
    data = request.data

    if data.get("type") != "like":
        return Response({"error": "Invalid object type."}, status=status.HTTP_400_BAD_REQUEST)

    # Extract author details
    liker_author_url = data["author"]["id"]
    liker = Author.objects.filter(author_id=liker_author_url.split("/")[-1]).first()

    if not liker:
        return Response({"error": "Liker author not found."}, status=status.HTTP_400_BAD_REQUEST)

    # Determine if this is a post or comment like
    object_url = data.get("object")
    #TODO: need to put the constraint that same user will not send the like what he already liked
    if(object_url.split("/")[-2]=="posts"):
        post = Post.objects.filter(id=object_url.split("/")[-1]).first()
        Like.objects.create(user=liker.user, post=post)
    elif(object_url.split("/")[-2]=="commented"):
        comment = Comment.objects.filter(id=object_url.split("/")[-1]).first()
        Like.objects.create(user=liker.user, comment=comment)
    else:
        return Response({"error": "Invalid object reference."}, status=status.HTTP_400_BAD_REQUEST)

    # if post:
        
    # elif comment:
    return Response({"message": "Like received successfully."}, status=status.HTTP_201_CREATED)

class LikePagination(PageNumberPagination):
    """
    Custom pagination for Likes.
    Ensures proper structure with page number, size, and count.
    """
    page_size_query_param = "size"  # Allow dynamic page size via query parameters
    page_size = 5  # Default page size
    max_page_size = 50  # Limit max likes per request

    def get_paginated_response(self, data,post):
        """
        Returns a paginated response structured as per the spec.
        """
        post_author = post.author.author_profile
        return Response({
            "type": "likes",
            "page": f"{post_author.host}/authors/{post_author.author_id}/posts/{post.id}",
            "id": f"{post_author.host}/api/authors/{post_author.author_id}/posts/{post.id}/likes",
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

    #if post.visibility not in ["PUBLIC", "UNLISTED"] and request.user != post.author:
    if post.visibility not in ["PUBLIC", "UNLISTED"]:
        return Response({"detail": "You do not have permission to view likes on this post."},
                        status=status.HTTP_403_FORBIDDEN)

    likes = Like.objects.filter(post=post).order_by("-created_at")  
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,post)

@api_view(['GET'])
@permission_classes([AllowAny])
def comment_likes(request, author_id, post_id, comment_id):
    """
    GET: Return all likes for a specific comment.
    """
    author = get_object_or_404(Author, author_id=author_id)
    post = get_object_or_404(Post, id=post_id, author=author.user)
    comment = get_object_or_404(Comment, id=comment_id, post__id=post_id, user=author.user)

    likes = Like.objects.filter(comment=comment).order_by("-created_at")
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,post)