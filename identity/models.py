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
    
    def __str__(self):
        return self.display_name or self.user.username

# In Django admin, create an Author instance:
from django.contrib import admin
from .models import Author

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'user']


