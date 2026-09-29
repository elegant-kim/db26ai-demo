# Oracle AI Database 26ai 데모 앱 — 크라운제과 PoC 대응 기능 확장 요청서

> 이 문서는 Claude Code에 전달하는 작업 지시서다. 각 Phase 는 독립적으로 실행하며,
> **Phase 0 (분석·갭 보고)** 가 끝나면 반드시 멈추고 사용자의 승인을 받은 뒤 다음 Phase 로 진행한다.

---

## 0. 배경과 목표

이 저장소는 Oracle AI Database 26ai 신기능 시연용 웹앱이다. 현재 구조:

- 상단 네비: `NL2SQL` / `Vector Search` / `Duality` / `Property Graph` / `생산성` / `AWR 분석` / `매뉴얼`
- 우측 상단 상태 배지: DB 연결, ONNX·E5_BASE, 현재 모델(gemini-2.5-flash), ⌘K 검색, 프레젠테이션 모드
- `NL2SQL` 페이지: 우상단 **AI 프로필 선택**(예: `GEMINI_SH_PROFILE`), 탭 3개
  - **환경**: AI 프로필 / LLM 크리덴셜 / 네트워크 ACL 3단 진단 카드(각 "조회 SQL" 펼침), 상단 요약 배지, "실제 호출 테스트"(chat 액션 핑)
  - **질문**: 액션 버튼 7개 `showsql / runsql / narrate / explainsql / showprompt / summarize / chat`, 예시 질문 드롭다운, 자연어 입력, `SELECT AI <액션> <질문>` 직접 실행 라인
  - **스키마·Annotation**: 프로필 object_list 테이블 목록(SH 샘플 8개)과 Display Annotation 표시 / 적용 / 제거 / 새로고침
- 기술: `DBMS_CLOUD_AI.GENERATE` 단발 호출(1질문=1응답). 프로필 속성 `conversation=true` 이지만 UI 에서 대화 컨텍스트를 유지하지 않음. 피드백·질의 이력·Agent 기능 없음. 현재 LLM 은 provider=`openai`(OpenAI 호환 엔드포인트로 Gemini 호출).

### 목표
한국오라클이 고객(크라운제과)에게 제공했던 PoC 앱 "Crown AI PoC" 의 핵심 기능을 이 앱에 흡수하고, 더 나아가
고객 인수인계·정확도 개선·운영 전환 시연에 필요한 기능을 추가한다. 참고로 오라클 PoC 앱은 다음을 제공했다:

- `Select AI Agent(RUN_TEAM)` 기반 채팅, Multi Turn 토글(conversation_id 유지), "새 대화", "정상답변시 대화초기화", "이어서 질문하기"
- 답변 아래 메타(conv_id, elapsed ms, team, multi turn), "Thinking" 접기, "단계별 시간(5단계·총 ms)·이 대화 누적"
- **답변 인라인 피드백: 👍좋음 / 👎나쁨 + "사유(선택)" + 저장**
- 저장 질문 프리셋(제목 + 추가/수정/삭제 + 드롭다운)
- **Agent History 화면**: 시작시각·Team·질문·상태(SUCCEEDED)·소요(ms)·피드백 아이콘·conversation_id, 질문 LIKE 검색·기간 필터, 행 클릭 → 피드백 모달(좋음/나쁨·의견·삭제/닫기/저장)
- 접속: `?customer=xxx` + 접속 key, 상단 DB 선택, 로그아웃

---

## Phase 0 — 현재 앱 분석 및 갭 보고 (구현 금지, 보고 후 정지)

1. 저장소 구조를 파악해 요약하라: 프론트/백엔드 스택, 라우팅, 상태관리, 스타일 시스템(디자인 토큰·컴포넌트), DB 접속 방식(드라이버, 풀, 세션/프로필 설정 방법), 설정·비밀값 관리 방식, 빌드/실행 명령, 테스트 유무.
2. `NL2SQL` 페이지 관련 코드를 찾아 다음을 목록화하라:
   - `DBMS_CLOUD_AI.*` 호출 지점(SET_PROFILE / GENERATE / SET_ATTRIBUTE / 기타)과 액션별 처리 흐름
   - 프로필 선택이 세션에 어떻게 반영되는지(SET_PROFILE 호출 시점, 세션 고정 여부)
   - 환경 탭 진단 카드가 참조하는 뷰/테이블(예: `USER_CLOUD_AI_PROFILES`, `USER_CREDENTIALS`, `DBA_HOST_ACES`)
   - Annotation 탭이 어떤 DDL/뷰를 쓰는지(`ANNOTATIONS`, `USER_ANNOTATIONS_USAGE` 등)
   - 예시 질문 드롭다운의 데이터 소스(하드코딩/DB)
   - 프레젠테이션 모드·⌘K 검색이 새 화면 추가 시 어떤 등록 절차를 요구하는지
