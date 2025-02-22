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
from .permissions import IsAuthorOrAdmin
from rest_framework.response import Response
from rest_framework import status
from .serializers import PostSerializer

@login_required
def index(request):
    """
    Display all posts created by the logged-in user.
    显示当前登录用户创建的所有帖子。（GJ）

    - Regular users see only their own posts.
      普通用户只能看到自己创建的帖子。（GJ）
    - Admin users see all posts, including deleted ones.
      管理员可以看到所有帖子，包括已删除的帖子。（GJ）
    """
    user = request.user  # Get the logged-in Django user / 获取当前登录的Django用户（GJ）

    if user.is_superuser:
        posts = Post.objects.all().order_by('-published')  # Admin can see all posts, ordered by creation date
    else:
        posts = Post.objects.filter(author=user).exclude(visibility="DELETED").order_by('-published')  # Regular users only see their posts, ordered by creation date 

    return render(request, "posts/index.html", {"posts": posts, "user": user.username})  # Pass username to the template / 传递用户名到模板（GJ）

@login_required
def view_posts(request):
    """
    Display posts visible to the logged-in user based on visibility rules.
    显示当前用户可以查看的帖子，遵循可见性规则。（GJ）

    - PUBLIC posts are visible to everyone.
      PUBLIC（公开）帖子对所有人可见。（GJ）
    - UNLISTED posts are visible via direct link.
      UNLISTED（未列出）帖子可通过直接链接访问。（GJ）
    - FRIENDS posts are visible only to friends.
      FRIENDS（仅好友可见）帖子仅对好友可见。（GJ）
    - DELETED posts are visible only to admins.
      DELETED（已删除）帖子仅管理员可见。（GJ）
    """
    user = request.user 

    if user.is_superuser:
        posts = Post.objects.all().order_by('-published') # Admin can see all posts, ordered by creation date
        return render(request, "posts/views.html", {"posts": posts, "user": user.username}) # Get the logged-in user / 获取当前用户（GJ）
    user_friends = getattr(user, 'friends', None) 
    if user_friends is None:
        friends_ids = []
    else:
        friends_ids = user.friends.all().values_list("id", flat=True)  
        
    following_ids = Post.objects.filter(author=user).values_list("author_id", flat=True).distinct()

    #posts = Post.get_visible_posts(user)  # Fetch visible posts for the user / 获取用户可见的帖子（GJ）
    posts = Post.objects.filter(
        models.Q(visibility="PUBLIC") |  # 公开帖子（GJ）
        models.Q(visibility="FRIENDS", author__id__in=friends_ids) |  # 仅好友可见帖子（GJ）
        models.Q(visibility="UNLISTED", author__id__in=following_ids) |  # 仅作者或关注者可见（GJ）
        models.Q(visibility="UNLISTED", author=user)  # 自己的 UNLISTED 也可见（GJ）
    ).exclude(visibility="DELETED").order_by('-published')  # Order by creation date

    
    return render(request, "posts/views.html", {"posts": posts, "user": user.username})  # Render the posts page / 渲染帖子页面（GJ）

@login_required
def post_detail(request, post_id):
    """
    Display a single post if the user has permission to view it.
    显示单个帖子，仅当用户有权限查看时。（GJ）

    - Checks visibility before displaying the post.
      检查可见性规则，确保用户有权限查看。（GJ）
    """
    post = get_object_or_404(Post, id=post_id)  # Retrieve post or return 404 / 获取帖子或返回404（GJ）
    print("post_id:",post_id)
    if post.visibility == "DELETED" and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to view this post.")  # Forbidden response if post is deleted / 如果帖子已删除且用户非管理员，则返回403（GJ）

    if post.visibility == "FRIENDS" and request.user != post.author and not request.user in post.author.friends.all():
        return HttpResponseForbidden("You do not have permission to view this post.")  # Prevent unauthorized friend-only access / 防止未授权用户访问仅好友可见帖子（GJ）
    return render(request, "posts/post_detail.html", {"post": post, "user": request.user.username})  # Pass user info / 传递用户信息（GJ）

