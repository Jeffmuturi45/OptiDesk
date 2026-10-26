from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from accounts.decorators import superadmin_required
from .models import AuditEvent


@login_required
@superadmin_required
def event_list(request):
    qs = AuditEvent.objects.select_related("user").order_by("-timestamp")
    event_type = request.GET.get("event_type", "")
    if event_type:
        qs = qs.filter(event_type=event_type)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))
    event_types = AuditEvent.objects.values_list(
        "event_type", flat=True).distinct().order_by("event_type")

    return render(request, "audit/event_list.html", {
        "page_obj": page,
        "event_types": event_types,
        "selected_type": event_type,
    })
