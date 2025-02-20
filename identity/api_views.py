from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Author
from posts.models import Post
from posts.serializers import PostSerializer
from uuid import UUID
from django.http import JsonResponse

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
    """Return all posts by a specific author"""
    author = get_object_or_404(Author, author_id=author_id)
    posts = Post.objects.filter(author=author, visibility='PUBLIC')
    return Response([post.to_dict() for post in posts])

@api_view(['GET'])
def author_post_detail(request, author_id, post_id):
    """Return details of a specific post by an author"""
    post = get_object_or_404(Post, id=post_id)
    serializer = PostSerializer(post)
    return Response(serializer.data)