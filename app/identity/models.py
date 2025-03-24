from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.conf import settings
from django.contrib import admin
from .id_mapping import get_numeric_id_for_author

class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='author_profile')
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    display_name = models.CharField(max_length=100)
    github_username = models.CharField(max_length=100, blank=True, null=True)  
    type = models.CharField(max_length=50, default='author')
    author_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.URLField(default=settings.SITE_URL)
    github = models.URLField(blank=True)
    is_approved = models.BooleanField(default=False)

    @property
    def id(self,request):
        """Return the full API URL for the author"""
        base_url = self.get_dynamic_host(request)
        return f"{base_url}/api/authors/{self.author_id}"
    
    def get_dynamic_host(self, request):
        return f"https://{request.get_host()}" if request else self.host

    @property
    def page(self,request):
        """Return the URL of the user's HTML profile page"""
        first_name = self.display_name.split(" ", 1)[0].lower()
        base_url = self.get_dynamic_host(request)
        return f"{base_url}/authors/{first_name}"
    
    def get_absolute_url(self):
        return reverse('identity:author-profile', kwargs={'pk': self.author_id})
    
    def to_dict(self,request=None):
        #numeric_id = get_numeric_id_for_author(self.author_id)
        base_url = f"https://{request.get_host()}" if request else self.host
        return {
            "type": "author",
            "id": f"{base_url}/api/authors/{self.author_id}",
            "host": base_url,
            "displayName": self.display_name,
            "github": self.github,
            "profileImage": self.profile_image.url if self.profile_image else "",
            "page": f"{base_url}/authors/{self.display_name.split(' ', 1)[0].lower()}",
            # "url": f"{base_url}/authors/{self.author_id}"
        }
    github_username = models.CharField(max_length=100, blank=True, null=True)

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
# In Django admin, create an Author instance:


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'user', 'is_approved']
    list_filter = ['is_approved']
    actions = ['approve_authors']
    
    def approve_authors(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} authors have been approved.")
    approve_authors.short_description = "Approve selected authors"

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

class Following(models.Model):
    # represents a following relationship, i.e. follower is following followee
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="follower")  
    followee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followee")
    created_at = models.DateTimeField(auto_now_add=True)

class RemoteFollower(models.Model):
    # represents a remote follower
    follower_name = models.CharField(max_length=100)
    follower_id = models.CharField(max_length=255)
    followee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="remote_followee")
    created_at = models.DateTimeField(auto_now_add=True)

class FollowRequests(models.Model):
    # represents a follow request, i.e. sender requested to follow receiver
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sender")  
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="receiver")
    created_at = models.DateTimeField(auto_now_add=True)

class RemoteFollowRequests(models.Model):
    # represents a remote follow request
    sender_name = models.CharField(max_length=100)
    sender_id = models.CharField(max_length=255)
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="remote_receiver")
    created_at = models.DateTimeField(auto_now_add=True)

class Friendship(models.Model):
    # represents a friendship between two users
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user2")
    created_at = models.DateTimeField(auto_now_add=True)


class RemoteNode(models.Model):
    """Model representing a remote node to share content with"""
    name = models.CharField(max_length=100)
    host_url = models.URLField(max_length=255, unique=True, help_text="Full URL including http:// or https:// and port if needed")
    username = models.CharField(max_length=100)  # For HTTP Basic Auth
    password = models.CharField(max_length=100)  # For HTTP Basic Auth
    is_active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
    def get_formatted_url(self):
        """
        Returns a properly formatted URL, ensuring IPv6 addresses have brackets
        """
        host_url = self.host_url.rstrip('/')
        
        # Check if it's an IPv6 address without brackets
        if ':' in host_url.replace('http://', '').replace('https://', '') and not ('[' in host_url and ']' in host_url):
            # Extract protocol
            protocol = 'https://' if host_url.startswith('https://') else 'http://'
            
            # Extract address part
            address_part = host_url.replace('http://', '').replace('https://', '')
            
            # Check if there's a port
            if address_part.count(':') > 1:  # More than one colon means it's IPv6
                # Check if it has a port at the end
                if ':' in address_part.rsplit(':', 1)[1]:  # e.g., the last part is a port like :80
                    ip_part = address_part.rsplit(':', 1)[0]
                    port_part = address_part.rsplit(':', 1)[1]
                    return f"{protocol}[{ip_part}]:{port_part}"
                else:
                    return f"{protocol}[{address_part}]"
        
        return host_url

class RemoteAuthor(models.Model):
    """Model representing an author from a remote node"""
    node = models.ForeignKey(RemoteNode, on_delete=models.CASCADE, related_name='authors')
    author_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    host = models.URLField(max_length=255)
    github = models.URLField(blank=True, null=True)
    profile_image = models.URLField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.node.name})"

    class Meta:
        unique_together = ['node', 'author_id']
        ordering = ['display_name']