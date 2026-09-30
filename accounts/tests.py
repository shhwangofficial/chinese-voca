from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester", password="test-password"
        )

    def test_login_safe_next(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "tester", "password": "test-password", "next": "/words/list/"},
        )
        self.assertRedirects(response, "/words/list/")

    def test_login_rejects_external_next(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "tester",
                "password": "test-password",
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(response, reverse("words:index"))

    def test_logout_is_post_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_brute_force_throttle(self):
        for _ in range(10):
            self.client.post(
                reverse("accounts:login"), {"username": "tester", "password": "wrong"}
            )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "tester", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 429)

    def test_signup_logs_user_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "new-user",
                "password1": "A-strong-password-2390",
                "password2": "A-strong-password-2390",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "test-password",
                "new_password1": "Another-strong-password-2390",
                "new_password2": "Another-strong-password-2390",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-strong-password-2390"))
