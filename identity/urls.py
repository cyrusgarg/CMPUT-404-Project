from django.urls import path
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # Web views
    path('', views.AuthorListView.as_view(), name='author-list'),
    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    path('webhook/github/', views.github_webhook, name='github-webhook'),
    path('follow', views.follow, name='follow'),
    path('unfollow', views.unfollow, name='unfollow'),
    path('<str:username>/requests/', views.Requests.as_view(), name='requests'),
    path('accept', views.accept, name='accept'),
    path('decline', views.decline, name='decline'),
]