# Generated by Django 4.2 on 2025-06-16 04:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="learningword",
            name="learning_term",
            field=models.IntegerField(default=0),
        ),
    ]
