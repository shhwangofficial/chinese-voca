from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.http import HttpResponse
from datetime import timedelta, datetime
from django.db.models import Count, Q, F, ExpressionWrapper, DateTimeField
from django.db.models.functions import TruncDate
import math
import re
from .models import Word
from accounts.models import LearningWord, StudyLog
from .forms import WordForm, LearnWordForm
from newpjt.settings import CACHE_TTL
import unicodedata


@require_http_methods(["GET"])
def index(request):
    if request.user.is_authenticated:
        user = request.user
        
        # 사용자별 캐시 키 생성
        cache_key_stats = f'user_stats_{user.id}'
        cache_key_recent = f'user_recent_words_{user.id}'
        cache_key_today = f'user_today_words_{user.id}'
        cache_key_weekly = f'user_weekly_stats_{user.id}'
        
        # 캐시에서 데이터 가져오기
        cached_stats = cache.get(cache_key_stats)
        cached_recent = cache.get(cache_key_recent)
        cached_today = cache.get(cache_key_today)
        cached_weekly = cache.get(cache_key_weekly)
        
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
        
        if cached_weekly is None:
            # 최근 일주일 통계 계산 (4시 기준)
            # 현재 시간에서 4시간을 뺀 시간을 기준으로 날짜 계산
            stats_now = timezone.now() - timedelta(hours=4)
            today = stats_now.date()
            week_ago = today - timedelta(days=6)  # 오늘 포함 7일
            
            # 일주일간 날짜 리스트 생성
            date_list = [week_ago + timedelta(days=i) for i in range(7)]
            
            # 날짜별 추가한 단어 수
            # DB 레코드 시간도 4시간 빼고 날짜로 변환해야 함
            words_added_by_date = (
                user.learningword_set
                .annotate(
                    adjusted_time=ExpressionWrapper(
                        F('learning_since') - timedelta(hours=4),
                        output_field=DateTimeField()
                    )
                )
                .filter(adjusted_time__date__gte=week_ago, adjusted_time__date__lte=today)
                .annotate(date=TruncDate('adjusted_time'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            added_dict = {item['date']: item['count'] for item in words_added_by_date}
            
            # 날짜별 맞은 단어 수 (StudyLog 기준)
            # StudyLog는 이미 date 필드가 "논리적 날짜"를 가지고 있으므로 바로 집계 가능
            words_correct_by_date = (
                StudyLog.objects
                .filter(
                    user=user,
                    date__gte=week_ago,
                    date__lte=today,
                    is_correct=True
                )
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            correct_dict = {item['date']: item['count'] for item in words_correct_by_date}
            
            # 모든 날짜에 대해 데이터 생성 (없으면 0)
            weekly_stats = []
            for date in date_list:
                weekly_stats.append({
                    'date': date,
                    'date_str': date.strftime('%m/%d'),
                    'day_name': ['월', '화', '수', '목', '금', '토', '일'][date.weekday()],
                    'words_added': added_dict.get(date, 0),
                    'words_correct': correct_dict.get(date, 0),
                })
            
            cached_weekly = weekly_stats
            cache.set(cache_key_weekly, cached_weekly, CACHE_TTL)
        
        context = {
            'total_learning_words': cached_stats['total_learning_words'],
            'today_review_words': cached_stats['today_review_words'],
            'recent_words': cached_recent,
            'today_words': cached_today,
            'weekly_stats': cached_weekly,
            'today': timezone.now().date(),
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
    # 랜덤 순서로 퀴즈 문제 출제
    words = user.learning.filter(
        learningword__to_be_revised__lt=timezone.now()
    ).order_by("?")[:num_quiz]
    
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
                try:
                    ans_word = Word.objects.get(pk=pk)
                except Word.DoesNotExist:
                    continue

                quiz_no = request.POST.get(f"quizno_{pk}", "").strip()
                user_pinyin = request.POST.get(f"pinyin_{pk}", "").strip()
                user_tone = request.POST.get(f"tone_{pk}", "").strip()
                user_meaning = request.POST.get(f"meaning_{pk}", "").strip()

                # 병음과 의미의 공백 정규화 (여러 공백을 하나로, 앞뒤 공백 제거)
                user_pinyin_normalized = re.sub(r'\s+', ' ', user_pinyin).strip()
                user_meaning_normalized = re.sub(r'\s+', ' ', user_meaning).strip()
                ans_pinyin_normalized = re.sub(r'\s+', ' ', ans_word.pinyin).strip()
                ans_meaning_normalized = re.sub(r'\s+', ' ', ans_word.meaning).strip()

                is_correct = (
                    user_pinyin_normalized == ans_pinyin_normalized
                    and
                    # user_tone == ans_word.tone and
                    user_meaning_normalized == ans_meaning_normalized
                )

                learning = LearningWord.objects.get(user=user, word=ans_word)
                learning.no_of_revision += 1
                learning.last_time_revised = timezone.now()  # 마지막 복습 시간 업데이트
                
                # StudyLog 생성
                # 현재 시간에서 4시간을 빼서 "논리적 오늘"을 구함
                log_date = (timezone.now() - timedelta(hours=4)).date()
                StudyLog.objects.create(
                    user=user,
                    word=ans_word,
                    is_correct=is_correct,
                    date=log_date
                )

                if is_correct:
                    # 정답일 때: 틀린 횟수에 따라 승수를 2→1.5로 점진적으로 낮추는 로지스틱형 보정
                    # m = c + (2 - c) / (1 + wrong_count), 여기서 c는 1.5로 고정
                    updated_wrong = learning.wrong_count
                    learning.correct_count += 1
                    
                    base_multiplier = 1.5
                    multiplier = base_multiplier + (2 - base_multiplier) / (1 + updated_wrong)
                    new_learning_term = math.ceil(learning.learning_term * multiplier + 1)
                    # learning_term일 후의 04시로 설정 (4시부터 퀴즈 가능)
                    # 현재 시간에서 4시간을 빼서 "논리적 오늘"을 구함
                    logical_today = (timezone.now() - timedelta(hours=4)).date()
                    target_date = logical_today + timedelta(days=new_learning_term)
                    # target_date의 04:00:00으로 설정
                    learning.to_be_revised = timezone.make_aware(datetime.combine(target_date, datetime.min.time())) + timedelta(hours=4)
                    learning.learning_term = new_learning_term
                else:
                    # 오답일 때: 다음날 즉시 복습
                    learning.wrong_count += 1
                    new_learning_term = 0
                    # 현재 시간에서 4시간을 빼서 "논리적 오늘"을 구함
                    logical_today = (timezone.now() - timedelta(hours=4)).date()
                    target_date = logical_today + timedelta(days=new_learning_term)
                    # target_date의 04:00:00으로 설정
                    learning.to_be_revised = timezone.make_aware(datetime.combine(target_date, datetime.min.time())) + timedelta(hours=4)
                    learning.learning_term = new_learning_term
                
                learning.save()

                # results의 key를 Word의 pk(정수)로 저장
                results[str(ans_word.pk)] = [
                    is_correct,
                    ans_word.word,
                    [ans_word.pinyin, ans_word.tone, ans_word.meaning],
                    [user_pinyin, user_tone, user_meaning],
                    "",
                    ans_word.get_word_class_display(),
                ]
        # 캐시 삭제: index의 정답/오답/통계가 바로 반영되도록
        cache.delete(f'user_stats_{user.id}')
        cache.delete(f'user_recent_words_{user.id}')
        cache.delete(f'user_today_words_{user.id}')
        cache.delete(f'user_weekly_stats_{user.id}')
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
    added_word = None
    added_word_class = None

    def set_word_field_readonly(word_form):
        word_field = word_form.fields.get("word")
        if word_field:
            existing_class = word_field.widget.attrs.get("class", "")
            word_field.widget.attrs["readonly"] = True
            word_field.widget.attrs["class"] = f"{existing_class} readonly-input".strip()
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "LearnWord":
            form = LearnWordForm(request.POST)
            if form.is_valid():
                word = form.cleaned_data["word"]
                word_class = form.cleaned_data["word_class"]
                # 입력값 정규화
                word = unicodedata.normalize('NFC', word.strip())
                found_word = Word.objects.filter(word=word, word_class=word_class).first()

                word_class_label = dict(Word.WORD_CLASS_CHOICES).get(word_class, word_class)

                if found_word:
                    if LearningWord.objects.filter(user=user, word=found_word).exists():
                        messages.warning(
                            request,
                            f"'{word}' ({word_class_label})는 이미 학습 목록에 있습니다.",
                        )
                        form_type = "LearnWord"
                    else:
                        # 새로 추가된 단어는 즉시 복습할 수 있도록 과거 시간으로 설정
                        to_be_revised = timezone.now() - timedelta(hours=1)
                        LearningWord.objects.create(
                            user=user, word=found_word, to_be_revised=to_be_revised
                        )
                        # 관련 캐시 삭제하여 메인 페이지에서 즉시 반영
                        cache.delete(f'user_stats_{user.id}')
                        cache.delete(f'user_recent_words_{user.id}')
                        cache.delete(f'user_today_words_{user.id}')
                        cache.delete(f'user_weekly_stats_{user.id}')
                        # 세션에서 added_word 정리
                        request.session.pop("added_word", None)
                        request.session.pop("added_word_class", None)
                        messages.success(
                            request,
                            f"'{word}' ({word_class_label})를 학습 목록에 추가했습니다.",
                        )
                        form = LearnWordForm()
                        form_type = "LearnWord"
                        added_word = None
                        added_word_class = None
                else:
                    messages.error(
                        request,
                        f"'{word}' ({word_class_label})는 DB에 존재하지 않아서 직접 추가해야 합니다.",
                    )
                    request.session["added_word"] = word
                    request.session["added_word_class"] = word_class
                    form = WordForm(initial={"word": word, "word_class": word_class})
                    set_word_field_readonly(form)
                    form_type = "Word"
                    added_word = word
                    added_word_class = word_class

        elif form_type == "Word":
            form = WordForm(request.POST)
            set_word_field_readonly(form)
            added_word = request.session.get("added_word")
            added_word_class = request.session.get("added_word_class")
            if form.is_valid():
                word = unicodedata.normalize('NFC', form.cleaned_data["word"].strip())
                word_class = form.cleaned_data["word_class"]
                word_class_label = dict(Word.WORD_CLASS_CHOICES).get(word_class, word_class)

                existing_word = Word.objects.filter(word=word, word_class=word_class).first()

                if existing_word:
                    # 기존 단어 정보 업데이트
                    existing_word.pinyin = form.cleaned_data["pinyin"]
                    existing_word.tone = form.cleaned_data["tone"]
                    existing_word.meaning = form.cleaned_data["meaning"]
                    existing_word.save()
                    word_obj = existing_word
                else:
                    word_obj = form.save(commit=False)
                    word_obj.word = word
                    word_obj.word_class = word_class
                    word_obj.save()

                if LearningWord.objects.filter(user=user, word=word_obj).exists():
                    messages.warning(
                        request,
                        f"'{word}' ({word_class_label})는 이미 학습 목록에 있습니다.",
                    )
                else:
                    # 새로 추가된 단어는 즉시 복습할 수 있도록 과거 시간으로 설정
                    to_be_revised = timezone.now() - timedelta(hours=1)
                    LearningWord.objects.create(
                        user=user, word=word_obj, to_be_revised=to_be_revised
                    )
                    # 관련 캐시 삭제하여 메인 페이지에서 즉시 반영
                    cache.delete(f'user_stats_{user.id}')
                    cache.delete(f'user_recent_words_{user.id}')
                    cache.delete(f'user_today_words_{user.id}')
                    cache.delete(f'user_weekly_stats_{user.id}')
                    # 세션에서 added_word 정리
                    request.session.pop("added_word", None)
                    request.session.pop("added_word_class", None)
                    messages.success(
                        request,
                        f"'{word}' ({word_class_label})가 데이터베이스에 추가되고 학습 목록에도 추가되었습니다.",
                    )

                return redirect("words:add")
            else:
                # 폼이 유효하지 않을 때는 word 변수가 정의되지 않을 수 있으므로 안전하게 처리
                word_value = request.POST.get('word', '알 수 없는 단어')
                word_class_value = request.POST.get('word_class', '알 수 없는 품사')
                messages.error(
                    request,
                    f"{word_value} ({word_class_value})를 데이터베이스로 추가에 실패했습니다.",
                )
    else:
        added_word = request.session.pop("added_word", None)
        added_word_class = request.session.pop("added_word_class", None)
        if added_word:
            form = LearnWordForm(initial={"word": added_word, "word_class": added_word_class})
            form_type = "LearnWord"
        else:
            form = LearnWordForm()
            form_type = "LearnWord"
            added_word = None
            added_word_class = None

    context = {
        "form": form,
        "form_type": form_type,
        "added_word": added_word,
        "added_word_class": added_word_class,
    }
    response = render(request, "words/add.html", context)
    # 캐시 방지 헤더 추가
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response



