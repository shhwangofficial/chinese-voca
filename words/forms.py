import re
import unicodedata

from django import forms

from accounts.models import LearningWord
from .models import Word
from .services import normalize_pinyin, normalize_tone


def validate_pronunciation(data, language, prefix=""):
    pinyin_key, tone_key = prefix + "pinyin", prefix + "tone"
    pinyin = normalize_pinyin(data.get(pinyin_key, ""))
    tone = normalize_tone(data.get(tone_key, ""))
    if language == "en":
        return "", ""
    if not pinyin or not re.fullmatch(
        r"[a-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜêńňǹḿ\s]+", pinyin
    ):
        raise forms.ValidationError(
            "중국어 병음을 입력하세요. 음절은 공백으로 구분합니다."
        )
    if tone and (
        not re.fullmatch(r"[1-5](?: [1-5])*", tone)
        or len(tone.split()) != len(pinyin.split())
    ):
        raise forms.ValidationError(
            "성조는 병음 음절 수에 맞게 1~5를 공백으로 구분해 입력하세요."
        )
    return pinyin, tone


class StyledForm:
    def style_fields(self):
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )


class WordForm(StyledForm, forms.ModelForm):
    class Meta:
        model = Word
        fields = ["language", "word", "word_class", "pinyin", "tone", "meaning"]
        help_texts = {
            "pinyin": "예: ni hao (영어는 비워두세요)",
            "tone": "예: 3 3. 경성은 5, 생략 가능",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_word(self):
        return unicodedata.normalize("NFC", self.cleaned_data["word"]).strip()

    def clean(self):
        data = super().clean()
        pinyin, tone = validate_pronunciation(data, data.get("language"))
        data.update(pinyin=pinyin, tone=tone)
        return data

    def _post_clean(self):
        # Existing shared words are allowed: this form never overwrites them.
        exclude = self._get_validation_exclusions()
        from django.forms.models import construct_instance

        self.instance = construct_instance(
            self, self.instance, self._meta.fields, self._meta.exclude
        )
        try:
            self.instance.full_clean(
                exclude=exclude, validate_unique=False, validate_constraints=False
            )
        except forms.ValidationError as exc:
            self._update_errors(exc)


class LearnWordForm(StyledForm, forms.Form):
    language = forms.ChoiceField(
        choices=Word._meta.get_field("language").choices, label="언어"
    )
    word = forms.CharField(max_length=100, label="단어")
    word_class = forms.ChoiceField(choices=Word.WORD_CLASS_CHOICES, label="품사")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_word(self):
        return unicodedata.normalize("NFC", self.cleaned_data["word"]).strip()


class LearningEditForm(StyledForm, forms.ModelForm):
    class Meta:
        model = LearningWord
        fields = [
            "personal_pinyin",
            "personal_tone",
            "personal_meaning",
            "accepted_meanings",
            "tags",
            "notes",
            "is_paused",
        ]
        labels = {
            "personal_pinyin": "나의 병음",
            "personal_tone": "나의 성조",
            "personal_meaning": "나의 뜻",
            "accepted_meanings": "추가 정답",
            "tags": "태그",
            "notes": "예문·메모",
            "is_paused": "복습 일시정지",
        }
        help_texts = {
            "accepted_meanings": "한 줄에 하나씩 입력하세요.",
            "tags": "예: HSK5, 업무",
            "personal_meaning": "비워두면 공용 사전의 뜻을 사용합니다.",
            "personal_pinyin": "비워두면 공용 병음·성조를 사용합니다.",
        }
        widgets = {
            "accepted_meanings": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean(self):
        data = super().clean()
        if data.get("personal_pinyin"):
            pinyin, tone = validate_pronunciation(
                data, self.instance.word.language, "personal_"
            )
            data.update(personal_pinyin=pinyin, personal_tone=tone)
        elif data.get("personal_tone"):
            self.add_error("personal_tone", "성조를 수정하려면 병음도 함께 입력하세요.")
        return data


class GradeForm(forms.Form):
    request_id = forms.UUIDField()
    word_id = forms.IntegerField(min_value=1)
    version = forms.IntegerField(min_value=0)
    pinyin = forms.CharField(max_length=255, required=False)
    meaning = forms.CharField(max_length=255)
    tone = forms.CharField(max_length=50, required=False)
    test_tone = forms.BooleanField(required=False)


class ImportForm(StyledForm, forms.Form):
    file = forms.FileField(
        label="UTF-8 CSV 파일",
        help_text="최대 1MB / 500행. 먼저 미리보기 후 저장합니다.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > 1024 * 1024:
            raise forms.ValidationError("파일 크기는 1MB 이하여야 합니다.")
        return file
