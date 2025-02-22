from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from .models import Post
from django.db import models
from identity.models import Author 
from django.contrib.auth.models import User  # Import Django User model / 导入Django用户模型（GJ）
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.decorators import api_view,permission_classes
from .permissions import IsAuthorOrAdmin
from rest_framework.response import Response
from rest_framework import status
from .serializers import PostSerializer


@api_view(['GET'])
def get_post_by_fqid(request, post_id):
    """
    Retrieve a public post by Fully Qualified ID (FQID).
    """
    post = get_object_or_404(Post, id=post_id)  
    serializer = PostSerializer(post)
    return Response(serializer.data, status=status.HTTP_200_OK)
