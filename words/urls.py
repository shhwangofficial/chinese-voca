from django.urls import path
from . import views

app_name = "words"
urlpatterns = [
    path("", views.index, name="index"),
    path("list/", views.word_list, name="word_list"),
    path("add/", views.add, name="add"),
    path("<int:pk>/edit/", views.edit_word, name="edit_word"),
    path("<int:pk>/remove/", views.remove_word, name="remove_word"),
    path("import/", views.import_words, name="import_words"),
    path("export/", views.export_words, name="export_words"),
    path("quiz/", views.quiz, name="quiz"),
    path("flashcard/", views.flashcard_list, name="flashcard_list"),
    path("api/grade/", views.api_grade_word, name="api_grade_word"),
    path("api/mark_correct/", views.api_mark_as_correct, name="api_mark_as_correct"),
]
