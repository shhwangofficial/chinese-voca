from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.http import HttpResponse
from datetime import timedelta
from .models import Word
from accounts.models import LearningWord
from .forms import WordForm, LearnWordForm
from newpjt.settings import CACHE_TTL
import unicodedata


@require_http_methods(["GET"])
def index(request):
    if request.user.is_authenticated:
        user = request.user
        
        # 사용자별 캐시 키 생성 (날짜 포함)
        today = timezone.now().date()
        cache_key_stats = f'user_stats_{user.id}_{today}'
        cache_key_recent = f'user_recent_words_{user.id}_{today}'
        cache_key_today = f'user_today_words_{user.id}_{today}'
        
        # 캐시에서 데이터 가져오기
        cached_stats = cache.get(cache_key_stats)
        cached_recent = cache.get(cache_key_recent)
        cached_today = cache.get(cache_key_today)
        
        if cached_stats is None:
            # 사용자 학습 통계
            total_learning_words = user.learning.count()
            today_review_words = user.learning.filter(
                learningword__to_be_revised__lt=timezone.now()
            ).count()
            
            cached_stats = {
                'total_learning_words': total_learning_words,
                'today_review_words': today_review_words
            }
            cache.set(cache_key_stats, cached_stats, CACHE_TTL)
        
        if cached_recent is None:
            # 최근 학습한 단어들 (최근 5개) - LearningWord 객체와 함께
            recent_words = user.learningword_set.select_related('word').order_by('-learning_since')[:5]
            
            # 각 단어의 추가 일수 계산
            for learning_word in recent_words:
                if learning_word.learning_since:
                    # 날짜만 비교하기 위해 날짜 부분만 추출
                    today = timezone.now().date()
                    learning_date = learning_word.learning_since.date()
                    days_diff = (today - learning_date).days
                    if days_diff == 0:
                        learning_word.days_since_added = "오늘"
                    elif days_diff == 1:
                        learning_word.days_since_added = "어제"
                    else:
                        learning_word.days_since_added = f"{days_diff}일 전"
                else:
                    learning_word.days_since_added = "알 수 없음"
            
            cached_recent = recent_words
            cache.set(cache_key_recent, cached_recent, CACHE_TTL)
        
        if cached_today is None:
            # 오늘 복습해야 할 단어들 (최근 5개) - LearningWord 객체와 함께
            today_words = user.learningword_set.filter(
                to_be_revised__lt=timezone.now()
            ).select_related('word').order_by('to_be_revised')[:5]
            
            # 각 단어의 학습 일수 계산
            for learning_word in today_words:
                # 정답/오답 횟수가 모두 0이면 첫 복습
                if learning_word.correct_count == 0 and learning_word.wrong_count == 0:
                    learning_word.days_since_revision = "첫 복습"
                elif learning_word.last_time_revised:
                    # 날짜만 비교하기 위해 날짜 부분만 추출
                    today = timezone.now().date()
                    revision_date = learning_word.last_time_revised.date()
                    days_diff = (today - revision_date).days
                    if days_diff == 0:
                        learning_word.days_since_revision = "오늘"
                    elif days_diff == 1:
                        learning_word.days_since_revision = "어제"
                    else:
                        learning_word.days_since_revision = f"{days_diff}일 전"
                else:
                    learning_word.days_since_revision = "첫 복습"
            
            cached_today = today_words
            cache.set(cache_key_today, cached_today, CACHE_TTL)
        
        context = {
            'total_learning_words': cached_stats['total_learning_words'],
            'today_review_words': cached_stats['today_review_words'],
            'recent_words': cached_recent,
            'today_words': cached_today,
        }
        response = render(request, "words/index.html", context)
        # 캐시 방지 헤더 추가
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    else:
        return redirect("accounts:login")


