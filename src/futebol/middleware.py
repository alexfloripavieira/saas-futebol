from contextvars import ContextVar
import uuid

request_id_var = ContextVar('request_id', default='-')


class RequestIDFilter:
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        token = request_id_var.set(request.request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response['X-Request-ID'] = request.request_id
        return response