3. 아래 "요구 기능 목록"(Phase 1~4)의 각 항목에 대해 `[이미 있음 / 부분 있음 / 없음]` 판정, 예상 작업량(S/M/L), 구현 시 건드릴 파일, 리스크를 표로 보고하라.
4. 새로 필요한 DB 객체(테이블/시퀀스/권한)를 초안으로 제시하라.
5. **여기서 멈추고 사용자 승인을 기다려라.** 질문이 있으면 이 시점에 한꺼번에 물어라.

---

## Phase 1 — 대화형 질문 + 피드백 + 질의 이력 (최우선)

### 1-A. 질문 탭을 "대화" 방식으로 개편
- 현재 단발 결과 영역을 **대화 말풍선 리스트**로 바꾼다. 사용자 질문 / AI 답변 각각 말풍선, 하단에 `AI · 13:59` 형식 타임스탬프.
- 첫 진입 시 그리팅 메시지: "안녕하세요! Oracle Select AI 입니다. 프로필과 실행 모드를 선택하고 질문하세요."
- 기존 7개 액션 버튼, 예시 질문 드롭다운, `SELECT AI <액션> <질문>` 직접 실행 라인은 **그대로 유지**한다(입력 영역 위/옆에 배치).
- 입력 UX: Enter 전송, Shift+Enter 줄바꿈. 실행 중에는 스피너 + "생성 중…" 표시, 중복 전송 방지.
- **멀티턴**:
  - 입력 영역 옆 토글 **Multi Turn**(기본 ON), 버튼 **새 대화**, 체크박스 **이어서 질문하기**(OFF 면 이번 질문만 독립 실행), 토글 **정상답변시 대화초기화**(ON 이면 성공 답변 후 conversation 을 자동 리셋하고 안내 문구 "정상 답변으로 대화가 초기화되었습니다 — 다음 질문은 새 conversation 으로 시작합니다"를 답변 아래에 표시).
  - 구현: 26ai `DBMS_CLOUD_AI` 의 conversation 기능을 사용한다. 프로필 속성 `conversation=true` 가 이미 켜져 있으므로, `DBMS_CLOUD_AI.CREATE_CONVERSATION` 으로 conversation_id 를 만들고 `GENERATE`/프로필 속성 `conversation_id` 로 전달하는 방식을 **문서와 DB 에서 확인한 뒤** 구현하라(정확한 프로시저/속성명은 `DBMS_CLOUD_AI` 패키지 스펙을 `DBA_PROCEDURES`/`ALL_ARGUMENTS` 로 조회해 검증. 추측으로 하드코딩 금지).
  - conversation_id 생성·재사용·리셋 로직은 서비스 계층 한 곳으로 모으고, 프로필·토글 상태와 함께 사용자 세션에 보관한다.
- **답변 메타 표시**: 답변 말풍선 아래 작은 글씨로 `conversation_id · elapsed 1,234 ms · 액션 runsql · 프로필 GEMINI_SH_PROFILE · multi turn ON`. elapsed 는 서버에서 측정.
- **"생성 SQL / 프롬프트" 접기**: runsql·narrate 답변에는 생성된 SQL 을 접기/펼치기로 붙인다(showsql 을 추가 호출하거나 GENERATE 결과에서 추출). showprompt 결과가 있으면 "프롬프트 보기" 접기도 제공.

