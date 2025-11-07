from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("words", "0006_remove_word_last_reviewed_remove_word_review_count"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="word",
            index=models.Index(fields=["word", "word_class"], name="words_word_word_word_class_idx"),
        ),
        migrations.AddConstraint(
            model_name="word",
            constraint=models.UniqueConstraint(fields=("word", "word_class"), name="unique_word_word_class"),
        ),
    ]

