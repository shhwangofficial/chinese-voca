import csv
import io
import json
import random
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.models import LearningWord, StudyLog
from .forms import GradeForm, ImportForm, LearningEditForm, LearnWordForm, WordForm
from .models import Word
from .services import StudyConflict, grade, logical_date, mark_correct, serialize_word

CSV_FIELDS = [
    "language",
    "word",
    "word_class",
    "pinyin",
    "tone",
    "meaning",
    "accepted_meanings",
    "notes",
    "tags",
]


def learning_queryset(user, params=None):
    queryset = LearningWord.objects.filter(user=user).select_related("word")
    params = params or {}
    if params.get("language") in {"zh", "en"}:
        queryset = queryset.filter(word__language=params["language"])
    if query := params.get("q", "").strip()[:100]:
        queryset = queryset.filter(
            Q(word__word__icontains=query)
            | Q(word__pinyin__icontains=query)
            | Q(word__meaning__icontains=query)
            | Q(personal_meaning__icontains=query)
            | Q(personal_pinyin__icontains=query)
            | Q(tags__icontains=query)
        )
    if params.get("word_class") in dict(Word.WORD_CLASS_CHOICES):
        queryset = queryset.filter(word__word_class=params["word_class"])
    if params.get("status") == "due":
        queryset = queryset.filter(is_paused=False, to_be_revised__lte=timezone.now())
    elif params.get("status") == "wrong":
        queryset = queryset.filter(wrong_count__gt=0)
    elif params.get("status") == "paused":
        queryset = queryset.filter(is_paused=True)
    return queryset


@require_GET
def index(request):
    now = timezone.now()
    today = logical_date(now)
    week_ago = today - timedelta(days=6)
    learning = learning_queryset(request.user)
    due = learning.filter(is_paused=False, to_be_revised__lte=now)
    added = dict(
        learning.annotate(date=TruncDate(F("learning_since") - timedelta(hours=4)))
        .filter(date__gte=week_ago, date__lte=today)
        .values("date")
        .annotate(n=Count("pk"))
        .values_list("date", "n")
    )
    correct = dict(
        StudyLog.objects.filter(
            user=request.user, date__gte=week_ago, date__lte=today, is_correct=True
        )
        .values("date")
        .annotate(n=Count("pk"))
        .values_list("date", "n")
    )
    recent = list(learning.order_by("-learning_since")[:5])
    today_words = list(due.order_by("to_be_revised")[:5])
    for item in recent:
        days = (today - logical_date(item.learning_since)).days
        item.days_since_added = (
            "오늘" if days == 0 else "어제" if days == 1 else f"{days}일 전"
        )
    for item in today_words:
        days = (today - logical_date(item.last_time_revised)).days
        item.days_since_revision = (
            "첫 복습"
            if not item.correct_count + item.wrong_count
            else "오늘"
            if days == 0
            else f"{days}일 전"
        )
    dates = [week_ago + timedelta(days=i) for i in range(7)]
    return render(
        request,
        "words/index.html",
        {
            "total_learning_words": learning.count(),
            "today_review_words": due.count(),
            "recent_words": recent,
            "today_words": today_words,
            "today": today,
            "wrong_words_count": learning.filter(
                wrong_count__gt=0, is_paused=False
            ).count(),
            "weekly_stats": [
                {
                    "date": d,
                    "date_str": d.strftime("%m/%d"),
                    "day_name": "월화수목금토일"[d.weekday()],
                    "words_added": added.get(d, 0),
                    "words_correct": correct.get(d, 0),
                }
                for d in dates
            ],
        },
    )


@require_GET
def word_list(request):
    ordering = {
        "recent": "-learning_since",
        "due": "to_be_revised",
        "wrong": "-wrong_count",
        "word": "word__word",
    }
    queryset = learning_queryset(request.user, request.GET).order_by(
        ordering.get(request.GET.get("sort"), "-learning_since"), "pk"
    )
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "words/list.html",
        {
            "page_obj": Paginator(queryset, 30).get_page(request.GET.get("page")),
            "query_string": params.urlencode(),
            "word_classes": Word.WORD_CLASS_CHOICES,
        },
    )


@transaction.atomic
def attach_word(user, data):
    word, _ = Word.objects.get_or_create(
        language=data["language"],
        word=data["word"],
        word_class=data["word_class"],
        defaults={k: data[k] for k in ["pinyin", "tone", "meaning"]},
    )
    pronunciation_changed = (data["pinyin"], data["tone"]) != (word.pinyin, word.tone)
    learning, created = LearningWord.objects.get_or_create(
        user=user,
        word=word,
        defaults={
            "to_be_revised": timezone.now(),
            "personal_pinyin": data["pinyin"] if pronunciation_changed else "",
            "personal_tone": data["tone"] if pronunciation_changed else "",
            "personal_meaning": data["meaning"]
            if data["meaning"] != word.meaning
            else "",
            **{
                key: data.get(key, "") for key in ["accepted_meanings", "notes", "tags"]
            },
        },
    )
    return learning, created


