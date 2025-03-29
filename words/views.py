from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Word
# Create your views here.
def index(request):
    return render(request, "base.html")

def quiz(request):
    words = Word.objects.all().order_by('order')[:10]
    context = {
        "words": words
    }
    return render(request, "words/quiz.html", context)
    

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
                # user_word    = request.POST.get(f'word_{pk}', '').strip()
                user_pinyin  = request.POST.get(f'pinyin_{pk}', '').strip()
                user_tone    = request.POST.get(f'tone_{pk}', '').strip()
                user_meaning = request.POST.get(f'meaning_{pk}', '').strip()

                is_correct = (
                    # user_word == ans_word.word and
                    user_pinyin == ans_word.pinyin and
                    user_tone == ans_word.tone and
                    user_meaning == ans_word.meaning
                )
                if is_correct:
                    ans_word.order = ans_word.order + 1
                else:
                    ans_word.order = 1
                ans_word.save()
                    
                results[quiz_no] = [is_correct, [ans_word.pinyin, ans_word.tone, ans_word.meaning], [user_pinyin, user_tone, user_meaning]]
        return render(request, 'words/result.html', {"results": results})
    else:
        return render(request, 'base.html')


def add(request):
    if request.method == 'POST':
        word = request.POST.get('word')
        if Word.objects.filter(word=word).exists():
            messages.info(request, "이미 단어가 있습니다.")
        else:
            pinyin = request.POST.get('pinyin')
            tone = request.POST.get('tone')
            meaning = request.POST.get('meaning')
            order = 1
            new_word = Word(word=word, pinyin=pinyin, tone=tone, meaning=meaning, order=order)
            new_word.save()
        return redirect("words:add")
    return render(request, "words/add.html")