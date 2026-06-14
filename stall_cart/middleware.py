from common.models import _thread_locals
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

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


class AjaxExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as exception:
            response = self.process_exception(request, exception)
            if response is None:
                raise exception
        
        # Intercept explicit 500 HTML responses returned by other handlers
        is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax and response and getattr(response, 'status_code', None) == 500:
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                logger.error("AJAX 500 HTML response detected, converting to JSON.")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Something went wrong on our server. Please try again later.'
                }, status=500)
                
        return response

    def process_exception(self, request, exception):
        is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            logger.error(f"AJAX Exception caught: {exception}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Something went wrong on our server. Please try again later.'
            }, status=500)
        return None