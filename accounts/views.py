"""
Accounts views: login, logout, password management, user administration,
recovery code generation and download.
"""
import secrets
import hashlib
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from audit.utils import log_event
from .models import User, RecoveryCode, Role
from .forms import (
    LoginForm, UserCreateForm, UserEditForm,
    ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm,
)
from .decorators import superadmin_required, role_required

logger = logging.getLogger("accounts")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash_code(plaintext: str) -> str:
    """Return a secure hash of a plaintext recovery code."""
    import hashlib
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ─── Authentication ────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)
            user.last_login_ip = _get_client_ip(request)
            user.save(update_fields=["last_login_ip"])
            log_event(request, "LOGIN_SUCCESS", f"User {username} logged in")

            if user.must_change_password:
                messages.warning(
                    request, "You must change your password before continuing.")
                return redirect("accounts:change_password")

            next_url = request.GET.get("next", "dashboard:home")
            return redirect(next_url)
        else:
            log_event(request, "LOGIN_FAILED",
                      f"Failed login attempt for username: {username}")
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    log_event(request, "LOGOUT", f"User {request.user.username} logged out")
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("accounts:login")


# ─── Password Management ───────────────────────────────────────────────────────

@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        request.user.must_change_password = False
        request.user.save(update_fields=["must_change_password"])
        log_event(request, "PASSWORD_CHANGED", "User changed own password")
        messages.success(request, "Password updated successfully.")
        return redirect("dashboard:home")
    return render(request, "accounts/change_password.html", {"form": form})


@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """Step 1: enter username + recovery code."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        code_input = form.cleaned_data["recovery_code"].strip()

        try:
            user = User.objects.get(username=username, is_active=True)
            rc = RecoveryCode.objects.select_for_update().get(user=user)
        except (User.DoesNotExist, RecoveryCode.DoesNotExist):
            messages.error(request, "Invalid username or recovery code.")
            return render(request, "accounts/forgot_password.html", {"form": form})

        with transaction.atomic():
            rc_fresh = RecoveryCode.objects.select_for_update().get(pk=rc.pk)
            if not rc_fresh.is_valid:
                messages.error(request, "Invalid username or recovery code.")
                return render(request, "accounts/forgot_password.html", {"form": form})

            expected_hash = _hash_code(code_input)
            if not secrets.compare_digest(rc_fresh.code_hash, expected_hash):
                log_event(request, "RECOVERY_CODE_INVALID",
                          f"Bad code for user {username}")
                messages.error(request, "Invalid username or recovery code.")
                return render(request, "accounts/forgot_password.html", {"form": form})

            # Valid — store user pk in session to proceed to step 2
            request.session["reset_user_pk"] = user.pk
            request.session["reset_code_pk"] = rc_fresh.pk
            request.session.set_expiry(300)   # 5 minutes to complete reset
            return redirect("accounts:reset_password")

    return render(request, "accounts/forgot_password.html", {"form": form})


@require_http_methods(["GET", "POST"])
def reset_password(request):
    """Step 2: set new password after valid recovery code."""
    user_pk = request.session.get("reset_user_pk")
    code_pk = request.session.get("reset_code_pk")

    if not user_pk or not code_pk:
        messages.error(
            request, "Password reset session expired. Please start again.")
        return redirect("accounts:forgot_password")

    user = get_object_or_404(User, pk=user_pk, is_active=True)
    form = ResetPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        new_password = form.cleaned_data["new_password1"]
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            for err in e.messages:
                messages.error(request, err)
            return render(request, "accounts/reset_password.html", {"form": form})

        with transaction.atomic():
            rc = RecoveryCode.objects.select_for_update().get(pk=code_pk, user=user)
            if not rc.is_valid:
                messages.error(request, "Recovery code is no longer valid.")
                return redirect("accounts:forgot_password")

            rc.consume()
            user.set_password(new_password)
            user.must_change_password = False
            user.save()

            # Invalidate all existing sessions for this user
            from django.contrib.sessions.backends.db import SessionStore
            from django.contrib.sessions.models import Session
            for session in Session.objects.filter(expire_date__gte=timezone.now()):
                data = session.get_decoded()
                if data.get("_auth_user_id") == str(user.pk):
                    session.delete()

        del request.session["reset_user_pk"]
        del request.session["reset_code_pk"]

        log_event(request, "PASSWORD_RESET",
                  f"Password reset via recovery code for {user.username}")
        messages.success(
            request, "Password reset successfully. Please log in.")
        return redirect("accounts:login")

    return render(request, "accounts/reset_password.html", {"form": form, "target_user": user})


# ─── Profile ───────────────────────────────────────────────────────────────────

@login_required
def profile(request):
    return render(request, "accounts/profile.html", {"profile_user": request.user})


# ─── User Management (Superadmin only) ────────────────────────────────────────

@login_required
@superadmin_required
def user_list(request):
    users = User.objects.all().order_by("last_name", "first_name")
    return render(request, "accounts/user_list.html", {"users": users})


@login_required
@superadmin_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data["password1"])
        user.must_change_password = True
        user.save()
        log_event(request, "USER_CREATED",
                  f"Created user {user.username} role={user.role}")
        messages.success(
            request, f"User '{user.get_full_name()}' created. They must change their password on first login.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "action": "Create"})


@login_required
@superadmin_required
def user_detail(request, pk):
    target = get_object_or_404(User, pk=pk)
    try:
        rc = target.recovery_code
    except RecoveryCode.DoesNotExist:
        rc = None
    return render(request, "accounts/user_detail.html", {"target_user": target, "recovery_code": rc})


@login_required
@superadmin_required
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_event(request, "USER_EDITED", f"Edited user {target.username}")
        messages.success(request, "User updated.")
        return redirect("accounts:user_detail", pk=pk)
    return render(request, "accounts/user_form.html", {"form": form, "target_user": target, "action": "Edit"})


@login_required
@superadmin_required
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_detail", pk=pk)
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    status = "activated" if target.is_active else "deactivated"
    log_event(request, "USER_STATUS_CHANGED",
              f"User {target.username} {status}")
    messages.success(request, f"Account {status}.")
    return redirect("accounts:user_detail", pk=pk)


# ─── Recovery Code Management ─────────────────────────────────────────────────

@login_required
@superadmin_required
@require_POST
def generate_recovery_code(request, pk):
    target = get_object_or_404(User, pk=pk)

    # Revoke existing code if any
    try:
        existing = target.recovery_code
        existing.revoke()
    except RecoveryCode.DoesNotExist:
        pass

    plaintext = secrets.token_urlsafe(32)   # 256 bits of entropy
    code_hash = _hash_code(plaintext)

    rc = RecoveryCode.objects.create(
        user=target,
        code_hash=code_hash,
        created_by=request.user,
    )

    log_event(request, "RECOVERY_CODE_GENERATED",
              f"Recovery code generated for {target.username} by {request.user.username}")

    # Store plaintext in session ONLY long enough for download (5 min)
    request.session[f"rc_plaintext_{target.pk}"] = plaintext
    request.session[f"rc_id_{target.pk}"] = rc.pk
    request.session.set_expiry(300)

    messages.success(
        request, f"Recovery code generated for {target.get_full_name()}. Download the file now — it will not be shown again.")
    return redirect("accounts:user_detail", pk=pk)


@login_required
@superadmin_required
def download_recovery_file(request, pk):
    target = get_object_or_404(User, pk=pk)

    plaintext = request.session.get(f"rc_plaintext_{target.pk}")
    rc_id = request.session.get(f"rc_id_{target.pk}")

    if not plaintext or not rc_id:
        messages.error(
            request, "Recovery file is no longer available. Generate a new code.")
        return redirect("accounts:user_detail", pk=pk)

    # Verify the code still exists and is active
    try:
        rc = RecoveryCode.objects.get(pk=rc_id, user=target, is_active=True)
    except RecoveryCode.DoesNotExist:
        messages.error(request, "Recovery code is no longer valid.")
        return redirect("accounts:user_detail", pk=pk)

    content = f"""OptiDesk — Staff Account Recovery File
