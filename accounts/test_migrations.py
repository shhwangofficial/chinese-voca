from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LegacyDatabaseMigrationTests(TransactionTestCase):
    def test_duplicate_links_are_merged_and_history_retained(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [
            ("accounts", "0006_remove_learningword_last_result_is_correct"),
            ("words", "0010_alter_word_tone"),
        ]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model("accounts", "User")
            Word = apps.get_model("words", "Word")
            Learning = apps.get_model("accounts", "LearningWord")
            Log = apps.get_model("accounts", "StudyLog")
            user = User.objects.create(username="legacy")
            word = Word.objects.create(
                word="你好", pinyin="ni hao", meaning="안녕하세요"
            )
            now = timezone.now()
            Learning.objects.create(
                user=user,
                word=word,
                correct_count=2,
                wrong_count=1,
                no_of_revision=4,
                to_be_revised=now,
            )
            Learning.objects.create(
                user=user,
                word=word,
                correct_count=3,
                wrong_count=2,
                no_of_revision=6,
                to_be_revised=now,
            )
            Log.objects.create(user=user, word=word, date=now.date(), is_correct=True)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            merged = apps.get_model("accounts", "LearningWord").objects.get(
                user_id=user.pk, word_id=word.pk
            )
            self.assertEqual(
                (merged.correct_count, merged.wrong_count, merged.no_of_revision),
                (5, 3, 10),
            )
            self.assertEqual(apps.get_model("accounts", "StudyLog").objects.count(), 1)
            self.assertEqual(
                apps.get_model("words", "Word").objects.get(pk=word.pk).language, "zh"
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
