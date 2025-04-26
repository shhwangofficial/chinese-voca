from django.contrib import admin
from django.urls import path
from . import views

app_name = "words"
urlpatterns = [
    path("", views.index, name="index"),
    path("quiz/", views.quiz, name="quiz"),
    path("grade/", views.grade, name="grade"),
    path("add/", views.add, name="add"),
]
