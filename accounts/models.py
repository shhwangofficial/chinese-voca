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
    no_of_revision = models.IntegerField(default=1)
    wrong_count = models.IntegerField(default=0)  # 틀린 횟수
    correct_count = models.IntegerField(default=0)  # 맞은 횟수


class StudyLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)  # 로직상 날짜 (4시 기준)
    is_correct = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'date']),
        ]
