# models.py
from django.db import models
# models.py
from django.contrib.auth.models import User
from django.db import models

class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    display_name = models.CharField(max_length=100)
    github_username = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.display_name or self.user.username

# In Django admin, create an Author instance:
from django.contrib import admin
from .models import Author

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'user']

class GitHubActivity(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='github_activities')
    # Unique event ID from GitHub to prevent duplicates:
    event_id = models.CharField(max_length=50, unique=True)
    event_type = models.CharField(max_length=100)
    # Store the full event data (requires Django 3.1+; for older versions, consider using TextField)
    payload = models.JSONField()
    created_at = models.DateTimeField()

    def __str__(self):
        return f"{self.author} - {self.event_type} at {self.created_at}"