@require_http_methods(["GET"])
def quiz(request):
    user = request.user
    
    # 오답만 다시 출제: retry_pks가 있으면 해당 단어만 출제
    retry_pks = request.GET.getlist("retry_pks")
    if retry_pks:
        words = Word.objects.filter(pk__in=retry_pks)
        if not words:
            messages.info(request, "틀린 문제가 없습니다. 모두 정답입니다!")
            return redirect("words:index")
        context = {"words": words}
        response = render(request, "words/quiz.html", context)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    # 학습 중인 단어가 0개인지 확인
    total_learning_words = user.learning.count()
    if total_learning_words == 0:
        messages.warning(request, "학습 중인 단어가 없습니다. 먼저 단어를 추가해주세요.")
        return redirect("words:index")
    
    # 퀴즈 문제 수 처리 - 기본값 5로 설정
    try:
        num_quiz = int(request.GET.get("num_quiz", 5))
    except (TypeError, ValueError):
        num_quiz = 5
    
    # 문제 수가 0 이하이거나 20을 초과하면 기본값 5로 설정
    if num_quiz <= 0 or num_quiz > 20:
        num_quiz = 5
    
    # 항상 fresh하게 DB에서 문제를 뽑아옴 (캐시 사용 안함)
    words = user.learning.filter(
        learningword__to_be_revised__lt=timezone.now()
    ).order_by("learningword__to_be_revised")[:num_quiz]
    
    # 복습할 단어가 없으면 알림
    if not words:
        messages.info(request, "오늘 복습할 단어가 없습니다. 내일 다시 시도해보세요.")
        return redirect("words:index")
    
    context = {"words": words}
    response = render(request, "words/quiz.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_http_methods(["GET", "POST"])
def grade(request):
    user = request.user
    if request.method == "POST":
        results = {}
        for key in request.POST:
            if key.startswith("quizno_"):
                pk = key.split("_")[1]
                cache_key = f'word_{pk}'
                ans_word = cache.get(cache_key)
                
                if ans_word is None:
                    try:
                        ans_word = Word.objects.get(pk=pk)
                        cache.set(cache_key, ans_word, CACHE_TTL)
                    except Word.DoesNotExist:
                        continue

                quiz_no = request.POST.get(f"quizno_{pk}", "").strip()
                user_pinyin = request.POST.get(f"pinyin_{pk}", "").strip()
                user_tone = request.POST.get(f"tone_{pk}", "").strip()
                user_meaning = request.POST.get(f"meaning_{pk}", "").strip()

                is_correct = (
                    user_pinyin == ans_word.pinyin
                    and
                    # user_tone == ans_word.tone and
                    user_meaning == ans_word.meaning
                )

                learning = LearningWord.objects.get(user=user, word=ans_word)
                learning.no_of_revision += 1
                learning.last_time_revised = timezone.now()  # 마지막 복습 시간 업데이트
                if is_correct:
                    new_learning_term = learning.learning_term * 2 + 1
                    learning.correct_count += 1
                else:
                    new_learning_term = 0
                    learning.wrong_count += 1
                learning.to_be_revised = timezone.now() + timedelta(
                    days=new_learning_term
                )
                learning.learning_term = new_learning_term
                learning.save()

                # Clear related caches
                cache.delete(cache_key)

                # results의 key를 Word의 pk(정수)로 저장
                results[str(ans_word.pk)] = [
                    is_correct,
                    ans_word.word,
                    [ans_word.pinyin, ans_word.tone, ans_word.meaning],
                    [user_pinyin, user_tone, user_meaning],
                    "",
                ]
        # 캐시 삭제: index의 정답/오답/통계가 바로 반영되도록
        cache.delete(f'user_stats_{user.id}')
        cache.delete(f'user_recent_words_{user.id}')
        cache.delete(f'user_today_words_{user.id}')
        request.session["grade_results"] = results
        return redirect("words:grade")

    results = request.session.pop("grade_results", None)  # 사용 후 삭제
    
    # 결과 통계 계산
    if results:
        total_questions = len(results)
        correct_count = sum(1 for data in results.values() if data[0])
        wrong_count = total_questions - correct_count
        accuracy_rate = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
    else:
        total_questions = 0
        correct_count = 0
        wrong_count = 0
        accuracy_rate = 0
    
    context = {
        "results": results,
        "total_questions": total_questions,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "accuracy_rate": accuracy_rate,
    }
    
    response = render(request, "words/result.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_http_methods(["GET", "POST"])
def add(request):
    user = request.user
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "LearnWord":
            form = LearnWordForm(request.POST)
            if form.is_valid():
                word = form.cleaned_data["word"]
                # 입력값 정규화
                word = unicodedata.normalize('NFC', word.strip())
                cache_key = f'word_lookup_{word}'
                found_word = cache.get(cache_key)
                
                if found_word is None:
                    found_word = Word.objects.filter(word=word).first()
                    if found_word:
                        cache.set(cache_key, found_word, CACHE_TTL)
                
                if found_word:
                    if user.learning.filter(word=word).exists():
                        messages.warning(request, f"'{word}'는 이미 학습 목록에 있습니다.")
                    else:
                        # 새로 추가된 단어는 즉시 복습할 수 있도록 과거 시간으로 설정
                        to_be_revised = timezone.now() - timedelta(hours=1)
                        LearningWord.objects.create(
                            user=user, word=found_word, to_be_revised=to_be_revised
                        )
                        # 관련 캐시 삭제하여 메인 페이지에서 즉시 반영
                        cache.delete(f'user_stats_{user.id}')
                        cache.delete(f'user_today_words_{user.id}')
                        cache.delete(f'user_recent_words_{user.id}')
                        messages.success(request, f"'{word}'를 학습 목록에 추가했습니다.")
                    return redirect("words:add")
                else:
                    messages.error(request, f"'{word}'는 DB에 존재하지 않아서 직접 추가해야 합니다.")
                    request.session["added_word"] = word
                    form = WordForm()
                    form_type = "Word"
                    added_word = word

        elif form_type == "Word":
            form = WordForm(request.POST)
            added_word = request.session.get("added_word")
            if form.is_valid():
                word = added_word
                if word:
                    # 폼 데이터로 Word 객체 생성
                    word_obj = form.save(commit=False)
                    word_obj.word = word
                    word_obj.save()
                    
                    # Clear related caches
                    cache.delete(f'word_lookup_{word}')
                    # Note: LocMemCache doesn't support delete_pattern, so we clear specific keys
                    
                    # 자동으로 학습 목록에 추가
                    if user.learning.filter(word=word).exists():
                        messages.warning(request, f"'{word}'는 이미 학습 목록에 있습니다.")
                    else:
                        # 새로 추가된 단어는 즉시 복습할 수 있도록 과거 시간으로 설정
                        to_be_revised = timezone.now() - timedelta(hours=1)
                        LearningWord.objects.create(
                            user=user, word=word_obj, to_be_revised=to_be_revised
                        )
                        # 관련 캐시 삭제하여 메인 페이지에서 즉시 반영
                        cache.delete(f'user_stats_{user.id}')
                        cache.delete(f'user_today_words_{user.id}')
                        cache.delete(f'user_recent_words_{user.id}')
                        messages.success(request, f"'{word}'가 데이터베이스에 추가되고 학습 목록에도 추가되었습니다.")
                    
                    return redirect("words:add")
                else:
                    messages.error(request, "단어 정보를 찾을 수 없습니다.")
                    return redirect("words:add")
            else:
                # 폼이 유효하지 않을 때는 word 변수가 정의되지 않을 수 있으므로 안전하게 처리
                word_value = request.POST.get('word', '알 수 없는 단어')
                messages.error(request, f"{word_value}를 데이터베이스로 추가에 실패했습니다.")
    else:
        added_word = request.session.pop("added_word", None)
        if added_word:
            form = LearnWordForm(initial={"word": added_word})
            form_type = "LearnWord"
        else:
            form = LearnWordForm()
            form_type = "LearnWord"
            added_word = None

    context = {
        "form": form,
        "form_type": form_type,
        "added_word": added_word,
    }
    response = render(request, "words/add.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response



