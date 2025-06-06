from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Word
from .forms import WordForm
from django.views.decorators.http import require_http_methods
# Create your views here.
@require_http_methods(['GET'])
def index(request):
    if request.user.is_authenticated:
        return render(request, "base.html")
    else:
        return redirect("accounts:login")
    

@require_http_methods(['GET'])
def quiz(request):
    try:
        num_quiz = int(request.GET.get("num_quiz", "0"))
    except (TypeError, ValueError):
        num_quiz = 0
    if num_quiz <= 0:
        return render(request, "base.html")
    words = Word.objects.all().order_by('order')[:num_quiz]
    context = {
        "words": words
    }
    return render(request, "words/quiz.html", context)
    

@require_http_methods(['GET', 'POST'])
def grade(request):
    if request.method == 'POST':
        results = {}
        for key in request.POST:
            if key.startswith('quizno_'):
                pk = key.split('_')[1]
                
                try:
                    ans_word = Word.objects.get(pk=pk)
                except Word.DoesNotExist:
                    continue
                
                quiz_no      = request.POST.get(f'quizno_{pk}', '').strip()
                user_pinyin  = request.POST.get(f'pinyin_{pk}', '').strip()
                user_tone    = request.POST.get(f'tone_{pk}', '').strip()
                user_meaning = request.POST.get(f'meaning_{pk}', '').strip()

                is_correct = (
                    user_pinyin == ans_word.pinyin and
                    # user_tone == ans_word.tone and
                    user_meaning == ans_word.meaning
                )
                if is_correct:
                    ans_word.order = ans_word.order + 1
                else:
                    ans_word.order = 1
                ans_word.save()
                    
                results[quiz_no] = [is_correct, ans_word.word, [ans_word.pinyin, ans_word.tone, ans_word.meaning], [user_pinyin, user_tone, user_meaning], ans_word.suffix]
        request.session['grade_results'] = results
        return redirect('words:grade')
    
    results = request.session.pop('grade_results', None)  # 사용 후 삭제
    return render(request, 'words/result.html', {'results': results})


@require_http_methods(['GET', 'POST'])
def add(request):
    if request.method == 'POST':
        form = WordForm(request.POST)
        if form.is_valid():
            word = form.cleaned_data['word']
            if Word.objects.filter(word=word).exists():
                messages.info(request, "이미 단어가 있습니다.")
            else:
                word = form.save(commit=False)
                word.order = 1
                word.save()
                messages.info(request, f"{word.word}가 추가되었습니다.")
            return redirect("words:add")
    else:
        form = WordForm()
    context = {
        "form" : form
    }
    return render(request, "words/add.html", context)
