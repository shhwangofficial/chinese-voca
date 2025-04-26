from django.db import models
from django.contrib.auth.models import AbstractUser
from words.models import Word 
# Create your models here.
class User(AbstractUser):
    learning = models.ManyToManyField(Word, through='LearningWord', related_name='learned')

class LearningWord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    learning_since = models.DateTimeField(auto_now_add=True)
    to_be_revised = models.DateTimeField(auto_now_add=True)