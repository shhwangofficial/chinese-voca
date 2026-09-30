# PythonAnywhere 배포와 복구

## 기존 서비스 업그레이드 전

이번 변경은 Python 3.12 + Django 5.2 기준입니다. 기존 웹앱의 Python 버전·가상환경을 확인하세요. Python 버전이 맞지 않으면 PythonAnywhere에서 3.12 웹앱/가상환경 구성이 먼저 필요합니다. 운영 DB나 `.env`를 Git에 넣지 마세요.

1. 사용자 쓰기 작업을 중단하고 기존 커밋 ID, 가상환경, Web 탭 설정을 기록합니다.
2. DB와 `.env`를 비공개 경로에 백업합니다. 아래 명령은 **운영 서버의 프로젝트 폴더**에서 실행합니다. `DATABASE_PATH`를 지정했다면 실제 DB 경로를 사용하세요.

```bash
git rev-parse HEAD
mkdir -p ../private-backups
chmod 700 ../private-backups
python - <<'PY'
import sqlite3
from datetime import datetime
from pathlib import Path
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
source = sqlite3.connect('file:db.sqlite3?mode=ro', uri=True)
path = Path('../private-backups') / f'vocabulary-{stamp}.sqlite3'
with sqlite3.connect(path) as target:
    source.backup(target)
source.close()
path.chmod(0o600)
print(path)
PY
```

`.env`는 별도로 안전하게 복사하고 기존 패키지 목록도 보관합니다 (`pip freeze > ../private-backups/requirements-before.txt`). 현재 운영 DB는 원격 코드 검토만으로 확인할 수 없습니다.

## 환경변수

기존 `SECRET_KEY`를 유지하세요. 무작정 키를 교체하면 모든 세션이 무효화됩니다.

```dotenv
SECRET_KEY=existing-secret-key
DEBUG=false
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
SECURE_SSL_REDIRECT=true
TRUST_PROXY_HTTPS=true
SECURE_HSTS_SECONDS=0
```

- `ALLOWED_HOSTS`: 실제 사용자명/커스텀 도메인만 쉼표로 나열합니다.
- `TRUST_PROXY_HTTPS=true`는 호스팅 프록시가 `X-Forwarded-Proto`를 올바르게 설정하고 클라이언트 입력을 정리하는 경우에만 사용합니다. PythonAnywhere Web 설정과 실제 HTTPS 요청을 확인하세요. 다른 호스팅 환경에 그대로 복사하지 마세요.
- HTTPS 리다이렉트 반복이 있으면 프록시 설정부터 확인합니다.
- HTTPS 동작 확인 뒤 `SECURE_HSTS_SECONDS=31536000`을 검토합니다. 하위 도메인·preload는 해당 도메인 전체를 HTTPS로 운영할 때만 설정합니다.

## 반영 순서

```bash
git pull --ff-only origin main
# 운영 웹앱과 동일한 가상환경을 활성화한 상태에서 실행
pip install -r requirements.txt
python manage.py check
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

PythonAnywhere의 Web 탭에서 다음을 확인하고 **Reload**합니다.

- WSGI가 `newpjt.settings`를 사용하고 있는지
- Python 버전과 Virtualenv 경로가 설치한 환경과 일치하는지
- 정적 URL `/static/`이 `<프로젝트 절대경로>/static`에 연결돼 있는지

`static/`은 이제 Git에 보관하지 않는 수집 결과물입니다. `collectstatic`을 생략하지 마세요. 기존 정적 URL 매핑은 그대로 유지할 수 있습니다. 프록시와 HSTS는 호스팅 환경에 따라 별도 확인이 필요하므로 `check --deploy` 경고를 숨기지 않습니다.

배포 후 로그인, 중국어/영어 단어 추가, 퀴즈 채점, 정답 인정, CSV 내보내기를 확인합니다. 개발자 도구에서 반복 요청·JS 오류도 확인합니다. 저장소 push 자체는 운영 배포가 아닙니다.

## 마이그레이션 내용

- 기존 모든 `Word`는 `language=zh`로 유지됩니다. 영어 데이터가 이미 섞여 있다면 관리자가 확인한 항목만 별도로 언어를 바꿔야 합니다.
- 중복 `(user, word)` 학습 연결이 있으면 가장 작은 ID를 유지하고 정답·오답·복습 횟수를 합산합니다. 최초 학습일, 최신 복습일, 가장 이른 복습 예정일과 가장 짧은 간격을 보존합니다.
- 기존 `StudyLog`와 공용 단어는 삭제하지 않습니다.
- 과거 `no_of_revision`의 초기값 1은 자동 보정하지 않습니다. 신규 항목만 0부터 시작합니다.
- 중복 행 병합은 되돌려도 원본 행을 재생성할 수 없으므로 **사전 DB 백업이 필수**입니다.

## 문제 발생 시 복구

웹앱의 쓰기 작업을 중단합니다. 기록한 이전 커밋과 이전 Python 가상환경으로 되돌리고, **같은 시점의 DB 백업**을 복원한 후 이전 코드로 `collectstatic`을 실행하고 Reload합니다. 새 DB를 둔 채 코드만 이전 버전으로 바꾸지 마세요. 백업 이후 데이터는 복구되지 않으므로 원본 장애 DB도 별도로 보관하세요.

정기 백업은 SQLite backup API 또는 쓰기 중단 상태의 파일 복사를 사용하고, 보관 기간·실제 복원 가능 여부를 주기적으로 확인합니다. 서버 계정·이메일 비밀번호 재설정은 이 저장소에서 자동 처리하지 않습니다.
