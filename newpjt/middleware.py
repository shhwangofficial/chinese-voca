from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.urls import Resolver404, resolve
from django.utils.cache import patch_cache_control


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            try:
                match = resolve(request.path_info)
            except Resolver404:
                return self.get_response(request)
            public = match.view_name in {"accounts:login", "accounts:signup"}
            if not public and not request.path_info.startswith("/admin/"):
                if request.path_info.startswith("/words/api/"):
                    return JsonResponse(
                        {"status": "error", "message": "다시 로그인해주세요."},
                        status=401,
                    )
                return redirect_to_login(request.get_full_path())
        response = self.get_response(request)
        patch_cache_control(response, private=True, no_store=True)
        return response