### 1-B. 답변 인라인 피드백 (26ai 전용 기능)
- 각 AI 답변 아래에 **이 답변 평가: 👍 좋음 / 👎 나쁨** 버튼, **사유(선택)** 텍스트영역(1~3줄), **저장** 버튼. 저장 후 상태 배지(👍 등록됨 / 👎 등록됨 · 사유 미리보기) 표시, 클릭 시 수정(=삭제 후 재등록) 또는 삭제.
- 👎 인 경우 선택적으로 **"올바른 SQL 직접 제시"** 입력란(접기)을 제공 → `response` 파라미터로 전달.
- **Oracle 공식 API 사용**:
  ```sql
  DBMS_CLOUD_AI.FEEDBACK(
      profile_name     => :profile,
      sql_id           => :sql_id,          -- 또는 sql_text => :sql_text (오버로드)
      feedback_type    => 'positive' | 'negative',
      response         => :corrected_sql,   -- 선택
      feedback_content => :reason,          -- ★ 사유(자유 텍스트)
      operation        => 'add' | 'delete'
  );
  ```
  - `sql_id` 는 `V$MAPPED_SQL` 에서 조회(권한: `GRANT READ ON SYS.V_$MAPPED_SQL`, `GRANT READ ON SYS.V_$SESSION`). 조회가 불안정하면 `sql_text` 오버로드(원 자연어 `select ai ... ` 문장)를 사용하라. 두 방식 중 실제 DB 에서 동작하는 쪽을 검증해 채택하고, 채택 근거를 README 에 남겨라.
  - 피드백은 `<프로필명>_FEEDBACK_VECINDEX` 벡터 인덱스에 저장되며 유사 질문 시 프롬프트에 자동 주입된다. 수정 API 는 없으므로 수정 = delete 후 add.
- **앱 자체 테이블에도 기록**(조회·수정·삭제·이력 조인용): `AI_FEEDBACK_LOG(id, log_id(→AI_QUERY_LOG), profile_name, conversation_id, question, generated_sql, sql_id, feedback_type, feedback_content, corrected_sql, created_at, updated_at)`. Oracle FEEDBACK 호출과 자체 테이블 기록은 하나의 서비스 함수·트랜잭션으로 묶고, Oracle 호출 실패 시 자체 기록도 롤백하고 오류를 화면에 보여라.
- 환경 탭 상단 배지에 `피드백 N건` 배지를 추가하고, 프로필 카드에 `_FEEDBACK_VECINDEX` 존재 여부를 표시하라.

### 1-C. 질의 이력 탭 (NL2SQL 페이지 4번째 탭 "이력")
- 모든 Select AI 호출을 `AI_QUERY_LOG(id, started_at, profile_name, action, question, generated_sql, status(SUCCEEDED/FAILED), error_msg, elapsed_ms, conversation_id, row_count, model, created_by)` 에 기록(서비스 계층에서 공통 처리).
- 표: 시작시각 · 프로필 · 액션 · 질문 · 상태 · 소요(ms) · 피드백(👍/👎/—) · conversation_id(축약, 클릭 복사). 기본 최신순, 페이징(20건).
- 필터: 질문 텍스트 LIKE(대소문자 무시), 시작일시~종료일시, 프로필, 액션, 상태, 피드백 유무. "조회" 버튼.
- 행 클릭 → 모달: 질문, 생성 SQL(코드 블록), 답변 요약, **피드백 편집(좋음/나쁨·사유·올바른 SQL·삭제/닫기/저장)** — 1-B 와 같은 서비스 함수 재사용.
- 상단 요약 카드: 총 질의 수, 성공률, 평균/최대 소요, 피드백 비율. (간단 수치만, 차트는 선택)

### 1-D. 저장 질문 프리셋
- 예시 질문 드롭다운을 **DB 저장 프리셋**으로 확장: `AI_PROMPT_PRESET(id, profile_name, title, question, action, sort_order, created_at)`. 입력창 옆 "저장할 제목" + 추가/수정/삭제. 기존 하드코딩 예시는 초기 시드로 이관.

---

## Phase 2 — 정확도 개선 시연 도구

### 2-A. Few-shot 일괄 등록 (신규 탭 "피드백·Few-shot" 또는 이력 탭 하위)
- 고객(크라운제과)이 작성한 few-shot 파일(질문, SQL, 선택적 설명)을 CSV/JSON/XLSX 로 업로드 → 미리보기 표 → 검증(각 SQL 을 `EXPLAIN PLAN` 또는 `DBMS_SQL.PARSE` 로 문법 검증, 실패 행 표시) → **positive feedback 으로 일괄 등록**(`DBMS_CLOUD_AI.FEEDBACK(feedback_type=>'positive', response=>:sql, feedback_content=>:note)` 반복). 진행률·성공/실패 건수 표시, 실패 행만 재시도.
- 등록된 피드백 목록(유형·질문·사유·등록일)과 개별 삭제, 프로필별 전체 삭제(확인 모달).
- 템플릿 CSV 다운로드 버튼.