========================================

CONFIDENTIAL — Keep this file private and secure.
Do not share it with anyone other than the account holder.
Anyone with this code and the associated username can reset this account's password.

Account Username : {target.username}
Account Name     : {target.get_full_name()}
Account Role     : {target.get_role_display()}
Code Generated   : {rc.created_at.strftime('%Y-%m-%d %H:%M:%S')} (server time)

Recovery Code:
--------------
{plaintext}

How to use:
1. Go to the OptiDesk login page.
2. Click "Forgot Password".
3. Enter the username above and this recovery code.
4. Follow the prompts to set a new password.

This code can only be used ONCE.
After use, request a new recovery file from your administrator.

========================================
OptiDesk Optical Clinic Management System
"""

    # Clear plaintext from session immediately after generating the file
    del request.session[f"rc_plaintext_{target.pk}"]
    del request.session[f"rc_id_{target.pk}"]

    log_event(request, "RECOVERY_FILE_DOWNLOADED",
              f"Recovery file downloaded for {target.username}")

    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="optidesksv-recovery-{target.username}.txt"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@superadmin_required
@require_POST
def revoke_recovery_code(request, pk):
    target = get_object_or_404(User, pk=pk)
    try:
        rc = target.recovery_code
        rc.revoke()
        log_event(request, "RECOVERY_CODE_REVOKED",
                  f"Recovery code revoked for {target.username} by {request.user.username}")
        messages.success(request, "Recovery code revoked.")
    except RecoveryCode.DoesNotExist:
        messages.warning(request, "No recovery code found.")
    return redirect("accounts:user_detail", pk=pk)
