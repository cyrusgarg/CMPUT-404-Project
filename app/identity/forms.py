from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Author
from .models import RemoteNode
class AuthorProfileForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['display_name', 'bio', 'profile_image', 'github_username', 'github']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }


class UserSignUpForm(UserCreationForm):
    """Form for user registration with Author profile fields"""
    email = forms.EmailField(required=True)
    display_name = forms.CharField(max_length=100, required=True)
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    github_username = forms.CharField(max_length=100, required=False)
    github = forms.URLField(required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            # Get author profile created by signal
            author = user.author_profile
            author.display_name = self.cleaned_data['display_name']
            author.bio = self.cleaned_data['bio']
            author.github_username = self.cleaned_data['github_username']
            author.github = self.cleaned_data['github']
            
            # Auto-approve if approval is not required
            from django.conf import settings
            author.is_approved = not settings.REQUIRE_AUTHOR_APPROVAL
            
            author.save()
        
        return user
    

class RemoteNodeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    
    class Meta:
        model = RemoteNode
        fields = ['name', 'host_url', 'username', 'password', 'is_active']
        widgets = {
            'host_url': forms.URLInput(attrs={'placeholder': 'https://example.com'}),
        }