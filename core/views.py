"""Core views: home redirect and error handlers."""
from django.shortcuts import redirect
from django.template.response import TemplateResponse


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return redirect("accounts:login")


def error_400(request, exception=None):
    return TemplateResponse(request, "errors/400.html", status=400)


def error_403(request, exception=None):
    return TemplateResponse(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return TemplateResponse(request, "errors/404.html", status=404)


def error_500(request):
    return TemplateResponse(request, "errors/500.html", status=500)
