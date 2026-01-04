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
        
        # 한국 시간 기준 현재 시간 구하기
        now_kst = timezone.localtime()
        # 4시간을 빼서 "논리적 오늘" 날짜 구하기 (오전 4시 기준 날짜 변경)
        logical_date = (now_kst - timedelta(hours=4)).date()
        logical_date_str = logical_date.strftime("%Y-%m-%d")

        # 사용자별 캐시 키 생성 (날짜 포함)
        cache_key_stats = f'user_stats_{user.id}_{logical_date_str}'
        cache_key_recent = f'user_recent_words_{user.id}_{logical_date_str}'
        cache_key_today = f'user_today_words_{user.id}_{logical_date_str}'
        cache_key_weekly = f'user_weekly_stats_{user.id}_{logical_date_str}'
        
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
            # KST 기준으로 계산해야 함
            now = timezone.localtime()
            stats_now = now - timedelta(hours=4)
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
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    user = request.user
    
    # 학습 중인 단어가 0개인지 확인
    total_learning_words = user.learning.count()
    if total_learning_words == 0:
        messages.warning(request, "학습 중인 단어가 없습니다. 먼저 단어를 추가해주세요.")
        return redirect("words:index")
    
    # 퀴즈 문제 수 처리 - 입력값 무시하고 전체 출제 (랜덤)
    # 항상 fresh하게 DB에서 문제를 뽑아옴 (캐시 사용 안함)
    # 오늘 복습해야 할 단어 전체 (to_be_revised <= now)
    
    # KST 기준 '오늘'의 범위 등을 고려해야 하지만, 
    # to_be_revised 필드 자체가 '언제부터 복습 가능'을 나타내므로
    # 단순히 현재 시간보다 이전인 것을 가져오면 됨
    
    quiz_queryset = user.learningword_set.filter(
        to_be_revised__lt=timezone.now()
    ).select_related('word').order_by("?")
    
    # 만약 복습할게 없으면? 
    if not quiz_queryset.exists():
        messages.info(request, "오늘 복습할 단어가 없습니다. 내일 다시 시도해보세요.")
        return redirect("words:index")
        
    # Serialize for Frontend SPA
    words_data = []
    for lw in quiz_queryset:
        # Pinyin tone normalization for display if needed? 
        # Actually we just pass raw, frontend handles input
        words_data.append({
            'id': lw.word.id,
            'word': lw.word.word,
            'pinyin': lw.word.pinyin,
            'tone': lw.word.tone,
            'meaning': lw.word.meaning,
            'meaning_length': lw.word.meaning_length,
            'word_class': lw.word.get_word_class_display(),
        })
    
    context = {
        "words_data_json": json.dumps(words_data, cls=DjangoJSONEncoder)
    }
    
    response = render(request, "words/quiz.html", context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_http_methods(["POST"])
def api_grade_word(request):
    import json
    from django.http import JsonResponse
    
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Login required'}, status=401)
        
    try:
        data = json.loads(request.body)
        word_id = data.get('word_id')
        user_pinyin = data.get('pinyin', '').strip()
        user_meaning = data.get('meaning', '').strip()
    except:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        
    try:
        ans_word = Word.objects.get(pk=word_id)
        learning = LearningWord.objects.get(user=user, word=ans_word)
    except (Word.DoesNotExist, LearningWord.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Word not found'}, status=404)

    # 병음과 의미의 공백 정규화
    user_pinyin_normalized = re.sub(r'\s+', ' ', user_pinyin).strip().lower()
    user_meaning_normalized = re.sub(r'\s+', ' ', user_meaning).strip()
    ans_pinyin_normalized = re.sub(r'\s+', ' ', ans_word.pinyin).strip().lower()
    
    # 의미 정답 처리 로직
    ans_meaning_normalized = re.sub(r'\s+', ' ', ans_word.meaning).strip()

    is_correct_pinyin = (user_pinyin_normalized == ans_pinyin_normalized)
    is_correct_meaning = (user_meaning_normalized == ans_meaning_normalized)
    
    is_correct = is_correct_pinyin and is_correct_meaning

    current_learning_term = learning.learning_term
    
    if is_correct:
         learning.no_of_revision += 1
         learning.last_time_revised = timezone.now()
         
         # StudyLog (KST -4h offset logic)
         log_date = (timezone.localtime() - timedelta(hours=4)).date()
         StudyLog.objects.create(
             user=user,
             word=ans_word,
             is_correct=True,
             date=log_date
         )
         
         # Correct Logic (Logistic Correction)
         updated_wrong = learning.wrong_count
         learning.correct_count += 1
         
         base_multiplier = 1.5
         multiplier = base_multiplier + (2 - base_multiplier) / (1 + updated_wrong)
         
         # Calculate new_learning_term (Future Cycle)
         # If term was 0 (new/failed), next term becomes 1.
         if current_learning_term == 0:
             next_review_delta = 1
             new_learning_term = 1
         else:
             # If term > 0, we use the current term as the delta ("Review in n days")
             # And calculate the next term for the future.
             next_review_delta = current_learning_term
             new_learning_term = math.ceil(current_learning_term * multiplier + 1)
         
         # Schedule next review
         logical_today = (timezone.localtime() - timedelta(hours=4)).date()
         target_date = logical_today + timedelta(days=next_review_delta)
         
         # Save results
         learning.to_be_revised = timezone.make_aware(datetime.combine(target_date, datetime.min.time())) + timedelta(hours=4)
         learning.learning_term = new_learning_term
         learning.save()
         
         # Cache Invalidation (Update Homepage Stats)
         now_kst = timezone.localtime()
         logical_date_str = (now_kst - timedelta(hours=4)).date().strftime("%Y-%m-%d")
         cache.delete(f'user_stats_{user.id}_{logical_date_str}')
         cache.delete(f'user_today_words_{user.id}_{logical_date_str}')
         cache.delete(f'user_weekly_stats_{user.id}_{logical_date_str}')
         cache.delete(f'user_recent_words_{user.id}_{logical_date_str}')
         
         return JsonResponse({
             'status': 'success',
             'is_correct': True,
             'message': 'Correct!',
             'next_review_delta': next_review_delta
         })
         
    else:
         # 틀림
         learning.no_of_revision += 1
         learning.last_time_revised = timezone.now()
         
         log_date = (timezone.localtime() - timedelta(hours=4)).date()
         StudyLog.objects.create(
             user=user,
             word=ans_word,
             is_correct=False,
             date=log_date
         )
         
         # 틀렸을 때의 패널티
         learning.wrong_count += 1
         # Store original term before resetting, to send to frontend for "undo"
         original_learning_term = learning.learning_term 
         
         learning.learning_term = 0
         learning.to_be_revised = timezone.now() # 복습 시간은 현재로
         learning.save()
         
         # Cache Invalidation
         now_kst = timezone.localtime()
         logical_date_str = (now_kst - timedelta(hours=4)).date().strftime("%Y-%m-%d")
         cache.delete(f'user_stats_{user.id}_{logical_date_str}')
         cache.delete(f'user_today_words_{user.id}_{logical_date_str}')
         cache.delete(f'user_weekly_stats_{user.id}_{logical_date_str}')
         cache.delete(f'user_recent_words_{user.id}_{logical_date_str}')
         
         return JsonResponse({
             'status': 'success',
             'is_correct': False,
             'correct_pinyin': ans_word.pinyin,
             'correct_meaning': ans_word.meaning,
             'word_tone': ans_word.tone,
              # Return answer details for UI feedback
              'word': ans_word.word,
              'original_learning_term': original_learning_term
         })



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
                        now_kst = timezone.localtime()
                        logical_date_str = (now_kst - timedelta(hours=4)).date().strftime("%Y-%m-%d")
                        cache.delete(f'user_stats_{user.id}_{logical_date_str}')
                        cache.delete(f'user_recent_words_{user.id}_{logical_date_str}')
                        cache.delete(f'user_today_words_{user.id}_{logical_date_str}')
                        cache.delete(f'user_weekly_stats_{user.id}_{logical_date_str}')
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
                    now_kst = timezone.localtime()
                    logical_date_str = (now_kst - timedelta(hours=4)).date().strftime("%Y-%m-%d")
                    cache.delete(f'user_stats_{user.id}_{logical_date_str}')
                    cache.delete(f'user_recent_words_{user.id}_{logical_date_str}')
                    cache.delete(f'user_today_words_{user.id}_{logical_date_str}')
                    cache.delete(f'user_weekly_stats_{user.id}_{logical_date_str}')
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




@require_http_methods(["GET"])
def flashcard_list(request):
    import random
    user = request.user
    if not user.is_authenticated:
        return redirect("accounts:login")

    # Fetch all learning words for the user
    # User requested random order, fixed per session (upon entry)
    # So we fetch all, then shuffle.
    learning_words_queryset = LearningWord.objects.filter(user=user, wrong_count__gt=0).select_related('word')

    if not learning_words_queryset.exists():
        messages.warning(request, "학습 중인 단어가 없습니다.")
        return redirect("words:index")

    learning_words = list(learning_words_queryset)
    random.shuffle(learning_words)

    # Serialize data for frontend
    words_data = []
    for lw in learning_words:
        words_data.append({
            'word': lw.word.word,
            'pinyin': lw.word.pinyin,
            'tone': lw.word.tone,
            'meaning': lw.word.meaning,
            'word_class': lw.word.get_word_class_display(),
            'wrong_count': lw.wrong_count,
            'correct_count': lw.correct_count,
        })
    
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    context = {
        'words_data_json': json.dumps(words_data, cls=DjangoJSONEncoder)
    }
    
    return render(request, "words/flashcard.html", context)


@require_http_methods(["POST"])
def api_mark_as_correct(request):
    import json
    from django.http import JsonResponse
    
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Login required'}, status=401)
        
    try:
        data = json.loads(request.body)
        word_id = data.get('word_id')
        # We need original term to restore state before applying "correct" logic properly
        # However, if we just want to treat it as "correct now", we can just
        # undo the "wrong" penalty and apply "correct" logic.
        # But "wrong" logic set term to 0. We need to know what it was.
        original_term = data.get('original_learning_term', 0)
    except:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    try:
        ans_word = Word.objects.get(pk=word_id)
        learning = LearningWord.objects.get(user=user, word=ans_word)
    except (Word.DoesNotExist, LearningWord.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Word not found'}, status=404)

    # 1. Revert "Wrong" penalties
    # The user just got it wrong, so wrong_count was incremented.
    if learning.wrong_count > 0:
        learning.wrong_count -= 1
    
    # Restore term so the "Correct" logic calculation has the right base
    learning.learning_term = original_term
    
    # Remove the "Wrong" StudyLog (if it exists and is recent)
    # We look for the most recent wrong log for this word today
    log_date = (timezone.localtime() - timedelta(hours=4)).date()
    wrong_log = StudyLog.objects.filter(
        user=user, 
        word=ans_word, 
        is_correct=False, 
        date=log_date
    ).order_by('-timestamp').first()
    
    if wrong_log:
        wrong_log.delete()

    # 2. Apply "Correct" logic
    # (Similar to api_grade_word but we don't increment revision count again 
    # if we consider the previous attempt was the revision event... 
    # actually, usually 'mark as correct' implies 'that last attempt was actually correct')
    # So we keep no_of_revision increment (it was tried), 
    # but we need to ensure we don't double count if we just edited the state.
    # The previous 'wrong' logic incremented no_of_revision. We keep that.
    
    # Update stats
    learning.correct_count += 1
    learning.last_time_revised = timezone.now() # Update time to now

    # Create "Correct" StudyLog
    StudyLog.objects.create(
        user=user,
        word=ans_word,
        is_correct=True,
        date=log_date
    )

    # Calculate Terms (Same formula as api_grade_word)
    # Note: learning.wrong_count is now reverted.
    updated_wrong = learning.wrong_count
    current_learning_term = learning.learning_term # This is now original_term
    
    base_multiplier = 1.5
    multiplier = base_multiplier + (2 - base_multiplier) / (1 + updated_wrong)
    
    if current_learning_term == 0:
        next_review_delta = 1
        new_learning_term = 1
    else:
        next_review_delta = current_learning_term
        new_learning_term = math.ceil(current_learning_term * multiplier + 1)
    
    # Schedule next review
    logical_today = (timezone.localtime() - timedelta(hours=4)).date()
    target_date = logical_today + timedelta(days=next_review_delta)
    
    learning.to_be_revised = timezone.make_aware(datetime.combine(target_date, datetime.min.time())) + timedelta(hours=4)
    learning.learning_term = new_learning_term
    learning.save()

    # Cache Invalidation
    now_kst = timezone.localtime()
    logical_date_str = (now_kst - timedelta(hours=4)).date().strftime("%Y-%m-%d")
    cache.delete(f'user_stats_{user.id}_{logical_date_str}')
    cache.delete(f'user_today_words_{user.id}_{logical_date_str}')
    cache.delete(f'user_weekly_stats_{user.id}_{logical_date_str}')
    cache.delete(f'user_recent_words_{user.id}_{logical_date_str}')

    return JsonResponse({
        'status': 'success',
        'message': 'Marked as correct',
        'next_review_delta': next_review_delta
    })
