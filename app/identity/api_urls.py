from django.urls import path
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # API endpoints
    path('', api_views.AuthorListView.as_view(), name='author-list'),
    path('<uuid:pk>/', api_views.AuthorDetailView.as_view(), name='author-detail-uuid'),
    path('<int:pk>/', api_views.AuthorDetailView.as_view(), name='author-detail'),
    path('<uuid:author_id>/posts/', api_views.author_posts, name='api-author-posts'),
    path('<uuid:author_id>/posts/<uuid:post_id>', api_views.author_post_detail, name='api-author-post-detail'),
    path('api/auth-test/', api_views.auth_test, name='auth-test'),
    path('<uuid:author_id>/commented', api_views.author_commented, name='author_commented'),
    path('<uuid:author_id>/commented/<uuid:comment_id>', api_views.get_comment, name='get_comment'),
    path('<uuid:author_id>/posts/<uuid:post_id>/likes', api_views.post_likes, name='post_likes'),
    path('<uuid:author_id>/posts/<uuid:post_id>/comments/<uuid:comment_id>/likes', api_views.comment_likes, name='comment_likes'),
    path('commented/<uuid:comment_id>', api_views.get_comment_by_id, name='get_comment_by_id'),
    path('<uuid:author_id>/liked', api_views.get_author_likes, name='api-author-liked'),
    path('<uuid:author_id>/liked/<uuid:like_id>', api_views.get_single_like, name='api-single-like'),
    path('<path:author_fqid>/liked', api_views.get_author_likes_by_fqid, name='author-likes-by-fqid'),
    # path('liked/<uuid:like_id>', api_views.get_single_like_by_fqid, name='api-liked-fqid'),
    path("liked/<path:like_fqid>", api_views.get_like_by_fqid, name="like-by-fqid"),
    path('<uuid:author_id>/posts/<uuid:post_id>/image', api_views.image_post, name='image_post'),
    path('<uuid:author_id>/posts/<uuid:post_id>/comments', api_views.post_comment, name='post_comment'),
    path('<uuid:author_id>/inbox', api_views.inbox, name='inbox'),
    path('<uuid:author_id>/followers', api_views.followers, name='followers'),
    path('<uuid:author_id>/followers/<uuid:follower_id>', api_views.follower, name='follower'),
    path('node-auth-test/', api_views.NodeAuthTestView.as_view(), name='node-auth-test'),


]