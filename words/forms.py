from django import forms
from .models import Word


class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = ['word', 'pinyin', 'tone', 'meaning', 'word_class']
        widgets = {
            'word': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 你好'}),
            'pinyin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: ni hao'}),
            'tone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 3 3'}),
            'meaning': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 안녕하세요'}),
            'word_class': forms.Select(attrs={'class': 'form-control'}),
        }


class LearnWordForm(forms.Form):
    word = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 你好'}),
        label='단어'
    )
    word_class = forms.ChoiceField(
        choices=Word.WORD_CLASS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='품사'
    )
