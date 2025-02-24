from django.urls import path,include
from . import views

app_name = "posts"  # Define namespace for URLs / 定义URL命名空间（GJ）

urlpatterns = [
    path("", views.index, name="index"),  
    # Show all posts created by the logged-in user / 显示当前用户创建的所有帖子（GJ）

    path("views/", views.view_posts, name="view_posts"),  
    # Show posts visible to the logged-in user / 显示用户可查看的帖子（GJ）

    path('<uuid:post_id>/', views.post_detail, name='post_detail'),  
    # Show details of a specific post / 显示指定帖子的详细信息（GJ）

    path('create/', views.create_post, name='create_post'),  
    # Create a new post / 创建新帖子（GJ）

    path('<uuid:post_id>/delete/', views.delete_post, name='delete_post'),  
    # Delete a post (mark as deleted) / 删除帖子（标记为删除）（GJ）

    path('<uuid:post_id>/edit/', views.edit_post, name="edit_post"),  
    # Show edit page for a post / 显示帖子编辑页面（GJ）

    path('<uuid:post_id>/update/', views.update_post, name="update_post"),  
    # API endpoint for updating a post / 通过API更新帖子（GJ）
    
    path('<uuid:post_id>/webUpdate/', views.web_update_post, name="web_update_post"),  

    path('<uuid:post_id>/like/', views.like_post, name="like_post"),  
    # Like a post

    path("<uuid:post_id>/likes/", views.post_likes, name="post_likes"),
    # List of likes

    path('<uuid:post_id>/comment/', views.add_comment, name="add_comment"),  
    # Add a comment

    path('<uuid:post_id>/comments/', views.get_comments, name="get_comments"),
    # Retrieve comments

]



