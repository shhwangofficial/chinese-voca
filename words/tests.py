from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class QuizViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")

    def test_quiz_without_num_quiz(self):
        self.client.login(username="tester", password="pass")
        response = self.client.get(reverse("words:quiz"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")

    def test_quiz_with_invalid_num_quiz(self):
        self.client.login(username="tester", password="pass")
        response = self.client.get(reverse("words:quiz"), {"num_quiz": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
