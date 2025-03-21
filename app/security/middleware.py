# security/middleware.py
from django.http import HttpResponseForbidden

class SameOriginMiddleware:
    """
    Middleware that ensures incoming requests have an Origin header
    matching the server's host. This way, the node's UI will only communicate
    with this node's own web server.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN")
        host = request.get_host()
        # If there is an Origin header and it does not match the host,
        # then reject the request.
        if origin and host not in origin:
            return HttpResponseForbidden("Forbidden: Cross origin request.")
        return self.get_response(request)
