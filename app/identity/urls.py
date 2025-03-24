from django.urls import path, include
from . import views, api_views
from .views import (
    RemoteNodeListView, 
    RemoteNodeCreateView, 
    RemoteNodeUpdateView, 
    RemoteNodeDeleteView,
    RemoteAuthorListView,
    RemoteAuthorDetailView,
    fetch_remote_authors
)
app_name = 'identity'

urlpatterns = [
    # Web views
    path('', views.AuthorListView.as_view(), name='author-list'),
    # shows all authors
    path('edit-profile/', views.AuthorProfileEditView.as_view(), name='edit-profile'),
    path('signup/', views.UserSignUpView.as_view(), name='signup'),
    path('waiting-approval/', views.waiting_approval_view, name='waiting_approval'),
    
    # Node management URLs - Must come before the username pattern
    path('nodes/', views.RemoteNodeListView.as_view(), name='remote-node-list'),
    path('nodes/add/', views.RemoteNodeCreateView.as_view(), name='remote-node-add'),
    path('nodes/<int:pk>/edit/', views.RemoteNodeUpdateView.as_view(), name='remote-node-edit'),
    path('nodes/<int:pk>/delete/', views.RemoteNodeDeleteView.as_view(), name='remote-node-delete'),
    
    # Remote Author paths
    path('nodes/<int:node_id>/authors/', views.RemoteAuthorListView.as_view(), name='remote-authors-list'),
    path('nodes/<int:node_id>/fetch-authors/', views.fetch_remote_authors, name='fetch-remote-authors'),
    # Other specific paths
    path('posts/', include('posts.urls', namespace='posts')),
    path('webhook/github/', views.github_webhook, name='github-webhook'),
    path('follow', views.follow, name='follow'),
    path('unfollow', views.unfollow, name='unfollow'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('accept', views.accept, name='accept'),
    path('decline', views.decline, name='decline'),
    
    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    path('<str:username>/requests/', views.Requests.as_view(), name='requests'),
    path('nodes/<int:node_id>/authors/', RemoteAuthorListView.as_view(), name='remote-authors-list'),
    path('nodes/<int:node_id>/authors/<int:pk>/', RemoteAuthorDetailView.as_view(), name='remote-author-detail'),
    path('nodes/<int:node_id>/fetch/', fetch_remote_authors, name='fetch-remote-authors'),
]