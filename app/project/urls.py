"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from identity.views import test_basic_auth

urlpatterns = [
    path('posts/', include('posts.urls',namespace='posts_frontend')),
    #path('api/authors/', include('authors.urls')),  # Include author-related API (including inbox)
    path('authors/', include('identity.urls', namespace='identity')),
    path('api/authors/', include('identity.api_urls', namespace='identity_api')),
    path('api/posts/', include('posts.api_urls',namespace='posts_api')),  # Keep post-related API separate
    path('api/',include('identity.api_urls',namespace='comments_api')),
    path('admin/', admin.site.urls),

    path('accounts/', include('django.contrib.auth.urls')),
    
    path('accounts/login/', RedirectView.as_view(pattern_name='identity:login'), name='login_redirect'),
    path('test-basic-auth/', test_basic_auth, name='test-basic-auth'),


]

if settings.DEBUG:  # Only serve media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)