from django.db import models

# Create your models here.
class Word(models.Model):
    word = models.CharField(max_length=20)
    pinyin = models.CharField(max_length=40)
    tone = models.CharField(max_length=20)
    meaning = models.CharField(max_length=40)
    suffix = models.CharField(max_length=20, blank=True)