# 중국어 단어장 (Chinese Vocabulary)

중국어 단어 학습을 위한 웹 애플리케이션입니다. 단어를 추가하고, 퀴즈를 통해 복습하며, 간격 반복 학습 알고리즘으로 효율적으로 중국어 단어를 암기할 수 있습니다.

## 주요 기능

### 📚 단어 관리
- **단어 추가**: 중국어 단어, 병음, 성조, 의미, 품사를 입력하여 단어장에 추가
- **품사별 관리**: 동일한 단어라도 품사가 다르면 별도로 관리 (예: 好 - 명사/형용사)
- **의미 길이 힌트**: 퀴즈에서 의미 입력 시 글자 수 힌트 제공

### 🎯 스마트 학습 시스템
- **간격 반복 학습**: 정답 시 복습 간격을 점진적으로 늘려 효율적인 암기 지원
- **개인화된 학습**: 사용자별로 학습 중인 단어와 복습 일정을 독립적으로 관리
- **학습 통계**: 정답/오답 횟수, 복습 일수 등 학습 진행 상황 추적

### 📝 퀴즈 기능
- **오늘의 퀴즈**: 복습이 필요한 단어들을 자동으로 선별하여 퀴즈 제공
- **맞춤형 문제 수**: 1~20개 문제 중 원하는 수만큼 선택 가능
- **오답 재학습**: 틀린 문제만 골라서 다시 풀 수 있는 기능
- **상세한 결과 분석**: 정답과 내 답안을 비교하여 학습 효과 극대화

### 🏠 대시보드
- **학습 현황**: 총 학습 단어 수, 오늘 복습할 단어 수 한눈에 확인
- **최근 추가 단어**: 최근에 추가한 단어 목록 확인
- **오늘 복습할 단어**: 복습이 필요한 단어들을 미리 확인

## 기술 스택

### Backend
- **Django 4.2**: Python 웹 프레임워크
- **SQLite**: 데이터베이스 (개발 환경)
- **Django Cache Framework**: 성능 최적화를 위한 캐싱

### Frontend
- **Bootstrap 5**: 반응형 UI 프레임워크
- **Font Awesome**: 아이콘 라이브러리
- **Vanilla JavaScript**: 동적 UI 구현

### 주요 라이브러리
- `python-dotenv`: 환경 변수 관리
- `django-extensions`: 개발 도구

## 프로젝트 구조

```
chinese-voca/
├── accounts/          # 사용자 인증 앱
│   ├── models.py      # User, LearningWord 모델
│   ├── views.py       # 로그인/로그아웃/회원가입 뷰
│   └── templates/     # 인증 관련 템플릿
├── words/             # 단어 관리 앱
│   ├── models.py      # Word 모델
│   ├── views.py       # 단어 추가/퀴즈/결과 뷰
│   ├── forms.py       # 단어 입력 폼
│   └── templates/     # 단어 관련 템플릿
├── newpjt/            # 프로젝트 설정
│   ├── settings.py    # Django 설정
│   ├── urls.py        # URL 라우팅
│   └── middleware.py  # 로그인 필수 미들웨어
├── templates/          # 공통 템플릿
│   └── base.html      # 기본 레이아웃
├── static/            # 정적 파일
└── manage.py          # Django 관리 스크립트
```

## 설치 및 실행

### 필수 요구사항
- Python 3.8 이상
- pip

### 설치 단계

1. **저장소 클론**
```bash
git clone <repository-url>
cd chinese-voca
```

2. **가상환경 생성 및 활성화**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **의존성 설치**
```bash
pip install -r requirements.txt
```

4. **환경 변수 설정**
프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:
```env
SECRET_KEY=your-secret-key-here
```

Django 시크릿 키 생성 방법:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

5. **데이터베이스 마이그레이션**
```bash
python manage.py migrate
```

6. **관리자 계정 생성** (선택사항)
```bash
python manage.py createsuperuser
```

7. **개발 서버 실행**
```bash
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000` 접속

## 사용 방법

### 1. 회원가입 및 로그인
- `/accounts/signup/`에서 새 계정 생성
- `/accounts/login/`에서 로그인

### 2. 단어 추가
- 홈 화면에서 "단어 추가" 버튼 클릭
- 단어와 품사를 입력하여 학습 목록에 추가
- DB에 없는 단어는 상세 정보(병음, 성조, 의미)를 입력하여 추가

### 3. 퀴즈 풀기
- 홈 화면의 "오늘의 퀴즈" 섹션에서 문제 수 선택 (1~20개)
- "퀴즈 시작" 버튼 클릭
- 병음과 의미를 입력하여 정답 확인

### 4. 결과 확인 및 복습
- 퀴즈 완료 후 결과 화면에서 정답률 확인
- 틀린 문제는 "틀린 문제 다시 풀기" 버튼으로 재학습
- 정답 시 자동으로 다음 복습 일정이 조정됨

## 데이터베이스 모델

### Word 모델
- `word`: 중국어 단어 (최대 20자)
- `pinyin`: 병음 (최대 40자)
- `tone`: 성조
- `meaning`: 한국어 의미 (최대 40자)
- `meaning_length`: 의미 길이 (자동 계산)
- `word_class`: 품사 (명사, 동사, 형용사 등)
- `created_at`: 생성일시
- `updated_at`: 수정일시

**제약 조건**: `word`와 `word_class`의 조합은 고유해야 함 (동일 단어라도 품사가 다르면 별도 관리)

### LearningWord 모델
- `user`: 사용자 (ForeignKey)
- `word`: 단어 (ForeignKey)
- `learning_since`: 학습 시작일
- `last_time_revised`: 마지막 복습일
- `to_be_revised`: 다음 복습 예정일
- `learning_term`: 학습 간격 (일 수)
- `no_of_revision`: 총 복습 횟수
- `wrong_count`: 오답 횟수
- `correct_count`: 정답 횟수

## 간격 반복 학습 알고리즘

- **정답 시**: `learning_term = learning_term * 2 + 1` (복습 간격 점진적 증가)
- **오답 시**: `learning_term = 0` (다음날 즉시 복습)
- 복습 예정일은 `learning_term`일 후의 00시로 설정

## 성능 최적화

- **캐싱**: 사용자 통계, 최근 단어, 오늘의 단어 목록을 1시간 캐시
- **데이터베이스 인덱싱**: 자주 조회되는 필드에 인덱스 적용
- **쿼리 최적화**: `select_related`, `prefetch_related` 활용

## 보안

- **환경 변수**: SECRET_KEY는 `.env` 파일로 관리
- **CSRF 보호**: Django 기본 CSRF 보호 활성화
- **로그인 필수**: 대부분의 페이지는 로그인 필수 (미들웨어 적용)
- **세션 관리**: 안전한 세션 쿠키 설정


## 라이선스

이 프로젝트는 개인 학습 목적으로 제작되었습니다.

## 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.

---
