# 나의 단어장 · Chinese & English Vocabulary

Django 기반 중국어·영어 단어 학습 웹앱입니다. 공용 사전과 개인별 뜻·병음·메모를 분리하고, 한국 시간 오전 4시를 기준으로 복습 일정을 관리합니다.

## 주요 기능

- 중국어·영어 단어 등록, 검색, 품사·언어·복습 상태 필터, 페이지 나누기
- 개인별 뜻·병음·성조 수정, 추가 정답(한 줄에 하나), 태그·예문·메모
- 학습 일시정지 및 내 목록에서 제외 (공용 단어와 과거 학습 기록은 보존)
- 10/20/50개 또는 전체 퀴즈, 신규/복습 선택, 선택적 성조 시험
- 오답 재출제, 정답 인정, 첫 시도 정답률·시도 횟수·문제별 결과
- 같은 브라우저 탭에서 퀴즈 이어하기, 중복 제출·네트워크 재시도 방지
- 오답/전체 플래시카드, 기기 음성을 이용한 중국어·영어 발음 듣기
- UTF-8 CSV 미리보기 가져오기 및 검색 결과 내보내기
- 회원가입·로그인·POST 로그아웃·비밀번호 변경, 로그인 시도 제한

## 기술 구성

Python 3.12 기준으로 검증합니다. Django 5.2 LTS, SQLite, Django Templates, Bootstrap 5, Vanilla JavaScript를 사용합니다. Bootstrap과 아이콘은 저장소에 포함해 외부 CDN 없이 제공합니다. 운영 의존성은 `requirements.txt`, 개발 도구는 `requirements-dev.txt`에 분리했습니다.

```text
accounts/                  인증, 개인 학습 상태, 학습 기록
words/models.py            공용 단어 사전 (언어+단어+품사 고유)
words/forms.py             서버 입력 검증
words/services.py          날짜·정규화·복습 일정·원자적 채점
words/views.py             화면/API/CSV
words/static/words/         퀴즈·플래시카드 JS/CSS
newpjt/                    환경변수 설정, 인증 미들웨어
tests/                     JavaScript 상태 전이 테스트
docs/DEPLOYMENT.md          PythonAnywhere 배포·백업·복구
docs/CHANGELOG.md           변경 내역 및 제한 사항
```

## 로컬 실행

