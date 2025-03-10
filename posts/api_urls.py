from django.urls import path
from . import views, api_views

app_name = 'api_posts'

urlpatterns = [
    # API endpoints
    path('<uuid:post_id>/', api_views.get_post_by_fqid, name='api-posts'),
    path('<uuid:post_id>/likes', api_views.local_post_likes, name='local_post_likes'),
    path('api/posts/<uuid:post_id>/shared/', api_views.shared_post_api, name='shared_post_api'),
]