from django.urls import path
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # API endpoints
    path('', api_views.author_list, name='api-author-list'),
    path('<uuid:author_id>/', api_views.author_detail, name='api-author-detail'),
    path('<uuid:author_id>/posts/', api_views.author_posts, name='api-author-posts'),
    path('<uuid:author_id>/posts/<uuid:post_id>/', api_views.author_post_detail, name='api-author-post-detail'),
    path('api/auth-test/', api_views.auth_test, name='auth-test'),
    path('<uuid:author_id>/commented/', api_views.author_commented, name='author_commented'),
    path('<uuid:author_id>/commented/<uuid:comment_id>/', api_views.get_comment, name='get_comment'),
    path('<uuid:comment_id>/', api_views.get_comment_by_id, name='get_comment_by_id'),
]