```bash
git clone https://github.com/shhwangofficial/chinese-voca.git
cd chinese-voca
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

생성한 키를 `.env`의 `SECRET_KEY`에 입력하세요. 로컬에서는 `DEBUG=true`, `SECURE_SSL_REDIRECT=false`를 사용합니다. `.env`와 DB를 커밋하지 않습니다.

```bash
python manage.py migrate
python manage.py createsuperuser  # 선택: 공용 사전 관리
python manage.py runserver
```

<http://127.0.0.1:8000>에서 회원가입 후 단어를 추가합니다. 운영 서버 갱신은 반드시 [배포 문서](docs/DEPLOYMENT.md)를 먼저 확인하세요. Git push만으로 PythonAnywhere 웹앱이 갱신되지는 않습니다.

## 사용 규칙

1. **추가**: 언어·단어·품사로 사전을 검색합니다. 없는 단어면 상세 정보를 입력합니다.
2. **중국어**: 병음을 공백으로 구분합니다 (`ni hao`). 성조는 선택이며 입력하면 음절 수에 맞는 1~5 숫자를 사용합니다 (`3 3`). 경성은 5입니다. `v`·`u:`는 `ü`로 정규화합니다. 성조가 포함된 병음도 저장할 수 있지만 무성조 병음과 자동으로 동등 취급하지 않습니다.
3. **영어**: 병음과 성조를 비워둡니다. 뜻만 채점합니다.
4. **추가 정답**: 개인 수정 화면에서 `안녕`, `안녕하세요` 등을 각각 별도 줄에 입력합니다. 저장된 기본 뜻 또는 추가 정답 중 하나와 일치하면 맞습니다. 대소문자·연속 공백·유니코드 NFC를 정규화하며 임의의 부분 일치나 AI 의미 판정은 하지 않습니다.
5. **개인 수정**: 다른 사용자가 보는 공용 사전은 바꾸지 않습니다. 공용 사전 수정은 Django 관리자에서 합니다.
6. **이어하기**: 같은 계정·학습일·퀴즈 옵션의 상태를 현재 탭의 sessionStorage에 저장합니다. 탭을 닫거나 로그아웃하면 보장되지 않습니다. 새 탭/다른 기기 동기화는 지원하지 않습니다. 이미 서버에 저장된 채점은 다시 기록하지 않습니다.
7. **정답 인정**: 가장 최근에 처리한, 이후 수정되지 않은 해당 학습 항목의 오답만 바꿀 수 있습니다. 이미 인정한 요청은 재전송해도 한 번만 적용됩니다.

## 복습 알고리즘

`learning_term`은 다음 정답에서 사용할 간격입니다. 실제 예정일은 `to_be_revised`가 기준입니다.

- 학습일: 한국 시간에서 4시간을 뺀 날짜 (04:00 변경)
- 신규/오답 후 정답: 다음 학습일 04:00에 복습, 다음 간격은 3일
- 그 외 정답: 현재 간격만큼 지난 학습일 04:00에 복습
- 다음 간격: `ceil(현재 간격 × (1.5 + 0.5 / (1 + 누적 오답 수)) + 1)`
- 간격 상한: 365일
- 오답: 간격 0, 즉시 복습 가능, 퀴즈 큐 뒤에 재배치
- 정답 인정: 해당 시도 이전의 서버 상태에서 정답으로 재계산. 시도 수를 두 번 늘리거나 오답 로그를 삭제하지 않음

오답 없는 단어의 실제 복습 간격은 1 → 3 → 7 → 15 → 31일 순입니다. 플래시카드는 일정과 채점 기록을 바꾸지 않습니다. 대시보드의 정답 횟수는 고유 단어 수가 아닌 학습 기록 건수입니다.

## CSV 양식

필수 헤더는 아래 앞 6개, 뒤 3개는 선택입니다. 언어는 `zh`/`en`, 품사는 `noun`, `pronoun`, `verb`, `adjective`, `numeral`, `adverb`, `preposition`, `interjection`을 사용합니다.

```csv
language,word,word_class,pinyin,tone,meaning,accepted_meanings,notes,tags
zh,你好,interjection,ni hao,3 3,안녕하세요,안녕,인사 표현,기초
en,apple,noun,,,사과,,,음식
```

- UTF-8 또는 UTF-8 BOM, 최대 1MB·500행. 엑셀에서 `CSV UTF-8`로 저장합니다. `.xlsx` 자체는 지원하지 않습니다.
- 미리보기에서 **모든 행**이 유효해야 확인 후 저장할 수 있습니다. 미리보기는 30분 유효합니다.
- 파일 내 중복은 오류, 이미 본인이 학습 중인 단어는 건너뜁니다. 기존 뜻·메모를 덮어쓰지 않습니다.
- 수식 실행 방지를 위해 위험한 셀은 내보낼 때 앞에 `'`를 붙이고 재가져오기 시 제거합니다.
- CSV는 단어 데이터 이동용입니다. 복습 일정·계정·전체 학습 기록 복구는 DB 백업을 사용하세요.

## 데이터와 보안

- `Word`: 공용 단어, 병음, 성조, 뜻, 언어, 품사
- `LearningWord`: 사용자-단어 고유 연결, 복습 일정, 개인 수정·메모, 동시 수정 버전
- `StudyLog`: 요청 UUID, 채점 결과, 수정 전 상태, 정답 인정 시각. 과거 로그는 보존
- `AuthThrottle`: 웹 프로세스 간 공유되는 DB 기반 인증 시도 제한

세션 인증과 CSRF 보호를 사용합니다. 화면에 단어를 표시할 때 `textContent` 또는 Django 자동 이스케이프를 사용합니다. 운영에서는 HTTPS 쿠키와 HTTPS 리다이렉트가 기본이며, 정확한 호스트와 프록시 설정이 필요합니다. 학습 통계는 매번 조회하므로 프로세스별 캐시 불일치가 없습니다.

## 테스트

```bash
pip install -r requirements-dev.txt
python -m ruff check .
python manage.py check --settings=newpjt.test_settings
python manage.py makemigrations --check --dry-run --settings=newpjt.test_settings
python manage.py test --settings=newpjt.test_settings
node --test tests/quiz-state.test.mjs
```

테스트 설정은 메모리 DB와 테스트 전용 키를 사용하며 운영 설정으로 사용하면 안 됩니다. GitHub Actions에서 동일한 검사를 실행합니다. 테스트는 사용자 격리, CSRF, 중복 요청, 정답 인정, 트랜잭션 롤백, 날짜 경계, CSV, 기존 DB의 중복 연결 마이그레이션을 포함합니다.

## 라이선스

아직 오픈소스 라이선스를 지정하지 않았습니다. 공개 저장소라는 이유만으로 자유로운 재배포·재사용을 허용한다고 해석하지 마세요. 라이선스 선택은 저장소 소유자가 결정합니다.
