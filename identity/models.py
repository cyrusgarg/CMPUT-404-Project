from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.conf import settings

class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='author_profile')
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    display_name = models.CharField(max_length=100)
    
    type = models.CharField(max_length=50, default='author')
    author_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.URLField(default=settings.SITE_URL)
    github = models.URLField(blank=True)
    
    @property
    def id(self):
        """Return the full API URL for the author"""
        return f"{self.host}/api/authors/{self.author_id}"
    
    @property
    def page(self):
        """Return the URL of the user's HTML profile page"""
        return f"{self.host}/authors/{self.author_id}"
    
    def get_absolute_url(self):
        return reverse('identity:author-profile', kwargs={'pk': self.author_id})
    
    def to_dict(self):
        return {
            "type": "author",
            "id": self.id,
            "host": self.host,
            "displayName": self.display_name,
            "github": self.github,
            "profileImage": self.profile_image.url if self.profile_image else "",
            "page": self.page
        }

    def __str__(self):
        return self.display_name or self.user.username

@receiver(post_save, sender=User)
def create_user_author(sender, instance, created, **kwargs):
    if created:
        Author.objects.create(user=instance, display_name=instance.username)

@receiver(post_save, sender=User)
def save_user_author(sender, instance, **kwargs):
    if hasattr(instance, 'author_profile'):
        instance.author_profile.save()
