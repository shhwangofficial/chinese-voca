from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password.html",
            success_url=reverse_lazy("words:index"),
        ),
        name="password_change",
    ),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("signup/", views.signup, name="signup"),
]
