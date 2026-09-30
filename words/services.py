"""Shared normalization, study-day boundaries and transactional grading."""

import math
import re
import unicodedata
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import LearningWord, StudyLog

MAX_INTERVAL = 365


def logical_date(moment=None):
    return (timezone.localtime(moment or timezone.now()) - timedelta(hours=4)).date()


def normalize_text(value):
    return " ".join(unicodedata.normalize("NFC", value).split()).casefold()


def normalize_pinyin(value):
    return normalize_text(value).replace("u:", "ü").replace("v", "ü")


def normalize_tone(value):
    return " ".join(re.split(r"[\s,]+", value.strip())) if value.strip() else ""


def serialize_word(learning, answers=False):
    data = {
        "id": learning.word_id,
        "version": learning.version,
        "word": learning.word.word,
        "language": learning.word.language,
        "word_class": learning.word.get_word_class_display(),
        "syllables": len(learning.display_pinyin.split()),
        "tone": learning.display_tone,
        "meaning_length": len(learning.display_meaning.strip()),
    }
    if answers:
        data.update(
            pinyin=learning.display_pinyin,
            meaning=learning.display_meaning,
            notes=learning.notes,
            wrong_count=learning.wrong_count,
        )
    return data


def snapshot(learning):
    return {
        "learning_id": learning.pk,
        **{
            name: getattr(learning, name)
            for name in (
                "learning_term",
                "no_of_revision",
                "wrong_count",
                "correct_count",
            )
        },
    }


def calculate_result(before, correct, now):
    state = {
        key: before[key]
        for key in ["learning_term", "no_of_revision", "wrong_count", "correct_count"]
    }
    state["no_of_revision"] += 1
    state["last_time_revised"] = now
    delta = 0
    if correct:
        state["correct_count"] += 1
        current = max(0, min(MAX_INTERVAL, before["learning_term"]))
        delta = current or 1
        multiplier = 1.5 + 0.5 / (1 + max(0, before["wrong_count"]))
        state["learning_term"] = (
            min(MAX_INTERVAL, math.ceil(current * multiplier + 1)) if current else 3
        )
        target = logical_date(now) + timedelta(days=delta)
        state["to_be_revised"] = timezone.make_aware(datetime.combine(target, time(4)))
    else:
        state["wrong_count"] += 1
        state["learning_term"] = 0
        state["to_be_revised"] = now
    return state, delta


class StudyConflict(Exception):
    pass


def save_state(learning, state):
    """CAS also protects databases where SELECT FOR UPDATE is unavailable."""
    state["version"] = learning.version + 1
    updated = LearningWord.objects.filter(
        pk=learning.pk, version=learning.version
    ).update(**state)
    if not updated:
        raise StudyConflict("다른 창에서 학습 상태가 바뀌었습니다. 새로고침해주세요.")
    return state["version"]


@transaction.atomic
def grade(user, data):
    old_log = StudyLog.objects.filter(request_id=data["request_id"]).first()
    if old_log:
        if old_log.user_id != user.pk or old_log.word_id != data["word_id"]:
            raise StudyConflict("이미 사용한 요청 ID입니다.")
        return old_log.response_data
    learning = (
        LearningWord.objects.select_for_update()
        .select_related("word")
        .get(user=user, word_id=data["word_id"])
    )
    if learning.is_paused or learning.version != data["version"]:
        raise StudyConflict("학습 상태가 바뀌었습니다. 새로고침해주세요.")
    meanings = [learning.display_meaning, *learning.accepted_meanings.splitlines()]
    meaning_ok = normalize_text(data["meaning"]) in {
        normalize_text(m) for m in meanings if m.strip()
    }
    pinyin_ok = learning.word.language == "en" or normalize_pinyin(
        data["pinyin"]
    ) == normalize_pinyin(learning.display_pinyin)
    tone_ok = (
        not data.get("test_tone")
        or learning.word.language == "en"
        or normalize_tone(data["tone"]) == normalize_tone(learning.display_tone)
    )
    correct = meaning_ok and pinyin_ok and tone_ok
    before = snapshot(learning)
    now = timezone.now()
    state, delta = calculate_result(before, correct, now)
    version = save_state(learning, state)
    log = StudyLog.objects.create(
        user=user,
        word=learning.word,
        date=logical_date(now),
        is_correct=correct,
        request_id=data["request_id"],
        previous_state=before,
    )
    result = {
        "status": "success",
        "is_correct": correct,
        "attempt_id": log.pk,
        "version": version,
        "next_review_delta": delta,
        "correct_pinyin": learning.display_pinyin,
        "correct_meaning": learning.display_meaning,
        "word_tone": learning.display_tone,
    }
    log.response_data = result
    log.save(update_fields=["response_data"])
    return result


@transaction.atomic
def mark_correct(user, attempt_id):
    log = StudyLog.objects.select_for_update().get(pk=attempt_id, user=user)
    if log.corrected_at:
        return log.response_data
    if log.is_correct or not log.previous_state:
        raise StudyConflict("정답으로 변경할 수 없는 기록입니다.")
    learning = LearningWord.objects.select_for_update().get(user=user, word=log.word)
    if learning.pk != log.previous_state.get(
        "learning_id"
    ) or learning.version != log.response_data.get("version"):
        raise StudyConflict("이후 학습 또는 수정이 있어 변경할 수 없습니다.")
    # Preserve the original attempt's study date, even across the 04:00 boundary.
    state, delta = calculate_result(log.previous_state, True, log.timestamp)
    version = save_state(learning, state)
    result = {
        **log.response_data,
        "is_correct": True,
        "version": version,
        "next_review_delta": delta,
    }
    log.is_correct = True
    log.corrected_at = timezone.now()
    log.response_data = result
    log.save(update_fields=["is_correct", "corrected_at", "response_data"])
    return result
