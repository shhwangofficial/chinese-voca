from django.contrib import admin
from .models import Word


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('word', 'pinyin', 'tone', 'meaning', 'review_count', 'last_reviewed')
    list_filter = ('created_at', 'last_reviewed')
    search_fields = ('word', 'pinyin', 'meaning')
    ordering = ('-created_at',)
    fieldsets = (
        ('기본 정보', {
            'fields': ('word', 'pinyin', 'tone', 'meaning')
        }),
        ('복습 정보', {
            'fields': ('last_reviewed', 'review_count')
        }),
    )
