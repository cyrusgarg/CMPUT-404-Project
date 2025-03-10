from django import forms
from .models import Author

class AuthorProfileForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['display_name', 'bio', 'profile_image', 'github_username', 'github']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }