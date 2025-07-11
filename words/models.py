from django.db import models
from django.utils import timezone


# Create your models here.
class Word(models.Model):
    word = models.CharField(max_length=20, verbose_name='단어', db_index=True)
    pinyin = models.CharField(max_length=40, verbose_name='병음', db_index=True)
    tone = models.CharField(max_length=20, verbose_name='성조')
    meaning = models.CharField(max_length=40, verbose_name='의미', db_index=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='생성일', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')
    last_reviewed = models.DateTimeField(null=True, blank=True, verbose_name='마지막 복습일', db_index=True)
    review_count = models.IntegerField(default=0, verbose_name='복습 횟수')

    class Meta:
        verbose_name = '단어'
        verbose_name_plural = '단어들'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['word', 'pinyin']),
        ]

    def __str__(self):
        return f"{self.word} ({self.pinyin})"
