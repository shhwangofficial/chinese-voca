from django.db import models
from django.contrib.auth.models import AbstractUser
from words.models import Word


# Create your models here.
class User(AbstractUser):
    learning = models.ManyToManyField(
        Word, through="LearningWord", related_name="learned"
    )


class LearningWord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    learning_since = models.DateTimeField(auto_now_add=True)
    last_time_revised = models.DateTimeField(auto_now_add=True)
    to_be_revised = models.DateTimeField()
    learning_term = models.IntegerField(default=0)
    no_of_revision = models.IntegerField(default=0)
    wrong_count = models.IntegerField(default=0)  # 틀린 횟수
    correct_count = models.IntegerField(default=0)  # 맞은 횟수

    is_paused = models.BooleanField(default=False)
    personal_pinyin = models.CharField(max_length=255, blank=True)
    personal_tone = models.CharField(max_length=50, blank=True)
    personal_meaning = models.CharField(max_length=255, blank=True)
    accepted_meanings = models.TextField(blank=True, max_length=2000)
    notes = models.TextField(blank=True, max_length=2000)
    tags = models.CharField(max_length=200, blank=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "word"], name="unique_user_learning_word"
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "is_paused", "to_be_revised"], name="learning_due_idx"
            )
        ]

    @property
    def display_pinyin(self):
        return self.personal_pinyin or self.word.pinyin

    @property
    def display_tone(self):
        return self.personal_tone if self.personal_pinyin else self.word.tone

    @property
    def display_meaning(self):
        return self.personal_meaning or self.word.meaning


class StudyLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)  # 로직상 날짜 (4시 기준)
    is_correct = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    request_id = models.UUIDField(null=True, blank=True, unique=True)
    previous_state = models.JSONField(null=True, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    corrected_at = models.DateTimeField(null=True, blank=True)


class AuthThrottle(models.Model):
    """Database-backed fixed-window limits, shared across web workers."""

    key = models.CharField(max_length=64, unique=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
