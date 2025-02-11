from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse,JsonResponse
from .models import Post, User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import PostSerializer
import json, uuid

def index(request):
    """Homepage displaying all posts."""
    posts = Post.objects.all().order_by('-published')  # Show latest posts first
    return render(request, 'posts/index.html', {'posts': posts})

def post_detail(request, post_id):
    """View a single post."""
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'posts/post_detail.html', {'post': post})

def create_post(request):
    """Create a new post (supports both web form & API)."""
    if request.method == 'POST':
        title = request.POST.get('title', 'Untitled Post')
        description = request.POST.get('description', '')
        content = request.POST.get('content', '')
        contentType = request.POST.get('contentType', 'text/plain')
        visibility=request.POST.get('visibility','PUBLIC') #Default visibility

        if visibility not in ["PUBLIC", "FRIENDS", "UNLISTED"]:
            return HttpResponse("Invalid visibility option", status=400)

        user = User.objects.first()  # Assign to first user (change logic for actual users)
        if not user:
            return HttpResponse("No users exist in the database. Create a user first.", status=400)

        post = Post.objects.create(
            id=uuid.uuid4(),
            author=user,
            title=title,
            description=description,
            content=content,
            contentType=contentType,
            visibility=visibility
        )
        
        return redirect('posts:index')

    return HttpResponse("Invalid request", status=400)

def delete_post(request, post_id):
    """Delete a post."""
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    return redirect('posts:index')
    #return HttpResponse(f"Post {post_id} deleted successfully!")

@api_view(['GET'])
def get_post_by_fqid(request, post_id):
    """
    Retrieve a public post by Fully Qualified ID (FQID).
    """
    post = get_object_or_404(Post, id=post_id)  
    serializer = PostSerializer(post)
    return Response(serializer.data, status=status.HTTP_200_OK)