@login_required
def create_post(request):
    """
    Handle post creation via form submission.
    处理用户提交表单以创建帖子。（GJ）

    - Supports PUBLIC, FRIENDS, and UNLISTED visibility.
      支持 PUBLIC（公开）、FRIENDS（仅好友可见）、UNLISTED（未列出）可见性选项。（GJ）
    """
    if request.method == "POST":
        title = request.POST.get("title", "")
        description = request.POST.get("description", "")
        content = request.POST.get("content", "")
        contentType = request.POST.get("contentType", "text/plain")
        visibility = request.POST.get("visibility", "UNLISTED")
        image = request.FILES.get("image")  # Handle uploaded image
        # Retrieve the logged-in author's profile
        print(request.user)
        # Log the uploaded image to see if it's correctly received
        print("Image received: ", image)

        post = Post.objects.create(
            author=request.user,  # Assign the logged-in user as the post author / 设定当前用户为帖子作者（GJ）
            title=title,
            description=description,
            content=content,
            contentType=contentType,
            visibility=visibility,
            image=image  # Save the image if provided
        )
        return redirect("posts:index")  # Redirect to posts index / 创建帖子后跳转到主页（GJ）
    
    return render(request, "posts/create_post.html", {"user": request.user.username})  # Render post creation page / 渲染帖子创建页面（GJ）

@login_required
def delete_post(request, post_id):
    """
    Allow users to delete their own posts. Admins can delete any post.
    允许用户删除自己的帖子，管理员可以删除任何帖子。（GJ）

    - Regular users can delete only their own posts.
      普通用户只能删除自己的帖子。（GJ）
    - Admins can delete any post.
      管理员可以删除任何帖子。（GJ）
    - Instead of deleting from DB, mark as DELETED.
      不是直接从数据库删除，而是标记为 DELETED。（GJ）
    """
    post = get_object_or_404(Post, id=post_id)
    user = request.user 

    if request.user != post.author and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to delete this post.")  # Prevent unauthorized deletion / 防止未授权删除（GJ）

    post.visibility = "DELETED"  # Change visibility to DELETED instead of removing from DB / 更改可见性为 DELETED 而非直接删除（GJ）
    post.save()
    
    return redirect("posts:index")  # Redirect back to post list / 返回帖子列表（GJ）

@login_required
def edit_post(request, post_id):
    """
    Display the edit page for a post if the user has permission.
    仅当用户有权限时，显示帖子编辑页面。（GJ）
    """
    post = get_object_or_404(Post, id=post_id)

    if request.user != post.author:
        return HttpResponseForbidden("You do not have permission to edit this post.")  # Only author can edit / 仅作者可以编辑帖子（GJ）

    return render(request, "posts/edit_post.html", {"post": post, "user": request.user.username})  # Pass user data to template / 传递用户数据到模板（GJ）

@login_required
@csrf_exempt
def update_post(request, post_id):
    """
    Handle updates to an existing post via API.
    处理通过API更新现有帖子。（GJ）
    """
    post = get_object_or_404(Post, id=post_id)

    if request.user != post.author:
        return HttpResponseForbidden("You do not have permission to update this post.")  # Only author can update / 仅作者可以更新帖子（GJ）

    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))  # Parse JSON data / 解析JSON数据（GJ）
        image = request.FILES.get("image")  # Handle uploaded image

        post.title = data.get("title", post.title)
        post.description = data.get("description", post.description)
        post.content = data.get("content", post.content)
        post.contentType = data.get("contentType", post.contentType)
        post.visibility = data.get("visibility", post.visibility)

        if image:  # Only update if a new image is uploaded
            post.image = image
        post.save()

        return JsonResponse({"message": "Post updated successfully"})  # Return success response / 返回成功响应（GJ）

    return JsonResponse({"error": "Invalid request"}, status=400)  # Return error response / 返回错误响应（GJ）

@api_view(['GET'])
def get_post_by_fqid(request, post_id):
    """
    Retrieve a public post by Fully Qualified ID (FQID).
    """
    post = get_object_or_404(Post, id=post_id)  
    serializer = PostSerializer(post)
    return Response(serializer.data, status=status.HTTP_200_OK)

@permission_classes([IsAuthorOrAdmin])  # Ensure only the author can edit
def web_update_post(request, post_id):
    """Allow an author to update their own post."""
    post = get_object_or_404(Post, id=post_id)

    # Handling Web Form Submission
    if request.method == "POST":
      title = request.POST.get("title", post.title)
      description = request.POST.get("description", post.description)
      content = request.POST.get("content", post.content)
      contentType = request.POST.get("contentType", post.contentType)
      visibility=request.POST.get("visibility",post.visibility)

      # Get the new image (if any) from the form
      image = request.FILES.get('image')

      post.title = title
      post.description = description
      post.content = content
      post.contentType = contentType
      post.visibility=visibility

      # If a new image is uploaded, update the image
      if image:
          post.image = image

      post.save()

    return redirect("posts:index")
    
    return redirect("posts:post_detail", post_id=post.id)  # return to the post detail page if form submission fails