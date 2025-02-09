from datetime import datetime
from django.db import models

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True, default="example@example.com")  # Add a default value
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Link post to an author
    pub_date = models.DateTimeField("date published", default=datetime.now)   # Store the published date in a datetime field in the database
    content = models.TextField(blank=True, null=True)