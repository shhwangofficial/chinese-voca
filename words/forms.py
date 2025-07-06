from django import forms
from .models import Word


class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = ['pinyin', 'tone', 'meaning']
        widgets = {
            'pinyin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: ni hao'}),
            'tone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 3 3'}),
            'meaning': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 안녕하세요'}),
        }


class LearnWordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = [
            "word",
        ]
