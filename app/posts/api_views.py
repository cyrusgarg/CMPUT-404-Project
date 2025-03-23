from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from .models import Post,Like
from identity.api_views import LikePagination, CommentPagination
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
from .serializers import PostSerializer,LikeSerializer, CommentSerializer
import base64, re
from django.http import HttpResponse

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

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
        serializer = PostSerializer(post,context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif post.visibility == "FRIENDS":
        # Check if the user is authenticated and is a friend of the author
        if request.user.is_authenticated:
            author = post.author.author_profile  # Get the Author profile from the User
            if request.user in author.friends.all() or request.user == post.author:
                serializer = PostSerializer(post,context={'request': request})
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "You do not have permission to view this post."},
                                status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"detail": "Authentication is required to view this post."},
                            status=status.HTTP_401_UNAUTHORIZED)

    elif post.visibility == "UNLISTED":
        # Allow access if a user knows the post ID (direct link access)
        serializer = PostSerializer(post,context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif post.visibility == "DELETED":
        # Only superusers (admins) can view deleted posts
        if request.user.is_superuser:
            serializer = PostSerializer(post,context={'request': request})
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

    likes = Like.objects.filter(post=post).exclude(user=post.author).order_by("-created_at")  
    paginator = LikePagination()
    paginated_likes = paginator.paginate_queryset(likes, request)

    serializer = LikeSerializer(paginated_likes, many=True)

    return paginator.get_paginated_response(serializer.data,post,request)

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

@api_view(['GET'])
@permission_classes([AllowAny])
def shared_post_api(request, post_id):
    """
    API endpoint for accessing shared posts.
    This endpoint doesn't require login for PUBLIC posts.
    """
    post = get_object_or_404(Post, id=post_id)
    
    if post.visibility not in ["PUBLIC", "UNLISTED"]:
        return Response(
            {"detail": "This post is not shareable"},
            status=status.HTTP_403_FORBIDDEN
        )
        
    is_logged_in = request.user.is_authenticated
    
    post_serializer = PostSerializer(post)
    post_data = post_serializer.data
    
    if is_logged_in:
        post_data['is_liked_by_user'] = post.likes.filter(id=request.user.id).exists()
    
    comments = post.comments.all()
    
    if is_logged_in:
        for comment in comments:
            comment.is_liked_by_user = comment.likes.filter(id=request.user.id).exists()
    
    from .serializers import CommentSerializer  # Import at the top of your file
    comment_serializer = CommentSerializer(comments, many=True)
    
    response_data = {
        "post": post_data,
        "comments": comment_serializer.data,
        "is_logged_in": is_logged_in
    }
    
    return Response(response_data, status=status.HTTP_200_OK)

def post_comments(request, post_id):
    """
    GET: Retrieve a paginated list of comments for the specified post.
         Visibility rules:
           - PUBLIC and UNLISTED posts are accessible to everyone.
           - FRIENDS posts require the request user to be authenticated and either the post's author 
             or in the author's friends list.
    POST: Allows an authenticated user to add a new comment to the specified post.
    """
    post = get_object_or_404(Post, id=post_id)

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

@api_view(['GET'])
@permission_classes([AllowAny])
def get_post_image(request, post_id):
    """
    Retrieve the image from a post.
    
    - If post.image contains a base64 data URL, decode and return it.
    - If post.image is an external URL, redirect to that URL.
    - Otherwise, try to extract an image URL from post.content.
      * First, attempt to parse HTML (<img src="...">) using BeautifulSoup if available.
      * Next, fall back to a regex for HTML if necessary.
      * Finally, try a regex for markdown image syntax: ![alt text](image_url)
    - If an image URL is found, redirect to it.
    - Otherwise, return a 404.
    """
    post = get_object_or_404(Post, id=post_id)
    
    # 1. Check the dedicated image field.
    if post.image:
        if post.image.startswith("data:image/"):
            try:
                header, encoded = post.image.split(',', 1)
                content_type = header.split(':')[1].split(';')[0]
                # Ensure proper padding for base64 string.
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
    
    # 2. If no dedicated image, try to extract an image URL from the content.
    img_src = None
    if post.content:
        # Try using BeautifulSoup if available.
        if BS4_AVAILABLE:
            soup = BeautifulSoup(post.content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag:
                img_src = img_tag.get('src')
        # Fallback: regex to search for an HTML <img> tag.
        if not img_src:
            match = re.search(r'<img\s+[^>]*src=["\']([^"\']+)["\']', post.content)
            if match:
                img_src = match.group(1)
        # Fallback: regex for markdown image syntax, e.g. ![alt](url)
        if not img_src:
            match_md = re.search(r'!\[.*?\]\((.*?)\)', post.content)
            if match_md:
                img_src = match_md.group(1)
    
    if img_src:
        return redirect(img_src)
    
    return Response({"detail": "Not an image"}, status=status.HTTP_404_NOT_FOUND)
