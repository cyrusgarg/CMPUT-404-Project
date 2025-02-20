from django.urls import path, include
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # Web views
    path('', views.AuthorListView.as_view(), name='author-list'),
    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    path('posts/', include('posts.urls', namespace='posts')),

    path('webhook/github/', views.github_webhook, name='github-webhook'),
]