### 2-B. "정확도 개선 시나리오" 버튼 (질문 탭)
- 같은 질문을 3단계로 순차 실행해 나란히 비교: ① Annotation 제거 상태 → ② Annotation 적용 → ③ 피드백(few-shot) 반영. 각 단계의 생성 SQL·결과 요약·elapsed 를 3열 카드로 표시.
- 기존 Annotation 탭의 적용/제거 기능을 재사용하되, 시나리오 종료 후 원래 상태로 복원한다(실패 시에도 복원).
- 프로필 속성 `annotations`/`comments` 토글을 `DBMS_CLOUD_AI.SET_ATTRIBUTE` 로 잠시 바꾸는 방식이 더 안전하면 그 방식을 쓰고, 어떤 방식을 택했는지 화면 하단에 설명 문구로 표시.

### 2-C. showprompt 강조
- 피드백 등록 전/후 `showprompt` 결과를 비교해 "유사 피드백 예시가 프롬프트에 주입됨"을 하이라이트(diff 표시). 피드백 기능의 동작 원리를 보여주는 데 사용.

---

## Phase 3 — 운영 전환 대비

### 3-A. OCI Generative AI 프로바이더 지원
- 환경 탭 진단이 provider=`oci` 프로필도 올바르게 해석하도록 확장: 엔드포인트 호스트 `inference.generativeai.<region>.oci.oraclecloud.com`, 프로필 속성 `region`, `oci_compartment_id`, `oci_apiformat`(COHERE/GENERIC), `oci_endpoint_id`(전용 클러스터) 표시. 크리덴셜 카드는 OCI API Key 방식(user_ocid/tenancy_ocid/fingerprint) 또는 Resource Principal 을 구분해 표시.
- 프로필 생성 도우미: "새 프로필 만들기" 모달에 provider 선택(openai/oci/azure/cohere/google/anthropic 등), 모델, 크리덴셜, object_list 를 입력받아 `DBMS_CLOUD_AI.CREATE_PROFILE` JSON 을 미리보기하고 실행. OCI 인 경우 region 필수, 한국 리전에는 GenAI 가 없으므로 `ap-osaka-1`(오사카) 등 GenAI 제공 리전만 선택지에 노출하고 안내 문구를 붙인다.
- 실제 호출 테스트는 프로바이더에 관계없이 동작해야 한다.

### 3-B. 크라운제과형 샘플 데이터셋 + 프로필
- 코드가 아니라 **SQL 스크립트**(`db/seed/crown_like/`)로 제공: 매장(STORES), 제품(PRODUCTS), 진열현황(DISPLAYS: 진열위치·면수·전시상태[단독/혼합/미입력]·전시위치[전면중앙/…]), 매출(SALES: 일자·매장·제품·금액·수량) 4~5개 테이블 + 합성 데이터 생성 스크립트(수만 행) + 각 테이블/컬럼 **Annotation 및 COMMENT**(한국어) + 프로필 `CROWN_LIKE_PROFILE` 생성 스크립트 + 예시 질문 프리셋 시드("면수별 전시상태별 매출 금액은?", "전시위치별 매출 상위 10개" 등).
- 데이터 품질 시연을 위해 진열위치 "미입력" 비율을 30% 정도로 넣고, 예시 질문에 "미입력 제외" 변형을 포함.
- 프로필 선택 드롭다운에서 전환하면 Annotation 탭·질문 탭·이력 탭이 모두 해당 프로필 기준으로 동작해야 한다(이미 그렇다면 확인만).

### 3-C. 속도 계측·모델 비교
- 이력 탭 요약에 프로필(모델)별 평균 elapsed 비교 표.
- 질문 탭에 "모델 비교 실행" 옵션: 같은 질문을 선택한 2~3개 프로필로 순차 실행해 SQL·결과·elapsed 나란히 표시.

---

## Phase 4 — Select AI Agent (별도 상단 네비 `Select AI Agent`)

