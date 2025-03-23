from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseNotAllowed
from .models import Post, Like, Comment
from identity.models import Following
from django.db import models
from identity.models import Author 
from django.contrib.auth.models import User  # Import Django User model / 导入Django用户模型（GJ）
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.decorators import api_view,permission_classes, authentication_classes
from .permissions import IsAuthorOrAdmin
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from .serializers import PostSerializer, LikeSerializer, CommentSerializer
from django.core.files.uploadedfile import InMemoryUploadedFile
from identity.models import RemoteNode
from django.http import HttpResponse, JsonResponse
import base64

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

    posts = Post.objects.filter(author=user).exclude(visibility="DELETED").order_by('-published')  # Regular users only see their posts, ordered by creation date 

    return render(request, "posts/index.html", {"posts": posts, "user": user.username})  # Pass username to the template / 传递用户名到模板（GJ）

@api_view(['GET'])
def get_post_by_fqid(request, post_id):
    """
    Retrieve a public post by Fully Qualified ID (FQID).
    """
    post = get_object_or_404(Post, id=post_id)  
    serializer = PostSerializer(post)
    return Response(serializer.data, status=status.HTTP_200_OK)

@login_required
def view_posts(request):
    """
    Display posts visible to the logged-in user based on visibility rules
    显示当前用户可以查看的帖子，遵循可见性规则（GJ）

    - PUBLIC posts are visible to everyone
      PUBLIC（公开）帖子对所有人可见（GJ）
    - UNLISTED posts are visible via direct link
      UNLISTED（未列出）帖子可通过直接链接访问（GJ）
    - FRIENDS posts are visible only to friends
      FRIENDS（仅好友可见）帖子仅对好友可见（GJ）
    - DELETED posts are visible only to admins
      DELETED（已删除）帖子仅管理员可见（GJ）
    """
    user = request.user 

    host = request.get_host()
    #print(f"Request from: {full_host_url}") 
    remote_node = RemoteNode.objects.filter(host_url__icontains=host).first()

    if user.is_superuser:
        posts = Post.objects.all().order_by('-published') # Admin can see all posts, ordered by creation date
        return render(request, "posts/views.html", {"posts": posts, "user": user.username}) # Get the logged-in user / 获取当前用户（GJ）

    if remote_node and not remote_node.is_active:
        print("1")
        posts = Post.objects.filter(author=user).exclude(visibility="DELETED").order_by('-published')
        return render(request, "posts/views.html", {"posts": posts, "user": user.username})
    # Get the followers of the current user / 获取当前用户的关注者（即用户关注的对象）（GJ）
    following_ids = Following.objects.filter(follower=user).values_list("followee_id", flat=True)  

    # Get users who follow the current user / 获取关注当前用户的用户（即谁关注了我）（GJ）
    followers_ids = Following.objects.filter(followee=user).values_list("follower_id", flat=True)  

    # Users who follow each other are friends/ 互相关注的用户即为好友（friends）（GJ）
    mutual_friends_ids = set(following_ids).intersection(set(followers_ids))

    #posts = Post.get_visible_posts(user)  # Fetch visible posts for the user / 获取用户可见的帖子（GJ）
    posts = Post.objects.filter(
        models.Q(visibility="PUBLIC") |  # public post / 公开帖子（GJ）
        models.Q(visibility="FRIENDS", author__id__in=mutual_friends_ids) |  # friend-only post / 仅好友可见帖子（GJ）
        models.Q(visibility="UNLISTED", author__id__in=following_ids) |  # unlist post / 仅作者或关注者可见（GJ）
        models.Q(visibility="FRIENDS", author=user) | # author can see his friends-only post / 自己的 FRIENDS 也可见（GJ）
        models.Q(visibility="UNLISTED", author=user)  # author can see his unlisted posts / 自己的 UNLISTED 也可见（GJ）
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
    user = request.user

   # Get the followers of the current user / 获取当前用户的关注者（即用户关注的对象）（GJ）
    following_ids = Following.objects.filter(follower=user).values_list("followee_id", flat=True)  

    # Get users who follow the current user / 获取关注当前用户的用户（即谁关注了我）（GJ）
    followers_ids = Following.objects.filter(followee=user).values_list("follower_id", flat=True)  

    # Users who follow each other are friends/ 互相关注的用户即为好友（friends）（GJ）
    mutual_friends_ids = set(following_ids).intersection(set(followers_ids))

    post.is_liked_by_user = post.likes.filter(id=user.id).exists()
    # Re-fetch comments and set liked status for each one
    comments = list(post.comments.all())
    for comment in comments:
        # Ensure we have the latest state from the DB
        comment.refresh_from_db()
        comment.is_liked_by_user = comment.likes.filter(id=user.id).exists()

    if post.visibility == "DELETED" and not user.is_superuser:
        return HttpResponseForbidden("You do not have permission to view this post.")  # Forbidden response if post is deleted / 如果帖子已删除且用户非管理员，则返回403（GJ）

    if post.visibility == "FRIENDS" and user != post.author and post.author.id not in mutual_friends_ids:
        return HttpResponseForbidden("You do not have permission to view this post.")  # Prevent unauthorized friend-only access / 防止未授权用户访问仅好友可见帖子（GJ）
        
    return render(request, "posts/post_detail.html", {"post": post, "user": request.user.username, "comments": comments}) 

def image_to_base64(image_file):
  """
  Converts an image file to a base64 encoded string.
  """
  if isinstance(image_file, InMemoryUploadedFile):
      image_data = image_file.read()  # Read image content
      file_type = image_file.content_type.split('/')[1]  # Get file type (png, jpeg)
      base64_data = base64.b64encode(image_data).decode('utf-8')  # Encode as base64
      return f"data:image/{file_type};base64,{base64_data}"
  return None

def upload_image(request):
  """
  Converts the uploaded image to base64 before saving it in the Post model.
  """
  if request.method == 'POST' and request.FILES['image']:
      image_file = request.FILES['image']
      base64_image = image_to_base64(image_file)  # Convert to base64
      if base64_image:
          post = Post.objects.create(
              title=request.POST['title'],
              content=request.POST['content'],
              description=request.POST['description'],
              image=base64_image,  # Save the base64 image string
              author=request.user
          )
          return redirect('posts:post_detail', post_id=post.id)
  return render(request, "posts/upload_image.html")

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

        # Convert image to base64 if an image is provided; otherwise, set to an empty string.
        base64_image = image_to_base64(image) if image else ""

        post = Post.objects.create(
            author=request.user, 
            title=title,
            description=description,
            content=content,
            contentType=contentType,
            visibility=visibility,
            image=base64_image,
        )
        #send_post_to_remote_followers(post)
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
    Needs to verify where this function gets used
    Handle updates to an existing post via API.
    处理通过API更新现有帖子。（GJ）
    """
    post = get_object_or_404(Post, id=post_id)

    if request.user != post.author and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to update this post.")  # Only author can update / 仅作者可以更新帖子（GJ）

    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))  # Parse JSON data / 解析JSON数据（GJ）
        post.title = data.get("title", post.title)
        post.description = data.get("description", post.description)
        post.content = data.get("content", post.content)
        post.contentType = data.get("contentType", post.contentType)
        post.visibility = data.get("visibility", post.visibility)

        # If an image is uploaded via multipart/form-data, convert it to base64.
        image = request.FILES.get("image")

        if image:  # Only update if a new image is uploaded
            post.image = image_to_base64(image)
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
    if request.user != post.author and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to update this post.")
    
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
          post.image = image_to_base64(image)

      post.save()
      return redirect("posts:post_detail", post_id=post.id)
    
    # return to the post edit if form submission fails
    return render(request, "posts/edit_post.html", {"post": post, "user": request.user.username})

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Check if the user already liked the post
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    
    if not created:
        like.delete()   # If the user already liked, remove the like

    # Dynamically calculate the like count:
    like_count = Like.objects.filter(post=post).count()

    return redirect('posts:post_detail', post_id=post.id)  # Redirect back to post detail

@login_required
def post_likes(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    likes = Like.objects.filter(post=post)
    return render(request, "posts/likes_list.html", {"post": post, "likes": likes})

@login_required
def add_comment(request, post_id):
    if request.method == "POST":
        post = Post.objects.get(id=post_id)
        content = request.POST.get("content")
        if not content:
            return JsonResponse({"error": "Content cannot be empty"}, status=400)

        comment = Comment.objects.create(
            post=post, 
            user=request.user,  # Ensure user is authenticated
            content=content
        )
        return JsonResponse({
            "message": "Comment added successfully",
            "comment": {
                "id": comment.id,
                "content": comment.content,
                "author": comment.user.username,
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    return JsonResponse({"error": "Invalid request"}, status=400)

@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_comments(request, post_id):
    """
    Retrieve comments for a post. For friends-only posts, only return comments 
    if the request user is a friend of the post's author or if the comment was 
    written by the request user.
    """
    post = get_object_or_404(Post, id=post_id)
    
    # If the post is friends-only, filter comments.
    if post.visibility == "FRIENDS":
        comments = Comment.objects.filter(
            post=post
        ).filter(
            models.Q(user=request.user) | models.Q(user__in=post.author.friends.all())
        ).order_by("-created_at")
    else:
        comments = Comment.objects.filter(post=post).order_by("-created_at")
    
    serializer = CommentSerializer(comments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@login_required
def like_comment(request, post_id, comment_id):
    # Retrieve the comment using the comment_id from the URL
    comment = get_object_or_404(Comment, id=comment_id)
    post = get_object_or_404(Post, id=post_id)
    user = request.user

    like, created = Like.objects.get_or_create(user=user, comment=comment)

    if not created:
        # If the like already exists, remove it (unlike)
        like.delete()
        comment.likes.remove(user)
        liked = False
    else:
        comment.likes.add(user)
        liked = True

    # Update the like count
    like_count = Like.objects.filter(comment=comment).count()
    comment.like_count = comment.likes.count()
    comment.save()
    
    return JsonResponse({
        "like_count": comment.like_count,
        "liked": liked
    })

def shared_post_view(request, post_id):
    """
    Public view for accessing shared posts.
    This view doesn't require login for PUBLIC or UNLISTED posts.
    """
    post = get_object_or_404(Post, id=post_id)
    
    # Only allow viewing of PUBLIC or UNLISTED posts through this route
    if post.visibility not in ["PUBLIC", "UNLISTED"]:
        return render(request, 'posts/error.html', {'message': 'This post is not shareable'}, status=403)
    
    # Check if user is logged in
    is_logged_in = request.user.is_authenticated
    is_liked = False
    
    # If user is logged in, check if they liked the post
    if is_logged_in:
        is_liked = post.likes.filter(id=request.user.id).exists()
    
    # Get comments for the post
    comments = post.comments.all()
    
    # For logged in users, set liked status for each comment
    if is_logged_in:
        for comment in comments:
            comment.is_liked_by_user = comment.likes.filter(id=request.user.id).exists()
    
    return render(request, "posts/shared_post.html", {
        "post": post,
        "comments": comments,
        "is_logged_in": is_logged_in,
        "is_liked": is_liked
    })

def send_post_to_remote_followers(post):
    """
    Sends a newly created PUBLIC post to all remote followers of the author.
    """
    if post.visibility != "PUBLIC":
        print(f"Skipping post {post.id} because it is not public.")
        return

    # Get remote followers
    # remote_followers = Following.objects.filter(
    #     followee_id=f"{post.author.author_profile.id}",
    #     follower_host__isnull=False  # Ensure it's a remote follower
    # )

    # Prepare post data
    post_data = {
        "type": "post",
        "id": f"{post.id}", #this is important to distinguish between current post or new post
        "title": post.title,
        "description": post.description,
        "contentType": post.contentType,
        "content": post.content,
        "visibility": post.visibility,
        
    }

    # for follower in remote_followers:
    #     inbox_url = f"{follower.follower_host}/api/authors/{follower_id}/inbox"

    inbox_url = f"http://10.2.6.207:8000//api/authors/c37307f0-a9ae-44fb-afd7-8d4194b35994/inbox"
    try:
        response = requests.post(
            inbox_url,
            json=post_data,
            headers={"Content-Type": "application/json"},
            auth=("your-username", "your-password")    # Replace with real authentication
        )

        if response.status_code in [200, 201]:
            print(f"Post sent successfully to {follower.follower_id}")
            #logger.info(f" Post sent successfully to {follower.follower_id}")
        else:
            print(f"Failed to send post to {follower.follower_id}: {response.status_code}")
            #logger.error(f" Failed to send post to {follower.follower_id}: {response.status_code}")

    except requests.RequestException as e:
        print(f"Error sending post to {follower.follower_id}: {e}")
        #logger.error(f"Error sending post to {follower.follower_id}: {e}")