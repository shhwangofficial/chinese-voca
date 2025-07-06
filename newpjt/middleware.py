from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 로그인한 사용자거나 관리자 페이지 접근 시 무시
        if request.user.is_authenticated or request.path.startswith("/admin/"):
            return self.get_response(request)

        # 현재 접근 중인 URL 이름
        resolver_match = resolve(request.path)
        url_name = resolver_match.url_name
        app_name = resolver_match.app_name

        # 로그인 없이 허용할 url 이름들
        exempt_urls = [
            ("accounts", "login"),
            ("accounts", "signup"),
        ]

        if (app_name, url_name) not in exempt_urls:
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
