from common.models import _thread_locals

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        try:
            response = self.get_response(request)
        finally:
            if hasattr(_thread_locals, 'user'):
                del _thread_locals.user
        return response