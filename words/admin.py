from django.contrib import admin
from .models import Word


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('word', 'pinyin', 'tone', 'meaning', 'word_class', 'created_at')
    list_filter = ('word_class', 'created_at')
    search_fields = ('word', 'pinyin', 'meaning')
    ordering = ('-created_at',)
    fieldsets = (
        ('기본 정보', {
            'fields': ('word', 'pinyin', 'tone', 'meaning', 'word_class')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'updated_at')
        }),
    )
