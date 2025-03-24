from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from .models import RemoteNode
import base64
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
# from rest_framework.authtoken.models import Token  # DRF's default token model

User = get_user_model()

class NodeBasicAuthentication(authentication.BaseAuthentication):
    """
    HTTP Basic authentication for node-to-node connections.
    """
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Basic '):
            return None
        
        try:
            # Decode auth header
            auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = auth_decoded.split(':', 1)
            
            # Check if this is a valid node connection
            try:
                node = RemoteNode.objects.get(username=username, password=password, is_active=True)
                # Use an admin user for node authentication
                system_user = User.objects.filter(is_superuser=True).first()
                return (system_user, node)
            except RemoteNode.DoesNotExist:
                raise exceptions.AuthenticationFailed('Invalid node credentials')
            except User.DoesNotExist:
                raise exceptions.AuthenticationFailed('System user not found')
            
        except (ValueError, UnicodeDecodeError):
            raise exceptions.AuthenticationFailed('Invalid basic auth header')
    
    def authenticate_header(self, request):
        return 'Basic realm="Node API"'

# def authenticate(username=None, password=None):
#     """
#     Authenticate a user using a username and password.
#     This function retrieves the user by username and then checks the password.
#     """
#     try:
#         user = User.objects.get(username=username)
#     except User.DoesNotExist:
#         return None
    
#     if user.check_password(password):
#         return user
#     return None

# def authenticate_with_token(token):
#     """
#     Authenticate a user using a token.
#     This function uses Django REST Framework's default Token model.
#     Tokens are created using the drf_create_token management command.
#     """
#     try:
#         token_obj = Token.objects.get(key=token)
#         return token_obj.user
#     except Token.DoesNotExist:
#         return None
