from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseNotAllowed
from .models import Post, Like, Comment
from identity.models import Following, Friendship
from django.db import models
from identity.models import Author , RemoteFollower, RemoteFriendship
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
import base64, requests,socket
from identity.models import RemoteNode
from django.http import HttpResponse, JsonResponse
import base64
from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth
from datetime import datetime
import re

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
        posts = Post.objects.filter(author=user).exclude(visibility="DELETED").order_by('-published')
        #print(f"123") 
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

    host = request.get_host()
    #print(f"Request from: {full_host_url}") 
    remote_node = RemoteNode.objects.filter(host_url__icontains=host).first()

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

    if post.visibility == "DELETED" and not user.is_superuser or remote_node and post.visibility == "DELETED" and not user.is_superuser:
        return HttpResponseForbidden("You do not have permission to view this post.")  # Forbidden response if post is deleted / 如果帖子已删除且用户非管理员，则返回403（GJ）

    if post.visibility == "FRIENDS" and user != post.author and post.author.id not in mutual_friends_ids and not user.is_superuser and not remote_node:
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
        print("author host :",request.user.author_profile.host)
        send_post_to_remote_recipients(post,request,False)
        #send_post_to_remote(post,request,False)
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

    send_post_to_remote_recipients(post,request,True)
    
    send_post_to_remote_recipients(post, request, is_update=True)

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
      send_post_to_remote_recipients(post,request,True)
      #send_post_to_remote(post,request,True)
      return redirect("posts:post_detail", post_id=post.id)
    
    # return to the post edit if form submission fails
    return render(request, "posts/edit_post.html", {"post": post, "user": request.user.username})

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def like_post(request, post_id):
    """
    post = get_object_or_404(Post, id=post_id)

    # Check if the user already liked the post
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    
    if not created:
        like.delete()   # If the user already liked, remove the like

    # Dynamically calculate the like count:
    like_count = Like.objects.filter(post=post).count()

    return redirect('posts:post_detail', post_id=post.id)  # Redirect back to post detail
    """
    post = get_object_or_404(Post, id=post_id)

    # Check if the user already liked the post
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    is_remote_author = post.author.username.startswith("remote_")

    if created and is_remote_author:
        
        send_like_to_remote_recipients(like, request, is_update=False)
    elif not created and is_remote_author:
        # If unliking a remote author's post
        send_like_to_remote_recipients(like, request, is_update=False)
        like.delete()   # If the user already liked, remove the like
    elif not created:
        # Just delete the like for local posts
        like.delete()
        
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
        send_comment_to_remote_recipients(comment, request, is_update=False)
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
        send_Comment_like_to_remote_recipients(like,request,is_update=False)
        like.delete()
        comment.likes.remove(user)
        liked = False
    else:
        comment.likes.add(user)
        send_Comment_like_to_remote_recipients(like,request,is_update=False)
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