@require_http_methods(["GET", "POST"])
def add(request):
    form_type = (
        request.POST.get("form_type", "LearnWord")
        if request.method == "POST"
        else "LearnWord"
    )
    if form_type not in {"LearnWord", "Word"}:
        return HttpResponse("Invalid form type", status=400)
    form = (LearnWordForm if form_type == "LearnWord" else WordForm)(
        request.POST or None
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if form_type == "LearnWord":
            word = Word.objects.filter(**data).first()
            if not word:
                form = WordForm(initial=data)
                form_type = "Word"
            else:
                _, created = LearningWord.objects.get_or_create(
                    user=request.user,
                    word=word,
                    defaults={"to_be_revised": timezone.now()},
                )
                messages.success(
                    request,
                    "학습 목록에 추가했습니다."
                    if created
                    else "이미 학습 중인 단어입니다.",
                )
                return redirect("words:word_list")
        else:
            _, created = attach_word(request.user, data)
            messages.success(
                request,
                "학습 목록에 추가했습니다."
                if created
                else "이미 학습 중인 단어입니다. 목록에서 수정하세요.",
            )
            return redirect("words:word_list")
    return render(request, "words/add.html", {"form": form, "form_type": form_type})


@require_http_methods(["GET", "POST"])
def edit_word(request, pk):
    learning = get_object_or_404(
        LearningWord.objects.select_related("word"), pk=pk, user=request.user
    )
    form = LearningEditForm(request.POST or None, instance=learning)
    if request.method == "POST" and form.is_valid():
        # Only edit personal fields; never overwrite concurrent grading counters.
        LearningWord.objects.filter(pk=learning.pk, user=request.user).update(
            **form.cleaned_data, version=F("version") + 1
        )
        messages.success(request, "본인의 단어 정보만 수정했습니다.")
        return redirect("words:word_list")
    return render(request, "words/edit.html", {"form": form, "learning": learning})


@require_POST
def remove_word(request, pk):
    learning = get_object_or_404(LearningWord, pk=pk, user=request.user)
    learning.delete()
    # StudyLog and the shared Word are deliberately retained.
    messages.success(
        request, "학습 목록에서 제외했습니다. 과거 학습 기록은 보존됩니다."
    )
    return redirect("words:word_list")


@require_GET
def quiz(request):
    raw_limit = request.GET.get("num_quiz", "20")
    if raw_limit != "all" and (
        not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 100
    ):
        messages.error(request, "문제 수는 1~100 또는 전체를 선택하세요.")
        return redirect("words:index")
    queryset = learning_queryset(request.user, request.GET).filter(
        is_paused=False, to_be_revised__lte=timezone.now()
    )
    kind = request.GET.get("kind", "all")
    if kind == "new":
        queryset = queryset.filter(correct_count=0, wrong_count=0)
    elif kind == "review":
        queryset = queryset.filter(Q(correct_count__gt=0) | Q(wrong_count__gt=0))
    ids = list(queryset.values_list("pk", flat=True))
    random.shuffle(ids)
    # Bound the browser payload even for "all"; remaining words are a next session.
    ids = ids[: 1000 if raw_limit == "all" else int(raw_limit)]
    if not ids:
        messages.info(request, "선택한 조건에 복습할 단어가 없습니다.")
        return redirect("words:index")
    by_id = {lw.pk: lw for lw in queryset.filter(pk__in=ids)}
    return render(
        request,
        "words/quiz.html",
        {
            "words_data": [serialize_word(by_id[pk]) for pk in ids],
            "quiz_options": {
                "user_id": request.user.pk,
                "day": str(logical_date()),
                "signature": f"{request.GET.get('language', '')}:{raw_limit}:{kind}:{request.GET.get('test_tone', '')}",
                "test_tone": request.GET.get("test_tone") == "1",
            },
        },
    )


def json_body(request):
    if request.content_type != "application/json" or len(request.body) > 8192:
        raise ValueError("JSON 요청이 필요합니다 (최대 8KB).")
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError("JSON 객체가 필요합니다.")
    return data


def api_error(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)


@require_POST
def api_grade_word(request):
    try:
        form = GradeForm(json_body(request))
        if not form.is_valid():
            return api_error("입력값을 확인해주세요: " + str(form.errors.as_text()))
        return JsonResponse(grade(request.user, form.cleaned_data))
    except (ValueError, UnicodeDecodeError):
        return api_error("올바른 JSON 요청이 아닙니다.")
    except LearningWord.DoesNotExist:
        return api_error("학습 중인 단어가 아닙니다.", 404)
    except StudyConflict as exc:
        return api_error(str(exc), 409)
    except (IntegrityError, OperationalError):
        return api_error(
            "처리 중인 요청이 있습니다. 잠시 후 같은 답안을 다시 제출해주세요.", 409
        )


@require_POST
def api_mark_as_correct(request):
    try:
        data = json_body(request)
        attempt_id = data.get("attempt_id")
        if type(attempt_id) is not int or attempt_id < 1:
            return api_error("올바른 학습 기록 ID가 필요합니다.")
        return JsonResponse(mark_correct(request.user, attempt_id))
    except (ValueError, UnicodeDecodeError):
        return api_error("올바른 JSON 요청이 아닙니다.")
    except (StudyLog.DoesNotExist, LearningWord.DoesNotExist):
        return api_error("학습 기록을 찾을 수 없습니다.", 404)
    except StudyConflict as exc:
        return api_error(str(exc), 409)
    except (IntegrityError, OperationalError):
        return api_error("다른 요청 처리 중입니다. 잠시 후 다시 시도해주세요.", 409)


@require_GET
def flashcard_list(request):
    queryset = learning_queryset(request.user, request.GET).filter(is_paused=False)
    if request.GET.get("scope") != "all":
        queryset = queryset.filter(wrong_count__gt=0)
    ids = list(queryset.values_list("pk", flat=True))
    random.shuffle(ids)
    by_id = {lw.pk: lw for lw in queryset.filter(pk__in=ids[:1000])}
    words = [serialize_word(by_id[pk], answers=True) for pk in ids[:1000]]
    return render(request, "words/flashcard.html", {"words_data": words})


def csv_safe(value):
    value = str(value)
    return (
        "'" + value
        if value.lstrip().startswith(("=", "+", "-", "@"))
        or value.startswith(("\t", "\r", "\n"))
        else value
    )


def csv_restore(value):
    if value.startswith("'") and (
        value[1:].lstrip().startswith(("=", "+", "-", "@"))
        or value[1:].startswith(("\t", "\r", "\n"))
    ):
        return value[1:]
    return value


@require_GET
def export_words(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="vocabulary.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(CSV_FIELDS)
    for lw in (
        learning_queryset(request.user, request.GET)
        .order_by("pk")
        .iterator(chunk_size=500)
    ):
        writer.writerow(
            [
                csv_safe(v)
                for v in [
                    lw.word.language,
                    lw.word.word,
                    lw.word.word_class,
                    lw.display_pinyin,
                    lw.display_tone,
                    lw.display_meaning,
                    lw.accepted_meanings,
                    lw.notes,
                    lw.tags,
                ]
            ]
        )
    return response


@require_http_methods(["GET", "POST"])
def import_words(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    preview = []
    errors = []
    if request.method == "POST" and request.POST.get("confirm") == "1":
        pending = request.session.get("csv_preview")
        if not pending or timezone.now().timestamp() - pending["created"] > 1800:
            messages.error(request, "미리보기가 만료됐습니다. 다시 파일을 선택하세요.")
            return redirect("words:import_words")
        with transaction.atomic():
            created = sum(attach_word(request.user, row)[1] for row in pending["rows"])
        request.session.pop("csv_preview", None)
        messages.success(
            request,
            f"{created}개 추가, {len(pending['rows']) - created}개 중복 건너뜀.",
        )
        return redirect("words:word_list")
    if request.method == "POST":
        request.session.pop("csv_preview", None)
    if request.method == "POST" and form.is_valid():
        try:
            text = form.cleaned_data["file"].read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text, newline=""))
            if not reader.fieldnames or not set(CSV_FIELDS[:6]).issubset(
                reader.fieldnames
            ):
                raise ValueError(
                    "필수 열: language, word, word_class, pinyin, tone, meaning"
                )
            seen = set()
            for number, row in enumerate(reader, start=2):
                if number > 501:
                    raise ValueError("한 번에 최대 500개 단어까지 가져올 수 있습니다.")
                if None in row or any(v is None for v in row.values()):
                    errors.append(f"{number}행: 열 수가 맞지 않습니다.")
                    continue
                row = {k: csv_restore(v) for k, v in row.items()}
                word_form = WordForm(row)
                if not word_form.is_valid():
                    errors.append(f"{number}행: {word_form.errors.as_text()}")
                    continue
                data = word_form.cleaned_data
                edit_form = LearningEditForm(
                    {k: row.get(k, "") for k in ["accepted_meanings", "notes", "tags"]},
                    instance=LearningWord(word=word_form.instance),
                )
                if not edit_form.is_valid():
                    errors.append(f"{number}행: {edit_form.errors.as_text()}")
                    continue
                key = (data["language"], data["word"], data["word_class"])
                if key in seen:
                    errors.append(f"{number}행: 파일 내 중복 단어입니다.")
                    continue
                seen.add(key)
                preview.append(
                    {
                        **data,
                        **{
                            k: edit_form.cleaned_data[k]
                            for k in ["accepted_meanings", "notes", "tags"]
                        },
                    }
                )
            if not preview and not errors:
                errors.append("등록할 단어가 없습니다.")
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            errors.append(str(exc))
        if not errors:
            request.session["csv_preview"] = {
                "created": timezone.now().timestamp(),
                "rows": preview,
            }
    return render(
        request,
        "words/import.html",
        {"form": form, "preview": preview, "errors": errors},
    )
