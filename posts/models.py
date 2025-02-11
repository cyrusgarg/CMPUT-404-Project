from datetime import datetime
from django.db import models
import markdown

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True, default="example@example.com")  # Add a default value
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    CONTENT_TYPE_CHOICES=[
        ('text/plain','Plain Text'),
        ('text/markdown','Markdown'),
    ]
    id=models.UUIDField(primary_key=True,editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Link post to an author
    title=models.CharField(max_length=255,default="")
    description=models.TextField(default="")
    content = models.TextField(blank=True, null=True)
    contentType = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text/plain')
    published = models.DateTimeField("published", default=datetime.now)   # Store the published date in a datetime field in the database
    visibility = models.CharField(max_length=20, choices=[("PUBLIC", "Public"), ("FRIENDS", "Friends Only"), ("UNLISTED", "Unlisted")],default='UNLISTED')
    
    def get_formatted_content(self):
        if self.contentType == 'text/markdown':
            return markdown.markdown(self.content)  # Convert markdown to HTML
        return self.content