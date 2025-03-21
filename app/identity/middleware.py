from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.http import JsonResponse
from .authentication import authenticate, authenticate_with_token

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

class NodeAuthenticationMiddleware:
    """
    Middleware to enforce node-level authentication on certain endpoints (e.g., /inbox/).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the request path should be node-authenticated.
        if "/inbox" in request.path:
            auth_header = request.META.get('HTTP_AUTHORIZATION')
            if not auth_header:
                return JsonResponse({"detail": "Authentication required."}, status=401)
            try:
                method, credentials = auth_header.split(' ', 1)
                if method.lower() == 'basic':
                    decoded = base64.b64decode(credentials).decode('utf-8')
                    username, password = decoded.split(':', 1)
                    user = authenticate(username=username, password=password)
                elif method.lower() == 'token':
                    token = credentials  # You might have a different logic for token authentication
                    user = authenticate_with_token(token)  # Replace with your token auth logic
                else:
                    return JsonResponse({"detail": "Unsupported authentication method."}, status=401)

            except Exception:
                return JsonResponse({"detail": "Invalid authentication header."}, status=401)

            if user is None:
                return JsonResponse({"detail": "Invalid credentials."}, status=401)
            
            # Optionally, attach the authenticated node user to the request if needed in views.
            request.node_user = user

        # Proceed to the next middleware or view.
        response = self.get_response(request)
        return response