def send_post_to_remote_recipients(post, request,is_update=False):
    """
    Sends a post (new or updated) to the appropriate remote recipients.
    
    - PUBLIC posts → Remote followers + friends
    - FRIENDS posts → Only remote mutual friends
    - Includes image as base64 if available
    """
    author = post.author.author_profile
    # we change this for indigo
    published = str(datetime.now()) 
    original_post_url = f"{author.host}authors/{post.author.id}/posts/{post.id}"
    #end
    # Prepare post data
    post_data = {
        "type": "post",
        "id": original_post_url, # also this lin indigo
        "author":author.to_dict(request),
        "title": post.title,
        "description": post.description,
        "contentType": post.contentType,
        "content": post.content,
        "visibility": post.visibility,
        "image": post.image if post.image else None,  # Include image if available
        "published": published # also this line ingigo
    }

    recipients = set()

    if post.visibility == "PUBLIC" or post.visibility == "DELETED":
         # Add remote followers
         # Get remote followers from RemoteFollower model
        remote_followers = RemoteFollower.objects.all()
        for remote_follower in remote_followers:
            #print("Line 489")
            parsed_url = urlparse(remote_follower.follower_id)
            base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
            author_id = parsed_url.path.strip("/").split("/")[-1]
            #print("baseHost:",base_host,"author_id:",author_id)
            inbox_url = f"{base_host}/api/authors/{author_id}/inbox"
            print("inbox url:",inbox_url)
            recipients.add(inbox_url)

    elif post.visibility == "FRIENDS":
        # Send only to mutual friends

        remote_friends = RemoteFriendship.objects.filter(local=author.user)
        for remote_friend in remote_friends:
            parsed_url = urlparse(remote_friend.remote)
            base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
            author_id = parsed_url.path.strip("/").split("/")[-1]
            inbox_url = f"{base_host}/api/authors/{author_id}/inbox"
            print("inbox url:",inbox_url)
            recipients.add(inbox_url)

    elif post.visibility == "DELETED":
         # Add remote followers
         # Get remote followers from RemoteFollower model
        remote_followers = RemoteFollower.objects.all()
        for remote_follower in remote_followers:
            #print("delete")
            parsed_url = urlparse(remote_follower.follower_id)
            base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
            author_id = parsed_url.path.strip("/").split("/")[-1]
            #print("baseHost:",base_host,"author_id:",author_id)
            inbox_url = f"{base_host}/api/authors/{author_id}/inbox"
            recipients.add(inbox_url)
          
    # # Convert image to base64 if it exists
    # if post.image and not post.image.startswith("data:image"):
    #     try:
    #         with open(post.image.path, "rb") as img_file:
    #             encoded_image = base64.b64encode(img_file.read()).decode("utf-8")
    #             post_data["image"] = f"data:image/jpeg;base64,{encoded_image}"  # Assuming JPEG
    #     except Exception as e:
    #         print(f"Error encoding image: {e}")
    
    # Send post to all recipients
    for inbox_url in recipients:
        print(f"Sending post to {inbox_url}")
        print("thisis postdata", post_data)
        auth = HTTPBasicAuth("indigo-node1", "node1-pass")

        try:
            response = requests.post(
                inbox_url,
                auth = auth,
                json=post_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code in [200, 201]:
                print(f"Post sent successfully to {inbox_url}")
            else:
                print(f"Failed to send post to {inbox_url}: {response.status_code}, {response.text}")

        except requests.RequestException as e:
            print(f" Error sending post to {inbox_url}: {e}")

#just for testing
def send_post_to_remote(post, request,is_update=False):
    """
    Sends a post (new or updated) to the appropriate remote recipients.
    
    - PUBLIC posts → Remote followers + friends
    - FRIENDS posts → Only remote mutual friends
    - Includes image as base64 if available
    """
    author = post.author.author_profile
    # Get remote followers
    # remote_followers = Following.objects.filter(
    #     followee_id=f"{post.author.author_profile.id}",
    #     follower_host__isnull=False  # Ensure it's a remote follower
    # )
    post_data = {
        "type": "post",
        "id": f"{post.id}",
        "author":author.to_dict(request),
        "title": post.title,
        "description": post.description,
        "contentType": post.contentType,
        "content": post.content,
        "visibility": post.visibility,
        "image": post.image if post.image else None,  # Include image if available
    }
    # post_data={"type": "post",}
    #inbox_url = f"http://10.2.6.207:8000/api/authors/3ccf030e-68f0-4de1-a135-a072e1c4902c/inbox"
    #inbox_url = f"http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]/api/authors/19290a3a-5ab8-4044-8834-d8dc497f08c5/inbox"
    #inbox_url = f"http://[2605:fd00:4:1001:f816:3eff:fe56:c195]/api/authors/f5b24430-e8e6-4e09-bd49-f4574d72b85c/inbox"
    #inbox_url = f"http://[2605:fd00:4:1001:f816:3eff:feb6:bbc]/api/authors/a3354abf-375d-4039-b712-3da6c1225366/inbox"
    inbox_url = f"http://[2605:fd00:4:1001:f816:3eff:fe1a:a199]/api/authors/80fe48df-2868-46aa-82ed-70d30f8e7a89/inbox"
    
    print("Sending post data:", json.dumps(post_data, indent=4))
    method='POST'
    try:
        response = requests.post(
            inbox_url,
            json=post_data,
            headers={"Content-Type": "application/json"},
            #auth=("nodeTesting", "Smriti21!")  # Replace with real authentication
        )

        if response.status_code in [200, 201]:
            print(f"Post sent successfully")
            #print(f"Post sent successfully to {recipient.author_id}")
        else:
            print(f"Failed to send post")
            #print(f"Failed to send post to {recipient.author_id}: {response.status_code}, {response.text}")

    except requests.RequestException as e:
        print(f"Error sending post {e}")
        #print(f"Error sending post to {recipient.author_id}: {e}")



def send_like_to_remote_recipients(like, request, is_update=False):
    """
    Sends a like object to the remote recipient (the author of the liked post).
    Uses `LikeSerializer` to format the data properly.
    """
    post = like.post
    post_author = post.author.author_profile  # Author of the post being liked
    
    if post_author.host != f"http://{request.get_host()}":
        remote_url = post.remote_url if hasattr(post, 'remote_url') and post.remote_url else None
    
        if not remote_url:
            print("Error: No remote_url found for this post. Cannot send like.")
            return
        parsed_url = urlparse(remote_url)
        base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Extract the path components
        path_parts = parsed_url.path.strip("/").split("/")
        
        # Find the author ID in the path
        # For a URL like 'http://3611d.yeg.rac.sh/service/api/authors/1/posts/2'
        # We need to identify the author ID (1 in this case)
        author_index = -1
        for i, part in enumerate(path_parts):
            if part == "authors" and i+1 < len(path_parts):
                author_index = i+1
                break
        
        if author_index == -1:
            print(f"Error: Could not find author ID in URL: {remote_url}")
            return
            
        remote_author_id = path_parts[author_index]
        
        # Construct the inbox URL using the same base structure
        # For most nodes, the inbox is at /api/authors/{id}/inbox
        service_path = ""
        if "service" in path_parts:
            service_path = "service/"
            
        inbox_url = f"{base_host}/{service_path}api/authors/{remote_author_id}/inbox"
        print(f"Constructed inbox URL: {inbox_url}")
        # Retrieve the corresponding RemoteNode for authentication
        #remote_node = RemoteNode.objects.filter(host_url__icontains=post_author.host).first()
        remote_node = RemoteNode.objects.filter(host_url__icontains=base_host).first()
        print("Remote node:",remote_node.username, remote_node.password)
        if not remote_node:
            print(f"Warning: Remote node not found for {base_host}. Skipping authentication.")
            auth = None  # No authentication
        
        # Use the post's stored remote_url if available
        original_post_url = post.remote_url if post.remote_url else None
        # If we don't have a stored URL, construct one (but this might not be reliable)
        if not original_post_url:
            post_id = post.id
            if is_uuid(post_id):
                post_id = get_numeric_id_for_author(post_id)
            original_post_url = f"{post_author.host}authors/{author_id}/posts/{post_id}"
        local_author = request.user.author_profile
        like_id = f"http://{request.get_host()}/api/authors/{local_author.author_id}/liked/{like.id}"
        # Create like data with the correct post reference
        like_data = {
            "type": "like",
            "summary": f"{request.user.author_profile.display_name} likes your post",
            "author": request.user.author_profile.to_dict(),
            "id":like_id,
            "published": like.created_at.isoformat() if hasattr(like, 'created_at') else timezone.now().isoformat(),
            # Use the original post URL instead of your local URL format
            "object": original_post_url
        }
        print("like data:\n",like_data)
        node_username = remote_node.username
        node_password = remote_node.password
        try:
            response = requests.post(
                inbox_url,
                json=like_data,
                headers={"Content-Type": "application/json"},
                auth=HTTPBasicAuth(node_username, node_password)  # Use Basic Auth
            )

            if response.status_code in [200, 201]:
                print(f"Like sent successfully to {post_author.author_id}")
            else:
                print(f"Failed to send like to {post_author.author_id}: {response.status_code}, {response.text}")

        except requests.RequestException as e:
            print(f"Error sending like to {post_author.author_id}: {e}")


def send_Comment_like_to_remote_recipients(like, request, is_update=False):
    """
    Sends a like object to the remote recipient (the author of the liked post).
    Uses `LikeSerializer` to format the data properly.
    """
    comment = like.comment
    post=comment.post
    post_author = comment.post.author.author_profile  # Author of the post being liked
    #post_author = comment.post.author.remote_author
    #post_author_dict=post.author.author_profile.to_dict()
    # print("Inside post view,printing post username",post.author.username)
    # print("Inside post view,printing post author host",post.author.author_profile.host)
    # print("Inside post view,printing post author display name",post.author.author_profile.display_name)
    # print("post_author dict:\n",post_author_dict)
    # print("post_author.host:",post_author.host,"\nhttp://{request.get_host()}:",f"http://{request.get_host()}")
    # Check if the post author is remote (only send if they are on a different node)
    if post_author.host != f"http://{request.get_host()}":
        author_id=post_author.user.username.split("_")[-1]
        inbox_url = f"{post_author.host}authors/{author_id}/inbox"
        print("inbox url:",inbox_url)
        #remote_node = RemoteNode.objects.filter(host_url__icontains=post_author.host).first()
        parsed_url = urlparse(inbox_url)
        base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        remote_node = RemoteNode.objects.filter(host_url__icontains=base_host).first()
        print("Remote node:",remote_node.username, remote_node.password)
        if not remote_node:
            print(f"Remote node not found for host: {post_author.host}")
            return

        # Extract authentication credentials
        node_username = remote_node.username
        node_password = remote_node.password
        # Serialize the like object
        local_author = request.user.author_profile
        
        # Create a proper like ID in the format they expect
        
        original_post_url = post.remote_url if post.remote_url else None
        parsed_url=urlparse(original_post_url)
        base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        like_id = f"{base_host}/api/authors/{local_author.author_id}/liked/{like.id}"
        match = re.match(r"(http://.*?/api/authors/[\w-]+/)", original_post_url)
        if match:
            extracted_url = match.group(1)
            print(extracted_url)
        # Create the full like data manually instead of using serializer
        like_data = {
            "type": "like",
            "author": local_author.to_dict(),  # This should include all required author fields
            "published": like.created_at.isoformat() if hasattr(like, 'created_at') else timezone.now().isoformat(),
            "id": like_id,
            "object": f"{extracted_url}commented/{comment.id}"
        }
        print("Comment like data:", like_data)
        try:
            response = requests.post(
                inbox_url,
                json=like_data,
                headers={"Content-Type": "application/json"},
                auth=HTTPBasicAuth(node_username, node_password)  # Use Basic Auth
            )

            if response.status_code in [200, 201]:
                print(f"Like sent successfully to {author_id}")
            else:
                print(f"Failed to send like to {author_id}: {response.status_code}, {response.text}")

        except requests.RequestException as e:
            print(f"Error sending like to {author_id}: {e}")

def send_comment_to_remote_recipients(comment, request, is_update=False):
    """
    Sends a comment object to the remote recipient (the author of the post being commented on).
    Uses `CommentSerializer` to format the data properly.
    """
    post = comment.post
    post_author = post.author.author_profile  # Author of the post being commented on
    
    if post_author.host != f"http://{request.get_host()}":
        # Check for remote_url, similar to the like function
        remote_url = post.remote_url if hasattr(post, 'remote_url') and post.remote_url else None
    
        if not remote_url:
            print("Error: No remote_url found for this post. Cannot send comment.")
            return
        
        parsed_url = urlparse(remote_url)
        base_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Extract the path components
        path_parts = parsed_url.path.strip("/").split("/")
        
        # Find the author ID in the path
        author_index = -1
        for i, part in enumerate(path_parts):
            if part == "authors" and i+1 < len(path_parts):
                author_index = i+1
                break
        
        if author_index == -1:
            print(f"Error: Could not find author ID in URL: {remote_url}")
            return
            
        remote_author_id = path_parts[author_index]
        
        # Construct the inbox URL using the same base structure
        service_path = "service/" if "service" in path_parts else ""
        inbox_url = f"{base_host}/{service_path}api/authors/{remote_author_id}/inbox"
        print(f"Constructed inbox URL: {inbox_url}")
        
        # Retrieve the corresponding RemoteNode for authentication
        remote_node = RemoteNode.objects.filter(host_url__icontains=base_host).first()
        print("Remote node:", remote_node.username, remote_node.password)
        
        if not remote_node:
            print(f"Warning: Remote node not found for {base_host}. Skipping authentication.")
            return
        
        # Use the post's stored remote_url if available
        original_post_url = post.remote_url if post.remote_url else None
        
        # If we don't have a stored URL, construct one (but this might not be reliable)
        if not original_post_url:
            post_id = post.id
            if is_uuid(post_id):
                post_id = get_numeric_id_for_author(post_id)
            original_post_url = f"{post_author.host}authors/{post_author.author_id}/posts/{post_id}"
        
        # Serialize the comment object
        serializer = CommentSerializer(comment, context={'request': request})
        comment_data = serializer.data
        print("Comment_data\n:",comment_data)
        # Modify comment data to use the original post URL
        comment_data['post'] = original_post_url
        
        node_username = remote_node.username
        node_password = remote_node.password
        
        try:
            response = requests.post(
                inbox_url,
                json=comment_data,
                headers={"Content-Type": "application/json"},
                auth=HTTPBasicAuth(node_username, node_password)  # Use Basic Auth
            )

            if response.status_code in [200, 201]:
                print(f"Comment sent successfully to {remote_author_id}")
            else:
                print(f"Failed to send comment to {remote_author_id}: {response.status_code}, {response.text}")

        except requests.RequestException as e:
            print(f"Error sending comment to {remote_author_id}: {e}")
