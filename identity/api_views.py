from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from identity.models import Author
from posts.models import Post
from posts.serializers import PostSerializer
from django.contrib.auth.models import User

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