- 26ai `DBMS_CLOUD_AI_AGENT` 패키지 사용: `CREATE_TOOL`(SQL 툴: 프로필 기반 NL2SQL), `CREATE_TASK`, `CREATE_AGENT`, `CREATE_TEAM`, `RUN_TEAM`. 정확한 시그니처와 히스토리 뷰(문서명 "DBMS_CLOUD_AI_AGENT History Views")는 DB 의 `ALL_ARGUMENTS`/`ALL_VIEWS` 로 검증 후 사용.
- 화면: ① **정의 탭** — Team/Agent/Task/Tool 목록과 JSON 정의 표시, 샘플 팀(`TEAM_DEMO_NL2SQL`) 생성 스크립트 버튼. ② **실행 탭** — Phase 1 의 대화 UI 를 재사용하되 "실행 설정"(Team 선택) 프리셋 추가/수정, `RUN_TEAM` 호출, 답변 아래 "Thinking" 접기(중간 추론·툴 호출·SQL), "단계별 시간(N단계·총 ms)·이 대화 누적" 접기(히스토리 뷰에서 task/step 단위 소요 조회). ③ **Agent History 탭** — 히스토리 뷰 기반 표(시작시각·Team·질문·상태·소요·피드백·conversation_id) + 필터 + 피드백 모달. 피드백은 Team 이 사용하는 NL2SQL 프로필에 대해 `DBMS_CLOUD_AI.FEEDBACK` 호출.
- Phase 1 의 로그/피드백 테이블을 공유하고, `source`(GENERATE/RUN_TEAM) 컬럼으로 구분.

---

## 공통 구현 원칙

1. **기존 스택·디자인 시스템·코딩 컨벤션을 그대로 따른다.** 새 탭/페이지는 기존 탭 컴포넌트·카드·배지·"조회 SQL" 펼침 패턴을 재사용한다. 프레젠테이션 모드와 ⌘K 검색에 새 화면을 등록한다.
2. **기존 기능을 깨지 않는다.** 7개 액션, 환경 진단, Annotation 적용/제거, 실제 호출 테스트는 회귀 확인 필수.
3. **DB 객체는 마이그레이션 스크립트로**: `db/migrations/NNN_*.sql`(테이블·시퀀스·인덱스·GRANT) + 롤백 스크립트. README 에 적용 순서와 필요한 GRANT 를 적는다. 접속정보·API 키는 기존 설정 방식만 사용, 하드코딩 금지.
4. **Oracle 패키지 시그니처는 추측하지 않는다.** `DBMS_CLOUD_AI`, `DBMS_CLOUD_AI_AGENT` 의 프로시저·파라미터·뷰 이름은 대상 DB 에서 `ALL_ARGUMENTS`, `ALL_VIEWS`, `ALL_TAB_COLUMNS` 로 확인한 뒤 사용하고, 확인 SQL 을 `docs/verified-signatures.md` 에 기록한다. 26ai 문서와 다르면 DB 실측을 우선한다.
5. **모든 Select AI 호출은 서비스 계층 한 곳을 거친다**(프로필 설정 → 실행 → 로그 기록 → 오류 변환). 화면 코드에서 SQL 을 직접 조립하지 않는다.
6. **오류는 사용자에게 보이게**: ORA 오류 번호·메시지·힌트(예: ACL 미설정, 크리덴셜 만료, FEEDBACK 권한 없음)를 말풍선/토스트로 표시하고, 환경 탭으로 가는 링크를 붙인다.
7. **작은 커밋 단위**로 진행하고, 각 커밋 전에 앱을 실제 실행해 화면을 확인한다(가능하면 스크린샷을 `docs/screens/` 에 저장). Phase 종료 시 변경 요약·새 DDL·GRANT·남은 이슈를 보고한다.
8. 불확실한 점은 추측으로 구현하지 말고 사용자에게 묻는다. 단, Phase 안에서 질문은 모아서 한 번에 한다.

---

## 완료 보고 형식 (각 Phase 종료 시)
- 추가/변경 기능 목록(화면 캡처 경로 포함)
- 변경 파일 목록, 새 마이그레이션 스크립트, 필요한 GRANT
- 실측으로 검증한 Oracle 시그니처/뷰 목록
- 회귀 확인 결과(기존 7개 액션, 환경 진단, Annotation 적용/제거)
- 남은 이슈·다음 Phase 에서 결정이 필요한 사항
