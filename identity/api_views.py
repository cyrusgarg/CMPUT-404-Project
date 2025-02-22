from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from identity.models import Author
from posts.models import Post
from posts.serializers import PostSerializer

@api_view(['GET'])
def author_list(request):
    """Return a list of all authors"""
    authors = Author.objects.all()
    return Response([author.to_dict() for author in authors])

@api_view(['GET'])
def author_detail(request, author_id):
    """Return details of a specific author"""
    author = get_object_or_404(Author, author_id=author_id)
    return Response(author.to_dict())

@api_view(['GET'])
def author_posts(request, author_id):
    """
    Returns paginated posts of a specific author with proper visibility rules.
    """
    author = get_object_or_404(Author, author_id=author_id)

    # Define post visibility based on authentication and relationships
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

    # Fetch filtered posts based on visibility
    posts = Post.objects.filter(
        author=author, visibility__in=visibility_filter
    ).order_by("-published")

    # Apply pagination
    paginator = CustomPagination()
    paginated_posts = paginator.paginate_queryset(posts, request)

    # Serialize posts
    serializer = PostSerializer(paginated_posts, many=True)

    # Return paginated response
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
def author_post_detail(request, author_id, post_id):
    """Return details of a specific post by an author"""
    post = get_object_or_404(Post, id=post_id)
    serializer = PostSerializer(post)
    return Response(serializer.data)

class CustomPagination(PageNumberPagination):
    """
    Custom pagination response matching the required format.
    """
    page_size_query_param = 'size'  # Allows client to set page size via query parameter

    
        
    def get_paginated_response(self, data):
        return Response({
            "type": "posts",
            "page_number": self.page.number, # Current page number
            "size": self.page.paginator.per_page, # Number of items per page
            "count": self.page.paginator.count, # Total number of items across all pages
            "src": data  # Serialized list of posts
        })
