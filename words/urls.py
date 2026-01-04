from django.contrib import admin
from django.urls import path
from . import views

app_name = "words"
urlpatterns = [
    path("", views.index, name="index"),
    path("quiz/", views.quiz, name="quiz"),
    path("add/", views.add, name="add"),
    path("flashcard/", views.flashcard_list, name="flashcard_list"),
    path("api/grade/", views.api_grade_word, name="api_grade_word"),
    path("api/mark_correct/", views.api_mark_as_correct, name="api_mark_as_correct"),
]
