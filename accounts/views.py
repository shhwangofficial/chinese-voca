from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.views.decorators.http import require_http_methods, require_POST
from django.core.cache import cache
from django.contrib import messages


@require_http_methods(["GET", "POST"])
def login(request):
    if request.user.is_authenticated:
        return redirect("words:index")
    
    error_message = None
    if request.method == "POST":
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect("words:index")
        else:
            error_message = "사용자명 또는 비밀번호가 올바르지 않습니다. 다시 시도해주세요."
    else:
        form = AuthenticationForm()
    
    context = {
        "form": form,
        "error_message": error_message
    }
    response = render(request, "accounts/login.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_http_methods(["GET", "POST"])
def logout(request):
    # 사용자 ID 저장 (로그아웃 후 캐시 정리용)
    user_id = request.user.id if request.user.is_authenticated else None
    
    # Django 인증 로그아웃
    auth_logout(request)
    
    # 세션 데이터 완전 정리
    request.session.flush()
    
    # 사용자 관련 캐시 정리
    if user_id:
        # LocMemCache는 delete_pattern을 지원하지 않으므로 개별 키 삭제
        # 퀴즈 관련 캐시들 삭제 (일반적인 패턴들)
        for i in range(1, 21):  # 1-20문제 퀴즈 캐시
            cache.delete(f'quiz_words_{user_id}_{i}')
        # 기타 사용자 관련 캐시들 삭제
        cache.delete(f'user_stats_{user_id}')
        cache.delete(f'user_recent_words_{user_id}')
        cache.delete(f'user_today_words_{user_id}')
    
    # 모든 캐시 완전 정리 (더 확실한 방법)
    cache.clear()
    
    # 성공 메시지 추가
    messages.success(request, "안전하게 로그아웃되었습니다.")
    
    return redirect("accounts:login")


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("words:index")
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("words:index")
    else:
        form = CustomUserCreationForm()
    context = {
        "form": form,
    }
    response = render(request, "accounts/signup.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
