import base64
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token  # DRF's default token model

User = get_user_model()

def authenticate(username=None, password=None):
    """
    Authenticate a user using a username and password.
    This function retrieves the user by username and then checks the password.
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None

    if user.check_password(password):
        return user
    return None

def authenticate_with_token(token):
    """
    Authenticate a user using a token.
    This function uses Django REST Framework's default Token model.
    Tokens are created using the drf_create_token management command.
    """
    try:
        token_obj = Token.objects.get(key=token)
        return token_obj.user
    except Token.DoesNotExist:
        return None
