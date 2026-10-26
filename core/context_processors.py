"""Global context processors available in every template."""
from django.conf import settings
import django.utils.timezone as tz


def clinic_context(request):
    """Inject clinic-wide context into every template."""
    return {
        "CLINIC_NAME": settings.CLINIC_NAME,
        "server_now": tz.now(),
        "TIME_ZONE": settings.TIME_ZONE,
        "DEBUG": settings.DEBUG,
    }
