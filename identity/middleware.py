from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

class AuthorApprovalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip check if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)
            
        # Skip for admin users and certain paths
        if request.user.is_staff or request.path.startswith('/admin/') or request.path == reverse('identity:waiting_approval'):
            return self.get_response(request)
            
        # Check if the user's author profile is approved
        if hasattr(request.user, 'author_profile') and not request.user.author_profile.is_approved:
            messages.warning(request, "Your account is pending approval by an admin.")
            return redirect('identity:waiting_approval')
            
        return self.get_response(request)