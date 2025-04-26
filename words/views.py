from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Word
from accounts.models import LearningWord 
from .forms import WordForm, LearnWordForm
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta

@require_http_methods(['GET'])
def index(request):
    if request.user.is_authenticated:
        return render(request, "base.html")
    else:
        return redirect("accounts:login")
    

@require_http_methods(['GET'])
def quiz(request):
    num_quiz = int(request.GET.get("num_quiz"))
    if num_quiz <= 0:
        return render(request, "base.html")
    user = request.user
    words = user.learning.filter( \
        learningword__to_be_revised__lt=timezone.now() \
        ).order_by('learningword__to_be_revised')
    context = {
        "words": words
    }
    return render(request, "words/quiz.html", context)
    

@require_http_methods(['GET', 'POST'])
def grade(request):
    user = request.user
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

                learning = LearningWord.objects.get(user=user, word=ans_word)
                learning.no_of_revision += 1
                if is_correct:
                    new_learning_term = learning.learning_term * 2 + 1
                else:
                    new_learning_term = 0
                learning.to_be_revised = timezone.now() + timedelta(days=new_learning_term)
                learning.learning_term = new_learning_term
                learning.save()
                    
                results[quiz_no] = [is_correct, ans_word.word, [ans_word.pinyin, ans_word.tone, ans_word.meaning], [user_pinyin, user_tone, user_meaning], ans_word.suffix]
        request.session['grade_results'] = results
        return redirect('words:grade')
    
    results = request.session.pop('grade_results', None)  # 사용 후 삭제
    return render(request, 'words/result.html', {'results': results})


@require_http_methods(['GET', 'POST'])
def add(request):
    user = request.user
    if request.method == 'POST':
        form_type = request.POST.get("form_type")
        if form_type == 'LearnWord':
            form = LearnWordForm(request.POST)
            if form.is_valid():
                word = form.cleaned_data['word']
                found_word = Word.objects.filter(word=word).first()
                if found_word:
                    if user.learning.filter(word=word).exists():
                        messages.info(request, f"{word}가 이미 학습 목록에 있습니다.")
                    else:
                        to_be_revised = timezone.now()
                        LearningWord.objects.create(user=user, word=found_word, to_be_revised=to_be_revised)
                        messages.info(request, f"{word}를 학습 목록에 추가했습니다.")
                    return redirect("words:add")
                else:
                    messages.info(request, f"{word}가 데이터베이스에 존재하지 않습니다. 추가하시겠습니까?")
                    form = WordForm(initial={'word': word})
                    form_type = "Word"

        elif form_type == 'Word':
            form = WordForm(request.POST)
            if form.is_valid():
                word = form.cleaned_data['word']
                form.save()
                messages.success(request, f"{word}가 데이터베이스에 추가되었습니다.")
                request.session['added_word'] = word
                return redirect("words:add")
            else:
                messages.error(request, f"{word}를 데이터베이스로 추가에 실패했습니다.")
    else:
        added_word = request.session.pop('added_word', None)
        if added_word:
            form = LearnWordForm(initial={'word': added_word})
        else:
            form = LearnWordForm()
        form_type = "LearnWord"
        
    context = {
        "form" : form,
        "form_type": form_type,
    }
    return render(request, "words/add.html", context)
