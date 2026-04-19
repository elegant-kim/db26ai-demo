# Oracle Select AI 데모

Oracle Autonomous Database의 **Select AI (NL2SQL)** 기능을 데모로 보여주기 위한 웹 앱입니다.
자연어로 질문하면 Oracle Select AI가 SQL을 생성하고 실행하여 결과를 보여줍니다.

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python FastAPI |
| 프론트엔드 | HTML + Vue 3 (CDN) |
| DB 연결 | python-oracledb (thin 모드) |
| 차트 | Chart.js (CDN) |
| LLM 프로바이더 | Groq (OpenAI-compatible API) |

## 프로젝트 구조

```
select-ai-demo/
├── main.py                  # FastAPI 서버 진입점
├── app/
│   ├── __init__.py
│   ├── config.py            # 환경설정 (.env 로드)
│   ├── database.py          # DB 연결 풀 관리
│   ├── select_ai.py         # Select AI 호출 로직
│   └── routes.py            # API 엔드포인트 정의
├── static/
│   ├── css/
│   │   └── style.css        # 커스텀 스타일
│   └── js/
│       └── app.js           # Vue 3 앱
├── templates/
│   └── index.html           # 메인 HTML
├── .env.example             # 환경변수 템플릿
├── .gitignore
├── requirements.txt
└── README.md
```

## 실행 방법

### 1. 레포 클론

```bash
git clone https://github.com/<username>/select-ai-demo.git
cd select-ai-demo
```

### 2. 파이썬 가상환경 (권장)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 DB 접속 정보 입력
```

`.env` 파일에 다음 항목을 설정합니다:

| 변수 | 설명 | 예시 |
|------|------|------|
| `ORACLE_DSN` | Oracle DB 접속 주소 | `adb.ap-seoul-1.oraclecloud.com:1522/xxx_high.adb.oraclecloud.com` |
| `ORACLE_USER` | DB 사용자명 | `DEMO_USER` |
| `ORACLE_PASSWORD` | DB 비밀번호 | |
| `SELECT_AI_PROFILE` | AI 프로필명 | `GROQ_PROFILE` |

Wallet 사용 시 `ORACLE_WALLET_DIR`과 `ORACLE_WALLET_PASSWORD`를 대신 설정합니다.

### 5. 실행

```bash
python main.py
```

### 6. 브라우저에서 접속

```
http://localhost:8247
```

## DB 사전 설정

앱 실행 전에 Oracle Autonomous Database에서 다음 설정이 필요합니다.

### 1. DB 사용자에게 권한 부여 (ADMIN으로 실행)

```sql
GRANT EXECUTE ON DBMS_CLOUD TO <your_user>;
GRANT EXECUTE ON DBMS_CLOUD_AI TO <your_user>;
```

### 2. Groq API 네트워크 접근 허용

```sql
BEGIN
  DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
    host => 'api.groq.com',
    ace  => xs$ace_type(
      privilege_list => xs$name_list('http'),
      principal_name => '<your_user>',
      principal_type => xs_acl.ptype_db)
  );
END;
/
```

### 3. Groq 자격증명 생성

```sql
EXEC DBMS_CLOUD.CREATE_CREDENTIAL(
  credential_name => 'GROQ_CRED',
  username        => 'GROQ',
  password        => '<your_groq_api_key>'
);
```

### 4. AI Profile 생성 (Groq - OpenAI-compatible)

```sql
BEGIN
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'GROQ_PROFILE',
    attributes   => '{
      "provider": "openai",
      "credential_name": "GROQ_CRED",
      "model": "llama-3.3-70b-versatile",
      "provider_endpoint": "https://api.groq.com/openai",
      "object_list": [{"owner": "<your_schema>"}],
      "conversation": "true",
      "comments": true,
      "temperature": 0.2
    }'
  );
END;
/
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/ask` | 자연어 질문을 Select AI에 전달 |
| `POST` | `/api/feedback` | 피드백 제출 |
| `GET` | `/api/profiles` | AI 프로필 목록 조회 |
| `GET` | `/api/health` | 서버 상태 및 DB 연결 확인 |

### POST /api/ask

```json
{
  "prompt": "국가별 총 매출액 상위 5개를 보여줘",
  "action": "runsql",
  "profile_name": "GROQ_PROFILE"
}
```

`action` 종류:
- `runsql` — SQL 생성 후 실행, 결과 반환
- `showsql` — 생성된 SQL만 반환
- `narrate` — 결과를 자연어로 서술
- `explainsql` — SQL을 단계별로 설명
- `showprompt` — LLM에 전송된 프롬프트 표시
- `summarize` — 결과 데이터 요약
- `chat` — LLM과 직접 대화

## 주의사항

- `python-oracledb`는 thin 모드로 사용하므로 Oracle Instant Client 설치가 불필요합니다.
- `.env` 파일은 `.gitignore`에 포함되어 있습니다. `.env.example`만 커밋됩니다.
- Vue 3, Chart.js는 CDN으로 로드되므로 npm/Vite 등 빌드 도구가 불필요합니다.
