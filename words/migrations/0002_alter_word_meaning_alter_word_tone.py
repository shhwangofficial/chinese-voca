# Generated by Django 5.1.7 on 2025-03-29 08:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('words', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='word',
            name='meaning',
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name='word',
            name='tone',
            field=models.CharField(max_length=20),
        ),
    ]
