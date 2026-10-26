"""
Dashboard views: route authenticated users to role-specific dashboards.
Shows real data when available, empty states when models are not yet populated.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User


@login_required
def home(request):
    """Route to the appropriate role-specific dashboard."""
    user = request.user
    today = timezone.localdate()
    now = timezone.now()

    # Base context shared across all roles
    ctx = {
        "today": today,
        "now": now,
        # Queue/appointment counts — will be real once those models are built
        "queue_waiting": 0,
        "queue_in_consultation": 0,
        "queue_completed": 0,
        "todays_appointments": 0,
    }

    if user.is_superadmin:
        return _admin_dashboard(request, ctx)
    elif user.is_doctor:
        return _doctor_dashboard(request, ctx)
    else:
        return _receptionist_dashboard(request, ctx)


def _admin_dashboard(request, ctx):
    """Superadmin dashboard: system health, users, activity."""
    # Real user counts
    ctx.update({
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "doctors": User.objects.filter(role="doctor", is_active=True).count(),
        "receptionists": User.objects.filter(role="receptionist", is_active=True).count(),
        "recent_users": User.objects.order_by("-date_joined")[:5],
    })
    return render(request, "dashboard/admin_dashboard.html", ctx)


def _doctor_dashboard(request, ctx):
    """Doctor dashboard: waiting queue, current consultation, appointments."""
    ctx.update({
        "waiting_patients": [],   # Populated by queue app in Phase 5
        "current_patient": None,  # Populated by queue app in Phase 5
        "todays_encounters": 0,   # Populated by clinical app in Phase 6
        "pending_notes": 0,       # Populated by clinical app in Phase 6
    })
    return render(request, "dashboard/doctor_dashboard.html", ctx)


def _receptionist_dashboard(request, ctx):
    """Receptionist dashboard: check-in, queue overview, appointments."""
    ctx.update({
        "waiting_patients": [],   # Populated by queue app in Phase 5
        "checked_in_patients": [],  # Populated by queue app in Phase 5
    })
    return render(request, "dashboard/receptionist_dashboard.html", ctx)
