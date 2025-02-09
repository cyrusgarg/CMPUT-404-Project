from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Post, User

def index(request):
    """Homepage displaying all posts."""
    posts = Post.objects.all().order_by('-pub_date')  # Show latest posts first
    return render(request, 'posts/index.html', {'posts': posts})

def post_detail(request, post_id):
    """View a single post."""
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'posts/post_detail.html', {'post': post})

def create_post(request):
    """Create a new post (dummy logic for now)."""
    user = User.objects.first()  # Example: assign to the first user (replace with actual logic)
    if not user:
        return HttpResponse("No users exist in the database. Create a user first.", status=400)

    post = Post.objects.create(author=user, content="Sample Post Content")
    return HttpResponse(f"New post created with ID: {post.id}")

def delete_post(request, post_id):
    """Delete a post."""
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    return HttpResponse(f"Post {post_id} deleted successfully!")
