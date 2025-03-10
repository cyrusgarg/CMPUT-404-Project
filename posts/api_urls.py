from django.urls import path
from . import views, api_views

app_name = 'api_posts'

urlpatterns = [
    # API endpoints
    path('', api_views.post_list, name='post_list'),
    path('<uuid:post_id>/', api_views.get_post_by_fqid, name='api-posts'),
    path('<uuid:post_id>/likes', api_views.local_post_likes, name='local_post_likes'),
    path('<uuid:post_id>/comments', api_views.post_comments, name='post_comments'),
]