from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()  # custom했던 User 모델 객체를 가져와준다.
        fields = ('username', 'password1', 'password2')  # 이메일 필드 제거
