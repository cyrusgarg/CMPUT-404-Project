from django.urls import path
from . import views, api_views

app_name = 'identity'

urlpatterns = [
    # Web views
    path('', views.AuthorListView.as_view(), name='author-list'),
    path('<str:username>/', views.AuthorProfileView.as_view(), name='author-profile'),
    
]