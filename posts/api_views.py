from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from .models import Post,Like
from identity.api_views import LikePagination
from django.db import models
from identity.models import Author 
from django.contrib.auth.models import User  # Import Django User model / 导入Django用户模型（GJ）
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import AllowAny
from .permissions import IsAuthorOrAdmin
from rest_framework.response import Response
from rest_framework import status
from .serializers import PostSerializer,LikeSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def post_list(request):
    posts = Post.objects.all()
    serializer = PostSerializer(posts, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])  # Allow anyone to access the endpoint initially
def get_post_by_fqid(request, post_id):
    """
    Retrieve a public post by Fully Qualified ID (FQID).
    Friends-only posts require authentication.
    """
    # Fetch the post or return 404 if not found
    post = get_object_or_404(Post, id=post_id)

    # Handle visibility logic
    if post.visibility == "PUBLIC":
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif post.visibility == "FRIENDS":
        # Check if the user is authenticated and is a friend of the author
        if request.user.is_authenticated:
            author = post.author.author_profile  # Get the Author profile from the User
            if request.user in author.friends.all() or request.user == post.author:
                serializer = PostSerializer(post)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "You do not have permission to view this post."},
                                status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"detail": "Authentication is required to view this post."},
                            status=status.HTTP_401_UNAUTHORIZED)

    elif post.visibility == "UNLISTED":
        # Allow access if a user knows the post ID (direct link access)
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif post.visibility == "DELETED":
        # Only superusers (admins) can view deleted posts
        if request.user.is_superuser:
            serializer = PostSerializer(post)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "You do not have permission to view this post."},
                            status=status.HTTP_403_FORBIDDEN)

    # Default fallback
    return Response({"detail": "Post not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([AllowAny])
def local_post_likes(request, post_id):
    """
    GET: Return all likes for a specific post, following visibility rules.
    """
    post = get_object_or_404(Post, id=post_id)

    #if post.visibility not in ["PUBLIC", "UNLISTED"] and request.user != post.author:
    if post.visibility not in ["PUBLIC", "UNLISTED"]:
        return Response({"detail": "You do not have permission to view likes on this post."},
                        status=status.HTTP_403_FORBIDDEN)

    likes = Like.objects.filter(post=post).order_by("-created_at")  
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,post)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def like_post(request, author_id, post_id):
#     """
#     POST: Allow authenticated user to like a post.
#     """
#     author = get_object_or_404(Author, author_id=author_id)
#     post = get_object_or_404(Post, id=post_id, author=author.user)

#     if Like.objects.filter(user=request.user, post=post).exists():
#         return Response({"detail": "You have already liked this post."}, status=status.HTTP_400_BAD_REQUEST)

#     like = Like.objects.create(user=request.user, post=post)
#     serializer = LikeSerializer(like)

#     return Response(serializer.data, status=status.HTTP_201_CREATED)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def like_comment(request, author_id, post_id, comment_id):
#     """
#     POST: Allow authenticated user to like a comment.
#     """
#     author = get_object_or_404(Author, author_id=author_id)
#     comment = get_object_or_404(Comment, id=comment_id, post__id=post_id, user=author.user)

#     if Like.objects.filter(user=request.user, comment=comment).exists():
#         return Response({"detail": "You have already liked this comment."}, status=status.HTTP_400_BAD_REQUEST)

#     like = Like.objects.create(user=request.user, comment=comment)
#     serializer = LikeSerializer(like)

#     return Response(serializer.data, status=status.HTTP_201_CREATED)