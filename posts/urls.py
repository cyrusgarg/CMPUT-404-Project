from django.urls import path,include
from . import views

app_name = "posts"

urlpatterns = [
    path("", views.index, name="index"),
    path('<uuid:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create_post, name='create_post'),
    path('<uuid:post_id>/delete/', views.delete_post, name='delete_post'),
    path('api/authors/<uuid:author_id>/posts/', views.get_author_posts, name='author_posts'),
    # Get a specific post
    path('api/authors/<uuid:author_id>/posts/<uuid:post_id>/', views.get_post_detail, name='post_detail'),
    # Create a new post (API)
    path('api/authors/<uuid:author_id>/posts/', views.create_post, name='create_post'),
]