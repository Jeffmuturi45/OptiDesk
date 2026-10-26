"""Core middleware for OptiDesk."""
import logging

logger = logging.getLogger("audit")


class AuditMiddleware:
    """
    Attaches request metadata for downstream audit logging.
    Does not log every request — only records context
    that audit event handlers can use.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
