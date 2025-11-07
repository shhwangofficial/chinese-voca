from django.db import migrations, models


def populate_meaning_length(apps, schema_editor):
    Word = apps.get_model('words', 'Word')
    for word in Word.objects.all():
        meaning = (word.meaning or '').strip()
        word.meaning_length = len(meaning)
        word.save(update_fields=['meaning_length'])


class Migration(migrations.Migration):

    dependencies = [
        ('words', '0007_word_unique_word_class'),
    ]

    operations = [
        migrations.AddField(
            model_name='word',
            name='meaning_length',
            field=models.PositiveSmallIntegerField(default=0, editable=False, verbose_name='의미 길이'),
        ),
        migrations.RunPython(populate_meaning_length, migrations.RunPython.noop),
    ]

