from django.urls import path
from . import views, api_views

app_name = 'posts'

urlpatterns = [
    # API endpoints
    path('<uuid:post_id>/', api_views.get_post_by_fqid, name='api-posts')
]