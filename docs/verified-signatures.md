# Oracle 패키지 시그니처 실측 기록 (Select AI · Agent)

> `docs/CROWN_POC_UPGRADE_PROMPT.md` 공통 원칙 4: **`DBMS_CLOUD_AI`·`DBMS_CLOUD_AI_AGENT` 의 프로시저·파라미터·뷰 이름은
> 대상 DB 에서 확인한 뒤 쓴다. 26ai 문서와 다르면 DB 실측을 우선한다.**
> 이 파일은 그 확인 SQL 과 결과의 정본이다. 결과란이 비어 있는 항목은 **아직 추측 상태**이며 코드에 쓰면 안 된다.
>
> 실행 방법(로컬, 프로젝트 루트): `./venv/bin/python scripts/verify_signatures.py` (Phase 1 에서 작성 예정) 또는 SQLcl 로 아래 SQL 을 그대로.
> 대상: `db26aidemo_medium` · ADMIN · Oracle 26ai 23.26.3.3.0 (SESSION_HANDOFF §3 기준)

---

## 1. `DBMS_CLOUD_AI` — 대화·피드백 관련 프로시저 유무

```sql
SELECT object_name, overload, COUNT(*) args
FROM   all_arguments
WHERE  package_name = 'DBMS_CLOUD_AI'
AND    object_name IN ('GENERATE','FEEDBACK','CREATE_CONVERSATION','DROP_CONVERSATION',
                       'SET_CONVERSATION_ID','CLEAR_CONVERSATION_ID','UPDATE_CONVERSATION','SET_ATTRIBUTE')
GROUP  BY object_name, overload
ORDER  BY 1, 2;
```

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

## 2. `GENERATE` · `FEEDBACK` · `CREATE_CONVERSATION` 파라미터

```sql
SELECT object_name, overload, position, argument_name, data_type, defaulted, in_out
FROM   all_arguments
WHERE  package_name = 'DBMS_CLOUD_AI'
AND    object_name IN ('GENERATE','FEEDBACK','CREATE_CONVERSATION','SET_ATTRIBUTE')
ORDER  BY object_name, overload, position;
```

문서 기억(검증 전 — 틀릴 수 있다):
- `GENERATE(prompt, profile_name, action, attributes, params)` — `params` JSON 에 `conversation_id` 를 넘긴다고 기억한다.
- `FEEDBACK(profile_name, sql_id | sql_text, feedback_type, response, feedback_content, operation)` — 두 오버로드.
- `CREATE_CONVERSATION(attributes) RETURN VARCHAR2` — conversation_id 를 돌려준다고 기억한다.
- 현재 `app/select_ai.py` 의 `submit_feedback()` 은 `prompt`/`feedback` 파라미터를 쓰는데 이는 **어느 문서에도 없는 이름**이다(죽은 코드).

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

## 3. 대화·피드백 관련 뷰

```sql
SELECT owner, view_name FROM all_views
WHERE  view_name LIKE '%CLOUD_AI%' OR view_name LIKE '%CONVERSATION%'
ORDER  BY 1, 2;
```

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

## 4. `V$MAPPED_SQL` 접근 (피드백 `sql_id` 조회용)

```sql
SELECT COUNT(*) FROM v$mapped_sql WHERE ROWNUM <= 1;
-- 실패(ORA-00942) 면:  GRANT READ ON SYS.V_$MAPPED_SQL TO admin;  GRANT READ ON SYS.V_$SESSION TO admin;
```

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

## 5. `DBMS_CLOUD_AI_AGENT` (Phase 4)

```sql
SELECT owner, object_name, object_type, status FROM all_objects
WHERE  object_name = 'DBMS_CLOUD_AI_AGENT';

SELECT object_name, overload, COUNT(*) args FROM all_arguments
WHERE  package_name = 'DBMS_CLOUD_AI_AGENT'
GROUP  BY object_name, overload ORDER BY 1, 2;

SELECT owner, view_name FROM all_views
WHERE  view_name LIKE '%AI_AGENT%' OR view_name LIKE '%AGENT%TEAM%' OR view_name LIKE '%AGENT%TASK%'
ORDER  BY 1, 2;
```

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

## 6. 피드백 벡터 인덱스 명명 규칙 (피드백 1건 add 뒤)

```sql
SELECT index_name, index_type, table_name FROM user_indexes
WHERE  index_name LIKE '%FEEDBACK%' ORDER BY 1;
```

| 실측일 | 결과 |
|---|---|
| — | (미실측) |

---

## 채택 기록

| 결정 | 근거(실측) | 날짜 |
|---|---|---|
| FEEDBACK 은 `sql_id` / `sql_text` 중 어느 오버로드를 쓰는가 | — | — |
| conversation_id 를 GENERATE 에 넘기는 방법 | — | — |
