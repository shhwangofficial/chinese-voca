from django.db import models
from django.utils import timezone


# Create your models here.
class Word(models.Model):
    WORD_CLASS_CHOICES = [
        ('noun', '명사'),
        ('pronoun', '대명사'),
        ('verb', '동사'),
        ('adjective', '형용사'),
        ('numeral', '수사·양사'),
        ('adverb', '부사'),
        ('preposition', '개사·접속사·조사'),
        ('interjection', '감탄사·의성·의태'),
    ]
    
    word = models.CharField(max_length=20, verbose_name='단어', db_index=True)
    pinyin = models.CharField(max_length=40, verbose_name='병음', db_index=True)
    tone = models.CharField(max_length=20, verbose_name='성조')
    meaning = models.CharField(max_length=40, verbose_name='의미', db_index=True)
    word_class = models.CharField(
        max_length=20, 
        choices=WORD_CLASS_CHOICES, 
        verbose_name='품사', 
        db_index=True,
        default='noun'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='생성일', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '단어'
        verbose_name_plural = '단어들'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['word', 'pinyin']),
            models.Index(fields=['word', 'word_class'], name='words_word_word_word_class_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['word', 'word_class'], name='unique_word_word_class'),
        ]

    def __str__(self):
        return f"{self.word} ({self.pinyin})"
