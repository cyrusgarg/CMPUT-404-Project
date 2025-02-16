# urls.py
from django.urls import path
from . import views
app_name = 'identity'  

urlpatterns = [
    path('', views.AuthorListView.as_view(), name='author-list'),
    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    path('webhook/github/', views.github_webhook, name='github-webhook'),
]