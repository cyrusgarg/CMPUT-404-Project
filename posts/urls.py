from django.urls import path,include
from . import views

app_name = "posts"

urlpatterns = [
    path("", views.index, name="index"),
    path('<uuid:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create_post, name='create_post'),
    path('<uuid:post_id>/delete/', views.delete_post, name='delete_post'),
    path('<uuid:post_id>/', views.get_post_by_fqid, name='get_post_by_fqid'),
]