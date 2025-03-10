from django.urls import path, include
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # Web views
    path('', views.AuthorListView.as_view(), name='author-list'),
    # shows all authors
    path('edit-profile/', views.AuthorProfileEditView.as_view(), name='edit-profile'),

    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    # shows an author's profile page
    path('posts/', include('posts.urls', namespace='posts')),
    path('webhook/github/', views.github_webhook, name='github-webhook'),

    path('follow', views.follow, name='follow'),
    # send a follow request

    path('unfollow', views.unfollow, name='unfollow'),
    # unfollow an author

    path('<str:username>/requests/', views.Requests.as_view(), name='requests'),
    # view your follow requests

    path('accept', views.accept, name='accept'),
    # accept a follow request

    path('decline', views.decline, name='decline'),
    # decline a follow request

]