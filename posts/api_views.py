from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from .models import Post
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
from .serializers import PostSerializer


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
