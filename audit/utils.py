"""Utility function to record audit events."""
import logging
from .models import AuditEvent

logger = logging.getLogger("audit")


def _get_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_event(request, event_type: str, description: str = "", extra: dict = None):
    """
    Record a security or business audit event.
    Never logs passwords, recovery code plaintexts, or session tokens.
    """
    user = None
    username = ""

    if request and hasattr(request, "user") and request.user.is_authenticated:
        user = request.user
        username = request.user.username

    ip = _get_ip(request) if request else ""

    try:
        AuditEvent.objects.create(
            user=user,
            username_snapshot=username,
            event_type=event_type,
            description=description,
            ip_address=ip or None,
            extra=extra or {},
        )
    except Exception as e:
        # Never let audit logging crash the application
        logger.error("Failed to write audit event %s: %s", event_type, e)
