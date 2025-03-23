from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User
from .models import RemoteNode
import base64

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