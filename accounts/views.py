from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import OperationalError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CustomUserCreationForm
from .security import allow_attempt


def safe_next(request):
    target = request.POST.get("next") or request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return "words:index"


def throttle(request, signup=False):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    try:
        if not allow_attempt(
            "signup" if signup else "login-ip", ip, 20 if signup else 100
        ):
            return False
        return signup or allow_attempt(
            "login-user", request.POST.get("username", "").strip().casefold()[:150], 10
        )
    except OperationalError:
        return False


@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def login(request):
    if request.user.is_authenticated:
        return redirect("words:index")
    form = AuthenticationForm(request, data=request.POST or None)
    error_message = None
    status = 200
    if request.method == "POST":
        if not throttle(request):
            error_message = "시도가 너무 많습니다. 15분 후 다시 시도해주세요."
            status = 429
        elif form.is_valid():
            auth_login(request, form.get_user())
            return redirect(safe_next(request))
        else:
            error_message = "사용자명 또는 비밀번호가 올바르지 않습니다."
    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "error_message": error_message,
            "next": request.GET.get("next", ""),
        },
        status=status,
    )


@require_POST
def logout(request):
    auth_logout(request)
    messages.success(request, "로그아웃되었습니다.")
    return redirect("accounts:login")


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("words:index")
    form = CustomUserCreationForm(request.POST or None)
    status = 200
    if request.method == "POST":
        if not throttle(request, signup=True):
            form.add_error(
                None, "가입 시도가 너무 많습니다. 15분 후 다시 시도해주세요."
            )
            status = 429
        elif form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("words:index")
    return render(request, "accounts/signup.html", {"form": form}, status=status)
