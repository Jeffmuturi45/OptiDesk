"""Role-based access control decorators."""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def superadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.is_superadmin:
            messages.error(
                request, "You do not have permission to access that page.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapper


def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (request.user.is_doctor or request.user.is_superadmin):
            messages.error(
                request, "You do not have permission to access that page.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapper


def receptionist_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not (request.user.is_receptionist or request.user.is_superadmin):
            messages.error(
                request, "You do not have permission to access that page.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*roles):
    """Allow access to users whose role is in the given list."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.role not in roles and not request.user.is_superadmin:
                messages.error(
                    request, "You do not have permission to access that page.")
                return redirect("dashboard:home")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
