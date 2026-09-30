import csv
import io
import json
import uuid
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import LearningWord, StudyLog
from .forms import WordForm
from .models import Word
from .services import calculate_result, logical_date


class VocabularyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester", password="test-password"
        )
        self.other = get_user_model().objects.create_user(
            username="other", password="test-password"
        )
        self.word = Word.objects.create(
            word="你好", pinyin="ni hao", tone="3 3", meaning="안녕하세요"
        )
        self.learning = LearningWord.objects.create(
            user=self.user, word=self.word, to_be_revised=timezone.now()
        )
        self.client.force_login(self.user)

    def grade(self, **overrides):
        data = {
            "request_id": str(uuid.uuid4()),
            "word_id": self.word.pk,
            "version": 0,
            "pinyin": "ni hao",
            "meaning": "안녕하세요",
        }
        data.update(overrides)
        return self.client.post(
            reverse("words:api_grade_word"),
            json.dumps(data),
            content_type="application/json",
        )

    def correct(self, attempt_id):
        return self.client.post(
            reverse("words:api_mark_as_correct"),
            json.dumps({"attempt_id": attempt_id}),
            content_type="application/json",
        )

    def test_grade_is_idempotent(self):
        key = str(uuid.uuid4())
        first = self.grade(request_id=key)
        second = self.grade(request_id=key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.learning.refresh_from_db()
        self.assertEqual(
            (
                self.learning.correct_count,
                self.learning.no_of_revision,
                self.learning.version,
            ),
            (1, 1, 1),
        )
        self.assertEqual(StudyLog.objects.count(), 1)
        self.assertEqual(timezone.localtime(self.learning.to_be_revised).hour, 4)

    def test_stale_tab_cannot_grade_twice(self):
        self.grade()
        self.assertEqual(self.grade().status_code, 409)
        self.assertEqual(StudyLog.objects.count(), 1)

    def test_correction_is_idempotent_and_keeps_original_log(self):
        wrong = self.grade(meaning="오답").json()
        first = self.correct(wrong["attempt_id"])
        second = self.correct(wrong["attempt_id"])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.learning.refresh_from_db()
        self.assertEqual(
            (
                self.learning.correct_count,
                self.learning.wrong_count,
                self.learning.no_of_revision,
            ),
            (1, 0, 1),
        )
        log = StudyLog.objects.get()
        self.assertTrue(log.is_correct)
        self.assertIsNotNone(log.corrected_at)
        self.assertIsNotNone(log.previous_state)

    def test_cannot_correct_a_previous_attempt_after_new_grade(self):
        wrong = self.grade(meaning="오답").json()
        self.grade(version=wrong["version"])
        self.assertEqual(self.correct(wrong["attempt_id"]).status_code, 409)

    def test_cannot_correct_attempt_from_removed_learning_link(self):
        wrong = self.grade(meaning="오답").json()
        self.learning.delete()
        replacement = LearningWord.objects.create(
            user=self.user, word=self.word, to_be_revised=timezone.now()
        )
        self.grade(meaning="오답")
        self.assertEqual(self.correct(wrong["attempt_id"]).status_code, 409)
        replacement.refresh_from_db()
        self.assertEqual(replacement.correct_count, 0)

    def test_chinese_personal_tone_can_be_cleared_on_import(self):
        from .views import attach_word

        learning, _ = attach_word(
            self.other,
            {
                "language": "zh",
                "word": "你好",
                "word_class": "noun",
                "pinyin": "ni hao",
                "tone": "",
                "meaning": "안녕",
            },
        )
        self.assertEqual(learning.display_tone, "")
        self.word.refresh_from_db()
        self.assertEqual(self.word.tone, "3 3")

    def test_cannot_correct_a_correct_attempt(self):
        result = self.grade().json()
        self.assertEqual(self.correct(result["attempt_id"]).status_code, 409)

    def test_correction_uses_original_study_date(self):
        seoul = ZoneInfo("Asia/Seoul")
        before = datetime(2026, 9, 29, 3, 59, tzinfo=seoul)
        after = datetime(2026, 9, 29, 4, 1, tzinfo=seoul)
        with patch("django.utils.timezone.now", return_value=before):
            wrong = self.grade(meaning="오답").json()
        with patch("django.utils.timezone.now", return_value=after):
            self.assertEqual(self.correct(wrong["attempt_id"]).status_code, 200)
        log = StudyLog.objects.get()
        self.assertEqual(str(log.date), "2026-09-28")
        self.learning.refresh_from_db()
        self.assertEqual(
            timezone.localtime(self.learning.to_be_revised),
            datetime(2026, 9, 29, 4, tzinfo=seoul),
        )

    def test_transaction_rolls_back_on_log_failure(self):
        with patch(
            "words.services.StudyLog.objects.create",
            side_effect=IntegrityError("simulated"),
        ):
            self.assertEqual(self.grade().status_code, 409)
        self.learning.refresh_from_db()
        self.assertEqual(self.learning.correct_count, 0)
        self.assertEqual(self.learning.version, 0)

    def test_word_ownership(self):
        self.client.force_login(self.other)
        self.assertEqual(self.grade().status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse("words:edit_word", args=[self.learning.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("words:remove_word", args=[self.learning.pk])
            ).status_code,
            404,
        )

    def test_attempt_ownership(self):
        attempt = self.grade(meaning="오답").json()["attempt_id"]
        self.client.force_login(self.other)
        self.assertEqual(self.correct(attempt).status_code, 404)

    def test_api_login_and_csrf(self):
        self.client.logout()
        response = self.grade()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["status"], "error")
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        self.assertEqual(
            secure_client.post(
                reverse("words:api_grade_word"), "{}", content_type="application/json"
            ).status_code,
            403,
        )

    def test_invalid_json_and_ids(self):
        for payload in ["[1]", "{", "null"]:
            self.assertEqual(
                self.client.post(
                    reverse("words:api_grade_word"),
                    payload,
                    content_type="application/json",
                ).status_code,
                400,
            )
        for value in ["abc", -1, None, 1.5, {}, []]:
            self.assertEqual(self.grade(word_id=value).status_code, 400)
        self.assertEqual(self.correct("abc").status_code, 400)
        self.assertEqual(self.grade(version=-1).status_code, 400)

    def test_paused_word_cannot_be_graded(self):
        self.learning.is_paused = True
        self.learning.save()
        self.assertEqual(self.grade().status_code, 409)

    def test_alternative_meanings(self):
        self.learning.accepted_meanings = "안녕\n반갑습니다"
        self.learning.save()
        self.assertTrue(self.grade(meaning="  안녕  ").json()["is_correct"])

    def test_pinyin_aliases(self):
        self.word.pinyin = "lü"
        self.word.save()
        self.assertTrue(self.grade(pinyin="LV").json()["is_correct"])

    def test_tone_mode(self):
        self.assertFalse(self.grade(tone="1 1", test_tone=True).json()["is_correct"])
        self.assertTrue(
            self.grade(version=1, tone="3,3", test_tone=True).json()["is_correct"]
        )

    def test_english_does_not_require_pinyin(self):
        self.word.language = "en"
        self.word.word = "hello"
        self.word.save()
        self.assertTrue(self.grade(pinyin="").json()["is_correct"])

    def test_personal_edit_preserves_shared_word_and_counters(self):
        self.grade()
        response = self.client.post(
            reverse("words:edit_word", args=[self.learning.pk]),
            {
                "personal_meaning": "안녕",
                "accepted_meanings": "반가워",
                "notes": "내 메모",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.word.refresh_from_db()
        self.learning.refresh_from_db()
        self.assertEqual(self.word.meaning, "안녕하세요")
        self.assertEqual(self.learning.display_meaning, "안녕")
        self.assertEqual(self.learning.correct_count, 1)
        self.assertEqual(self.learning.version, 2)

    def test_remove_preserves_word_and_history(self):
        self.grade()
        self.client.post(reverse("words:remove_word", args=[self.learning.pk]))
        self.assertFalse(LearningWord.objects.filter(pk=self.learning.pk).exists())
        self.assertTrue(Word.objects.filter(pk=self.word.pk).exists())
        self.assertEqual(StudyLog.objects.count(), 1)

    def test_unique_learning_word(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LearningWord.objects.create(
                user=self.user, word=self.word, to_be_revised=timezone.now()
            )

    def test_invalid_form_type(self):
        self.assertEqual(
            self.client.post(
                reverse("words:add"), {"form_type": "unknown"}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.post(reverse("words:add"), {}).status_code, 200)

    def test_add_existing_word_does_not_overwrite_global_data(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("words:add"),
            {
                "form_type": "Word",
                "language": "zh",
                "word": "你好",
                "word_class": "noun",
                "pinyin": "ni hao",
                "tone": "3 3",
                "meaning": "반가워",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.word.refresh_from_db()
        self.assertEqual(self.word.meaning, "안녕하세요")
        self.assertEqual(
            LearningWord.objects.get(user=self.other).display_meaning, "반가워"
        )

    def test_add_form_preserves_values_and_reports_errors(self):
        response = self.client.post(
            reverse("words:add"),
            {
                "form_type": "Word",
                "language": "zh",
                "word": "再见",
                "word_class": "verb",
                "pinyin": "zai jian",
                "tone": "4",
                "meaning": "잘 가",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "zai jian")
        self.assertContains(response, "성조는 병음 음절 수")

    def test_quiz_limits_and_empty_state(self):
        self.assertEqual(
            self.client.get(reverse("words:quiz"), {"num_quiz": "abc"}).status_code, 302
        )
        response = self.client.get(reverse("words:quiz"), {"num_quiz": "1"})
        self.assertEqual(len(response.context["words_data"]), 1)
        self.grade()
        self.assertEqual(self.client.get(reverse("words:quiz")).status_code, 302)

    def test_xss_payload_is_inert_in_templates(self):
        self.word.meaning = "<img src=x onerror=alert(1)></script>"
        self.word.save()
        response = self.client.get(reverse("words:flashcard_list"), {"scope": "all"})
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "\\u003Cimg")
        response = self.client.get(reverse("words:word_list"))
        self.assertContains(response, "&lt;img")

    def test_page_rendering_and_unknown_url(self):
        for name in [
            "index",
            "word_list",
            "add",
            "import_words",
            "quiz",
            "flashcard_list",
        ]:
            self.assertEqual(
                self.client.get(reverse("words:" + name)).status_code, 200, name
            )
        self.client.logout()
        self.assertEqual(self.client.get("/missing-url/").status_code, 404)

    def test_search_does_not_leak_other_users_words(self):
        word = Word.objects.create(word="秘密", meaning="비밀", pinyin="mi mi")
        LearningWord.objects.create(
            user=self.other, word=word, to_be_revised=timezone.now()
        )
        response = self.client.get(reverse("words:word_list"), {"q": "비밀"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def upload(self, rows):
        content = (
            "language,word,word_class,pinyin,tone,meaning,accepted_meanings,notes,tags\n"
            + rows
        )
        file = SimpleUploadedFile(
            "words.csv", content.encode("utf-8-sig"), content_type="text/csv"
        )
        return self.client.post(reverse("words:import_words"), {"file": file})

    def test_csv_preview_confirm_and_repeat(self):
        response = self.upload("en,apple,noun,,,사과,,,과일\n")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Word.objects.filter(word="apple").exists())
        self.client.post(reverse("words:import_words"), {"confirm": "1"})
        self.assertTrue(
            LearningWord.objects.filter(user=self.user, word__word="apple").exists()
        )
        self.client.post(reverse("words:import_words"), {"confirm": "1"})
        self.assertEqual(Word.objects.filter(word="apple").count(), 1)

    def test_csv_error_is_all_or_nothing(self):
        response = self.upload("en,apple,noun,,,사과,,,\nzh,坏,noun,,,나쁜,,,\n")
        self.assertTrue(response.context["errors"])
        self.client.post(reverse("words:import_words"), {"confirm": "1"})
        self.assertFalse(Word.objects.filter(word="apple").exists())

    def test_csv_duplicate_rows_are_rejected(self):
        response = self.upload("en,apple,noun,,,사과,,,\nen,apple,noun,,,사과,,,\n")
        self.assertTrue(response.context["errors"])

    def test_csv_formula_escape_and_unicode(self):
        self.learning.notes = '=HYPERLINK("evil")'
        self.learning.save()
        response = self.client.get(reverse("words:export_words"))
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["word"], "你好")
        self.assertTrue(rows[0]["notes"].startswith("'="))

    def test_pronunciation_validation(self):
        for tone in ["8", "3 3 3", "x"]:
            form = WordForm(
                {
                    "language": "zh",
                    "word": "你好",
                    "word_class": "noun",
                    "pinyin": "ni hao",
                    "tone": tone,
                    "meaning": "안녕",
                }
            )
            self.assertFalse(form.is_valid())

    def test_meaning_length_updated_with_update_fields(self):
        self.word.meaning = "안녕"
        self.word.save(update_fields=["meaning"])
        self.word.refresh_from_db()
        self.assertEqual(self.word.meaning_length, 2)

    def test_logical_date_boundary_and_interval_cap(self):
        seoul = ZoneInfo("Asia/Seoul")
        self.assertEqual(
            str(logical_date(datetime(2026, 9, 29, 3, 59, tzinfo=seoul))), "2026-09-28"
        )
        self.assertEqual(
            str(logical_date(datetime(2026, 9, 29, 4, 0, tzinfo=seoul))), "2026-09-29"
        )
        state, delta = calculate_result(
            {
                "learning_term": 999999999,
                "correct_count": 0,
                "wrong_count": 0,
                "no_of_revision": 0,
            },
            True,
            timezone.now(),
        )
        self.assertEqual(delta, 365)
        self.assertEqual(state["learning_term"], 365)

    def test_stats_include_only_owner_and_use_logical_date(self):
        self.grade()
        response = self.client.get(reverse("words:index"))
        self.assertEqual(
            sum(item["words_correct"] for item in response.context["weekly_stats"]), 1
        )
        self.assertEqual(response.context["today_review_words"], 0)
