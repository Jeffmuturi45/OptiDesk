from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/", views.reset_password, name="reset_password"),
    path("profile/", views.profile, name="profile"),
    path("change-password/", views.change_password, name="change_password"),

    # Admin: user management
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/toggle-active/",
         views.user_toggle_active, name="user_toggle_active"),
    path("users/<int:pk>/generate-recovery/",
         views.generate_recovery_code, name="generate_recovery"),
    path("users/<int:pk>/download-recovery/",
         views.download_recovery_file, name="download_recovery"),
    path("users/<int:pk>/revoke-recovery/",
         views.revoke_recovery_code, name="revoke_recovery"),
]
