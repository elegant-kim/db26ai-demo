import asyncio
import json
import logging
import re
import time

import oracledb

from app.config import settings
from app.select_ai import _lob_to_str

logger = logging.getLogger(__name__)


def _vec_to_str(vec: list) -> str:
    """Python list를 Oracle VECTOR 리터럴 문자열로 변환한다."""
    return "[" + ",".join(str(v) for v in vec) + "]"


# === Table Initialization ===

async def init_vector_tables(pool):
    """Vector Search 관련 테이블이 없으면 생성한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # documents 테이블
            await cursor.execute("""
                DECLARE
                    v_cnt NUMBER;
                BEGIN
                    SELECT COUNT(*) INTO v_cnt
                    FROM user_tables WHERE table_name = 'DOCUMENTS';
                    IF v_cnt = 0 THEN
                        EXECUTE IMMEDIATE '
                            CREATE TABLE documents (
                                doc_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                                filename    VARCHAR2(500),
                                upload_date TIMESTAMP DEFAULT SYSTIMESTAMP,
                                status      VARCHAR2(20) DEFAULT ''processing'',
                                chunks_count NUMBER DEFAULT 0
                            )
                        ';
                    END IF;
                END;
            """)

            # doc_chunks 테이블
            await cursor.execute("""
                DECLARE
                    v_cnt NUMBER;
                BEGIN
                    SELECT COUNT(*) INTO v_cnt
                    FROM user_tables WHERE table_name = 'DOC_CHUNKS';
                    IF v_cnt = 0 THEN
                        EXECUTE IMMEDIATE '
                            CREATE TABLE doc_chunks (
                                chunk_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                                doc_id      NUMBER NOT NULL,
                                chunk_text  CLOB,
                                source_file VARCHAR2(500),
                                page_num    NUMBER,
                                embedding   VECTOR
                            )
                        ';
                    END IF;
                END;
            """)

            # HNSW 벡터 인덱스 생성 시도
            await cursor.execute("""
                DECLARE
                    v_cnt NUMBER;
                BEGIN
                    SELECT COUNT(*) INTO v_cnt
                    FROM user_indexes WHERE index_name = 'DOC_CHUNKS_HNSW_IDX';
                    IF v_cnt = 0 THEN
                        BEGIN
                            EXECUTE IMMEDIATE '
                                CREATE VECTOR INDEX doc_chunks_hnsw_idx
                                ON doc_chunks(embedding)
                                ORGANIZATION INMEMORY NEIGHBOR GRAPH
                                DISTANCE COSINE
                                WITH TARGET ACCURACY 95
                            ';
                        EXCEPTION
                            WHEN OTHERS THEN
                                NULL;
                        END;
                    END IF;
                END;
            """)

            await conn.commit()


# === PDF Processing ===

def extract_text_from_pdf(file_path: str) -> list:
    """PDF 파일에서 페이지별 텍스트를 추출한다."""
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page_num": i + 1, "text": text})
        return pages
    except ImportError:
        # pdfplumber가 없으면 기본 텍스트 반환
        return [{"page_num": 1, "text": "PDF 텍스트 추출 라이브러리(pdfplumber)가 설치되지 않았습니다."}]


def chunk_text_python(text: str, max_chunk_size: int = 500, overlap: int = 50) -> list:
    """Python 기반 텍스트 청킹 (DB DBMS_VECTOR_CHAIN 대체)."""
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        # 문장 경계에서 분할 시도
        if end < len(text):
            for sep in ['. ', '.\n', '\n\n', '\n', ' ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep > max_chunk_size // 2:
                    end = start + last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


async def try_db_chunking(pool, text: str) -> list:
    """DB의 DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS로 청킹을 시도한다."""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS(
                        :text_content,
                        JSON('{"max_chunk_size": 500, "overlap": 50}')
                    ) FROM dual
                """, {"text_content": text})
                row = await cursor.fetchone()
                if row:
                    result = await _lob_to_str(row[0])
                    if isinstance(result, str):
                        parsed = json.loads(result)
                        return [item.get("chunk_text", item) for item in parsed]
        return None
    except Exception:
        return None


async def get_embedding_from_db(pool, text: str, model_name: str) -> list:
    """DB 내 ONNX 모델을 사용하여 임베딩을 생성한다."""
    # VECTOR_EMBEDDING의 모델명은 SQL identifier이므로 bind variable이 아닌 리터럴로 삽입
    safe_model = model_name.replace("'", "").replace('"', '').replace(';', '')
    sql = f"""
        SELECT VECTOR_EMBEDDING({safe_model} USING :text_data AS data)
        FROM dual
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(sql, {"text_data": text})
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None


async def get_embedding_external(text: str) -> list:
    """외부 API를 사용하여 임베딩을 생성한다."""
    import urllib.error
    import urllib.request

    api_url = settings.EMBEDDING_API_URL
    api_key = settings.EMBEDDING_API_KEY
    model = settings.EMBEDDING_MODEL

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "input": text,
        "model": model,
        "dimensions": settings.EMBEDDING_DIM,
    }
    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"][0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"외부 임베딩 API 호출 실패: {e}") from e


async def get_embedding(pool, text: str) -> list:
    """설정에 따라 DB 내부 또는 외부 API로 임베딩을 생성한다."""
    if settings.EMBEDDING_SOURCE == "database":
        return await get_embedding_from_db(pool, text, settings.EMBEDDING_MODEL)
    else:
        return await get_embedding_external(text)


# === Oracle Text 질의 변환 ===

# Oracle Text 예약 연산자. 자연어 문장을 그대로 CONTAINS 에 넣으면 '?' 등이
# 연산자로 해석되어 ORA-29902 로 터진다(2026-09-04 실측).
_CTX_RESERVED = re.compile(r'[,&|~;><%_$!{}()\[\]*?"\\+=:@#^\'`/\-]')

# 질문 어투 등 검색에 기여하지 않는 어절
_CTX_STOPWORDS = {
    "어떻게", "무엇", "무엇을", "왜", "어디", "언제", "하나요", "되나요", "합니까",
    "인가요", "입니까", "그리고", "그러나", "또는", "대해", "대한", "위해", "위한",
    "이란", "라는", "있나요", "알려줘", "알려주세요", "설명해줘",
}

# 의문사로 시작하는 어절은 활용형이 무한하다("무엇인가요"·"어떤가요"·"어떻습니까"…).
# 목록으로는 다 못 막아서 접두사로 거른다.
_CTX_INTERROGATIVE = ("무엇", "무슨", "어떻", "어떤", "어느", "얼마", "언제", "어디", "누가", "누구", "왜")

# 한글 조사·흔한 용언 어미 (긴 것부터). WORLD_LEXER 는 어절을 통째로 토큰화하므로
# "인덱스"(11건)와 "인덱스를"(2건)이 서로 다른 토큰이 된다 → 어간만 남기고 우측 절단한다.
_CTX_SUFFIXES = [
    "하려면", "으로써", "으로서", "에서는", "에게서", "적으로", "해야", "하는", "하고",
    "되는", "려면", "으로", "에서", "에게", "한테", "부터", "까지", "처럼", "보다",
    "라도", "이나", "을", "를", "이", "가", "은", "는", "에", "의", "와", "과",
    "도", "만", "로", "야", "여", "적",
]

_HANGUL = re.compile(r'[가-힣]')


def _ctx_stem(token: str) -> str:
    """어절에서 한글 조사·어미를 떼어 어간을 남긴다."""
    m = re.match(r'^([A-Za-z0-9._]+)[가-힣]+$', token)   # "SQL을" → "SQL"
    if m:
        return m.group(1)
    if not _HANGUL.search(token):
        return token
    for suf in _CTX_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 2:
            return token[: len(token) - len(suf)]
    return token


def to_contains_query(query: str) -> str | None:
    """자연어 질의를 Oracle Text CONTAINS 구문(ACCUM)으로 변환한다.

    2026-09-04 신설. 그전에는 사용자 문장을 CONTAINS 에 그대로 넣어,
    "인덱스를 효율적으로 사용하려면 … 하나요?" 같은 자연어 질문이 ORA-29902 로
    터지고 LIKE 로 폴백되어 **하이브리드가 조용히 벡터 전용으로 퇴화**했다.
    화면에서 실제로 질문해 보고서야 드러난 결함이다.

    변환 예: "인덱스를 효율적으로 사용하려면 어떻게 SQL을 작성해야 하나요?"
          → "인덱스%, 효율적%, 사용%, SQL, 작성%"   (쉼표 = ACCUM, 누적 점수)

    쉼표(ACCUM)를 쓰는 이유: AND 로 묶으면 한 단어만 없어도 0건이 된다. 하이브리드의
    키워드 성분은 필터가 아니라 **점수**여야 하므로 누적 점수가 맞다.
    반환값이 None 이면 쓸 만한 토큰이 없다는 뜻이니 호출부는 LIKE 로 폴백한다.
    """
    if not query:
        return None
    tokens = [t for t in _CTX_RESERVED.sub(' ', query).split()
              if len(t) >= 2
              and t not in _CTX_STOPWORDS
              and not t.startswith(_CTX_INTERROGATIVE)]
    terms, seen = [], set()
    for tok in tokens:
        stem = _ctx_stem(tok)
        # 어간으로 줄인 뒤에도 불용어일 수 있다 ("하나요" → "하나")
        if len(stem) < 2 or stem in seen or stem in _CTX_STOPWORDS:
            continue
        seen.add(stem)
        # 한글 어간은 우측 절단으로 남은 활용형을 흡수한다. 영문·숫자는 그대로.
        terms.append(stem + "%" if _HANGUL.search(stem) else stem)
    return ", ".join(terms) if terms else None


async def warm_embedding_pool(pool) -> dict:
    """풀의 모든 커넥션에 ONNX 임베딩 모델을 미리 로드한다(커넥션 풀 워밍).

    배경(2026-09-04 실측): DB 내장 ONNX 임베딩은 **커넥션마다** 모델을 최초 1회
    로드하며 그 비용이 크다 — MULTILINGUAL_E5_BASE 5.2초, E5_SMALL 1.1초.
    같은 커넥션의 두 번째 호출부터는 20~40ms 다. 풀이 min=1/max=5 라 데모 도중
    새 커넥션이 배정될 때마다 5초짜리 멈춤이 산발적으로 나타났다.

    커넥션을 **동시에** 잡아야 각각이 예열된다. 순차로 acquire/release 하면 같은
    커넥션이 재사용되어 하나만 달궈진다.

    외부 API 임베딩 모드에서는 할 일이 없으므로 건너뛴다.
    """
    if settings.EMBEDDING_SOURCE != "database":
        return {"warmed": 0, "skipped": "외부 API 임베딩 모드 — 워밍 불필요"}

    safe_model = settings.EMBEDDING_MODEL.replace("'", "").replace('"', '').replace(';', '')
    sql = f"SELECT VECTOR_EMBEDDING({safe_model} USING :t AS data) FROM dual"
    target = getattr(pool, "max", 5) or 5

    conns, errors, warmed = [], [], 0
    started = time.time()
    try:
        for _ in range(target):
            try:
                conns.append(await pool.acquire())
            except Exception as e:
                errors.append(str(e).splitlines()[0][:120])
                break

        async def _warm(conn):
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"t": "warmup"})
                await cursor.fetchone()

        for r in await asyncio.gather(*(_warm(c) for c in conns), return_exceptions=True):
            if isinstance(r, BaseException):
                errors.append(str(r).splitlines()[0][:120])
            else:
                warmed += 1
    finally:
        for c in conns:
            try:
                await pool.release(c)
            except Exception:
                pass

    result = {
        "warmed": warmed,
        "target": target,
        "model": settings.EMBEDDING_MODEL,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
    if errors:
        result["errors"] = errors[:3]
        logger.warning("[warmup] 커넥션 %d/%d 예열 실패: %s", target - warmed, target, errors[0])
    return result


# === Document Upload Pipeline ===

async def upload_document(pool, file_path: str, filename: str, progress_callback=None) -> dict:
    """PDF 파일을 처리하여 청킹 -> 임베딩 -> DB 저장 파이프라인을 실행한다.

    progress_callback이 주어지면 각 단계마다 호출하여 실시간 진행 상황을 전달한다.
    callback(event_type, data_dict) 형태.
    """
    pipeline = []
    start_total = time.time()

    async def emit(event, data):
        if progress_callback:
            await progress_callback(event, data)

    # Step 1: 문서 레코드 생성
    await emit("step", {"step": 1, "label": "문서 등록", "status": "running"})
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            doc_id_var = cursor.var(int)
            await cursor.execute("""
                INSERT INTO documents (filename, status)
                VALUES (:filename, 'processing')
                RETURNING doc_id INTO :doc_id
            """, {"filename": filename, "doc_id": doc_id_var})
            doc_id = doc_id_var.getvalue()[0]
            await conn.commit()
    await emit("step", {"step": 1, "label": "문서 등록", "status": "done",
                         "detail": f"doc_id={doc_id}",
                         "duration_ms": int((time.time() - start_total) * 1000)})

    try:
        # Step 2: PDF 텍스트 추출
        step_start = time.time()
        await emit("step", {"step": 2, "label": "텍스트 추출", "status": "running"})
        # pdfplumber 는 동기 코드다 — 2026-09-05 실측: 195쪽 PDF 추출 84초 동안 이벤트 루프가 통째로 막혀
        # SSE 는 "1단계 진행 중"에 멈춰 보였고 /api/health 도 응답하지 않았다. 스레드로 보낸다.
        pages = await asyncio.to_thread(extract_text_from_pdf, file_path)
        step_ms = int((time.time() - step_start) * 1000)
        pipeline.append({"step": "텍스트 추출", "sql": "-- pdfplumber PDF 텍스트 추출", "duration_ms": step_ms})

        if not pages:
            raise ValueError("PDF에서 텍스트를 추출할 수 없습니다.")

        total_chars = sum(len(p["text"]) for p in pages)
        await emit("step", {"step": 2, "label": "텍스트 추출", "status": "done",
                             "detail": f"{len(pages)}페이지 / {total_chars:,}자",
                             "duration_ms": step_ms})

        # Step 3: 청킹
        step_start = time.time()
        await emit("step", {"step": 3, "label": "청크 분할", "status": "running"})
        all_chunks = []
        for page in pages:
            db_chunks = await try_db_chunking(pool, page["text"])
            if db_chunks:
                for chunk in db_chunks:
                    all_chunks.append({"text": chunk, "page_num": page["page_num"]})
            else:
                py_chunks = chunk_text_python(page["text"])
                for chunk in py_chunks:
                    all_chunks.append({"text": chunk, "page_num": page["page_num"]})

        step_ms = int((time.time() - step_start) * 1000)
        chunking_sql = "SELECT DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS(:text, JSON('{\"max_chunk_size\": 500, \"overlap\": 50}')) FROM dual"
        pipeline.append({"step": "청크 분할", "sql": chunking_sql, "duration_ms": step_ms})
        await emit("step", {"step": 3, "label": "청크 분할", "status": "done",
                             "detail": f"{len(all_chunks)}개 청크 생성",
                             "duration_ms": step_ms})

        # Step 4: 임베딩 생성 + DB 저장  (가장 오래 걸림 — 청크별 진행률 전달)
        step_start_embed = time.time()
        total_chunks = len(all_chunks)
        # embed_count = 임베딩이 실제로 저장된 청크 수. 2026-09-04 이전에는 실패해도
        # 무조건 +1 해서, 임베딩이 전부 NULL 인데도 "79개 완료"로 보고했다
        # (원인은 ORA-51932 — HNSW 인덱스 차원 불일치였는데 except 가 삼켰다).
        embed_count = 0
        no_embed_count = 0
        first_embed_error = None
        await emit("step", {"step": 4, "label": "임베딩 & 저장", "status": "running",
                             "detail": f"0/{total_chunks}", "progress": 0})

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for idx, chunk_info in enumerate(all_chunks):
                    stored_with_embedding = False
                    try:
                        embedding = await get_embedding(pool, chunk_info["text"])
                        if embedding is not None:
                            await cursor.execute("""
                                INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num, embedding)
                                VALUES (:doc_id, :chunk_text, :source_file, :page_num, TO_VECTOR(:embedding))
                            """, {
                                "doc_id": doc_id,
                                "chunk_text": chunk_info["text"],
                                "source_file": filename,
                                "page_num": chunk_info["page_num"],
                                "embedding": _vec_to_str(embedding),
                            })
                            stored_with_embedding = True
                        else:
                            if first_embed_error is None:
                                first_embed_error = "임베딩 생성이 None을 반환했습니다."
                                logger.warning("[upload] %s", first_embed_error)
                            await cursor.execute("""
                                INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num)
                                VALUES (:doc_id, :chunk_text, :source_file, :page_num)
                            """, {
                                "doc_id": doc_id,
                                "chunk_text": chunk_info["text"],
                                "source_file": filename,
                                "page_num": chunk_info["page_num"],
                            })
                    except Exception as e:
                        # 임베딩 없이라도 본문은 남긴다(키워드 검색은 가능). 다만
                        # 실패를 조용히 넘기지 않는다 — 첫 예외를 로그와 응답에 싣는다.
                        if first_embed_error is None:
                            first_embed_error = str(e).splitlines()[0][:200]
                            logger.warning("[upload] 임베딩 저장 실패(이후 동일 오류는 생략): %s",
                                           first_embed_error)
                        await cursor.execute("""
                            INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num)
                            VALUES (:doc_id, :chunk_text, :source_file, :page_num)
                        """, {
                            "doc_id": doc_id,
                            "chunk_text": chunk_info["text"],
                            "source_file": filename,
                            "page_num": chunk_info["page_num"],
                        })
                    if stored_with_embedding:
                        embed_count += 1
                    else:
                        no_embed_count += 1
                    # 매 청크마다 또는 적절한 간격으로 진행률 전달
                    if total_chunks <= 20 or (idx + 1) % max(1, total_chunks // 20) == 0 or idx == total_chunks - 1:
                        pct = int((idx + 1) / total_chunks * 100)
                        await emit("progress", {
                            "step": 4, "current": idx + 1, "total": total_chunks, "percent": pct,
                        })

                await conn.commit()

        step_ms_embed = int((time.time() - step_start_embed) * 1000)
        if settings.EMBEDDING_SOURCE == "database":
            embed_sql = f"SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING :text AS data) FROM dual"
        else:
            embed_sql = f"-- 외부 API ({settings.EMBEDDING_MODEL}) 사용"
        pipeline.append({"step": "임베딩 & 저장", "sql": embed_sql, "duration_ms": step_ms_embed})
        embed_detail = f"{embed_count}개 완료"
        if no_embed_count:
            embed_detail += f" / 임베딩 실패 {no_embed_count}개 — {first_embed_error}"
        await emit("step", {"step": 4, "label": "임베딩 & 저장", "status": "done",
                             "detail": embed_detail,
                             "embedded": embed_count, "not_embedded": no_embed_count,
                             "error": first_embed_error,
                             "duration_ms": step_ms_embed})

        # Step 5: 인덱싱 완료
        step_start_idx = time.time()
        await emit("step", {"step": 5, "label": "인덱싱 완료", "status": "running"})
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE documents
                    SET status = 'indexed', chunks_count = :cnt
                    WHERE doc_id = :doc_id
                """, {"cnt": embed_count + no_embed_count, "doc_id": doc_id})
                await conn.commit()

        step_ms_idx = int((time.time() - step_start_idx) * 1000)
        pipeline.append({"step": "인덱싱 완료", "duration_ms": step_ms_idx})

        total_ms = int((time.time() - start_total) * 1000)
        result = {
            "success": True,
            "filename": filename,
            "doc_id": doc_id,
            "chunks_count": embed_count + no_embed_count,
            "embedded_count": embed_count,
            "not_embedded_count": no_embed_count,
            "pages_count": len(pages),
            "pipeline": pipeline,
            "total_ms": total_ms,
        }
        if no_embed_count:
            result["warning"] = (
                f"{no_embed_count}개 청크가 임베딩 없이 저장되어 의미 검색에서 제외됩니다. "
                f"첫 오류: {first_embed_error}"
            )
        await emit("done", result)
        return result

    except Exception as e:
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE documents SET status = 'error' WHERE doc_id = :doc_id
                    """, {"doc_id": doc_id})
                    await conn.commit()
        except Exception:
            pass
        await emit("error", {"message": str(e)})
        raise e


# === Search Functions ===

async def vector_search(pool, query: str, top_k: int = 5) -> dict:
    """벡터 유사도 검색을 수행한다."""
    start = time.time()

    if settings.EMBEDDING_SOURCE == "database":
        # DB 내 임베딩 모델 사용.
        # VECTOR_EMBEDDING 은 반드시 스칼라 서브쿼리 (SELECT ... FROM dual) 로 감싼다.
        # 인라인으로 두면 행마다 재평가되어 79청크에 5.4초가 걸렸다(2026-09-04 실측).
        # 감싸면 Oracle 이 1회만 평가한다 → 0.05초. hybrid_search 와 동일한 이유.
        sql = f"""
            SELECT chunk_id, chunk_text, source_file, page_num,
                   VECTOR_DISTANCE(embedding,
                       (SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING :query AS data)
                        FROM dual),
                       COSINE) AS distance
            FROM doc_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""SELECT chunk_id, chunk_text, source_file, page_num,
       VECTOR_DISTANCE(embedding,
           (SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING '{query}' AS data)
            FROM dual),
           COSINE) AS distance
FROM doc_chunks
WHERE embedding IS NOT NULL
ORDER BY distance
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"query": query, "top_k": top_k})
                rows = await cursor.fetchall()
    else:
        # 외부 임베딩 사용
        query_vector = await get_embedding_external(query)
        query_vec_str = _vec_to_str(query_vector)
        sql = """
            SELECT chunk_id, chunk_text, source_file, page_num,
                   VECTOR_DISTANCE(embedding, TO_VECTOR(:query_vector), COSINE) AS distance
            FROM doc_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""-- 외부 임베딩 API ({settings.EMBEDDING_MODEL}) 사용
SELECT chunk_id, chunk_text, source_file, page_num,
       VECTOR_DISTANCE(embedding, TO_VECTOR('<{len(query_vector)}차원 벡터>'), COSINE) AS distance
FROM doc_chunks
WHERE embedding IS NOT NULL
ORDER BY distance
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"query_vector": query_vec_str, "top_k": top_k})
                rows = await cursor.fetchall()

    chunks = []
    for row in rows:
        chunk_text = await _lob_to_str(row[1]) if hasattr(row[1], 'read') else row[1]
        similarity = 1 - (row[4] if row[4] else 0)  # cosine distance -> similarity
        chunks.append({
            "chunk_id": row[0],
            "chunk_text": chunk_text,
            "source_file": row[2],
            "page_num": row[3],
            "similarity": round(similarity, 4),
        })

    elapsed = int((time.time() - start) * 1000)

    return {
        "chunks": chunks,
        "match_count": len(chunks),
        "sql_executed": sql_executed,
        "elapsed_ms": elapsed,
    }


async def keyword_search(pool, query: str, top_k: int = 5) -> dict:
    """전통적 키워드 검색을 수행한다."""
    start = time.time()

    # CONTAINS 사용 시도, 실패하면 LIKE로 대체
    keyword = f"%{query}%"
    # 자연어 문장을 그대로 넣으면 ORA-29902 로 터진다 → ACCUM 구문으로 변환
    ctx_query = to_contains_query(query)

    try:
        if ctx_query is None:
            raise ValueError("CONTAINS 로 변환할 토큰이 없습니다.")
        # Oracle Text CONTAINS 시도
        sql_contains = """
            SELECT chunk_text, source_file, page_num, SCORE(1) AS relevance
            FROM doc_chunks
            WHERE CONTAINS(chunk_text, :query, 1) > 0
            ORDER BY relevance DESC
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""-- 질의 변환(ACCUM): '{query}'
--            → '{ctx_query}'
SELECT chunk_text, source_file, page_num, SCORE(1) AS relevance
FROM doc_chunks
WHERE CONTAINS(chunk_text, '{ctx_query}', 1) > 0
ORDER BY relevance DESC
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_contains, {"query": ctx_query, "top_k": top_k})
                rows = await cursor.fetchall()

    except Exception as e:
        logger.warning("[keyword] CONTAINS 실패 → LIKE 폴백: %s", str(e).splitlines()[0][:150])
        # CONTAINS 실패 시 LIKE로 대체
        sql_like = """
            SELECT chunk_text, source_file, page_num, 0 AS relevance
            FROM doc_chunks
            WHERE LOWER(chunk_text) LIKE LOWER(:keyword)
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""SELECT chunk_text, source_file, page_num
FROM doc_chunks
WHERE LOWER(chunk_text) LIKE LOWER('%{query}%')
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_like, {"keyword": keyword, "top_k": top_k})
                rows = await cursor.fetchall()

    chunks = []
    for row in rows:
        chunk_text = await _lob_to_str(row[0]) if hasattr(row[0], 'read') else row[0]
        chunks.append({
            "chunk_text": chunk_text,
            "source_file": row[1],
            "page_num": row[2],
            "similarity": None,
        })

    elapsed = int((time.time() - start) * 1000)

    return {
        "chunks": chunks,
        "match_count": len(chunks),
        "sql_executed": sql_executed,
        "elapsed_ms": elapsed,
    }


async def compare_search(pool, query: str, top_k: int = 5) -> dict:
    """키워드 검색과 벡터 검색을 동시에 수행하여 비교한다."""
    keyword_results = await keyword_search(pool, query, top_k)
    vector_results = await vector_search(pool, query, top_k)

    return {
        "keyword_results": keyword_results,
        "vector_results": vector_results,
    }


async def hybrid_search(pool, query: str, top_k: int = 5, vector_weight: float = 0.7) -> dict:
    """하이브리드 검색: 키워드 점수 + 벡터 유사도를 단일 SQL에서 결합한다 (Oracle 26ai).

    hybrid_score = vector_weight × vector_similarity + (1 - vector_weight) × keyword_score/100

    키워드 점수는 Oracle Text 의 CONTAINS/SCORE 를 우선 사용하고, Text 인덱스가 없거나
    질의 구문이 맞지 않으면 LIKE 로 폴백한다(2026-09-04 신설 — 그전에는 CONTAINS 를
    아예 시도하지 않고 LIKE 만 썼다. CLAUDE.md 기술과 코드가 갈라져 있었다).

    SCORE(n) 은 같은 문장의 WHERE 에 CONTAINS(..., n) 이 있어야 쓸 수 있는데, WHERE 에
    두면 키워드 미매칭 청크가 걸러져 "벡터 후보 전체를 키워드로 가점"이라는 하이브리드
    의미가 깨진다. 그래서 CONTAINS 는 LEFT JOIN 서브쿼리로 분리하고 NVL 로 0 을 채운다.
    """
    start = time.time()
    keyword_weight = round(1 - vector_weight, 2)
    # 자연어 문장을 그대로 CONTAINS 에 넣으면 ORA-29902 → ACCUM 구문으로 변환.
    # None 이면 쓸 만한 토큰이 없다는 뜻이니 곧바로 LIKE 로 간다.
    ctx_query = to_contains_query(query)

    # ── 임베딩 소스별 "질의 벡터" 표현식과 바인드 준비 ──
    if settings.EMBEDDING_SOURCE == "database":
        # VECTOR_EMBEDDING 을 스칼라 서브쿼리로 감싸는 것이 핵심이다(2026-09-04 실측).
        # 인라인으로 두면 하이브리드의 복합 ORDER BY 때문에 행마다 재평가되어
        # 79청크에 11.3초가 걸렸다. (SELECT ... FROM dual) 로 감싸면 Oracle 이
        # 스칼라 서브쿼리 캐싱으로 1회만 평가한다 → 0.11초. 약 100배.
        qvec_sql = f"(SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING :qtext AS data) FROM dual)"
        qvec_display = f"(SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING '{query}' AS data) FROM dual)"
        qvec_binds = {"qtext": query}
    else:
        query_vector = await get_embedding_external(query)
        qvec_sql = "TO_VECTOR(:qvec)"
        qvec_display = "TO_VECTOR(<query_vector>)"
        qvec_binds = {"qvec": _vec_to_str(query_vector)}

    def build(keyword_mode: str):
        """keyword_mode: 'contains' | 'like' → (sql, binds, display)"""
        if keyword_mode == "contains":
            kw_join = (
                "LEFT JOIN (SELECT chunk_id, SCORE(1) AS kw_score FROM doc_chunks\n"
                "           WHERE CONTAINS(chunk_text, :kw, 1) > 0) k ON k.chunk_id = c.chunk_id"
            )
            kw_expr = "NVL(k.kw_score, 0)"
            kw_binds = {"kw": ctx_query}
            note = (f"-- 키워드: Oracle Text CONTAINS + SCORE (doc_chunks_text_idx)\n"
                    f"-- 질의 변환(ACCUM): '{query}' → '{ctx_query}'")
        else:
            kw_join = ""
            kw_expr = "CASE WHEN LOWER(c.chunk_text) LIKE LOWER(:kw) THEN 100 ELSE 0 END"
            kw_binds = {"kw": f"%{query}%"}
            note = "-- 키워드: LIKE 폴백 (Oracle Text 인덱스 없음/질의 부적합)"

        sql = f"""
            SELECT c.chunk_id, c.chunk_text, c.source_file, c.page_num,
                   VECTOR_DISTANCE(c.embedding, {qvec_sql}, COSINE) AS vec_distance,
                   {kw_expr} AS keyword_score
            FROM doc_chunks c
            {kw_join}
            WHERE c.embedding IS NOT NULL
            ORDER BY ({vector_weight} * (1 - VECTOR_DISTANCE(c.embedding, {qvec_sql}, COSINE))
                    + {keyword_weight} * {kw_expr} / 100) DESC
            FETCH FIRST :top_k ROWS ONLY
        """
        binds = {**qvec_binds, **kw_binds, "top_k": top_k}
        display = f"""-- 하이브리드 검색 (Oracle 26ai): 단일 SQL 에서 키워드 + 벡터 결합
-- hybrid_score = {vector_weight} × vector_similarity + {keyword_weight} × keyword_score/100
{note}
SELECT c.chunk_id, c.chunk_text, c.source_file, c.page_num,
       VECTOR_DISTANCE(c.embedding, {qvec_display}, COSINE) AS vec_distance,
       {kw_expr.replace(':kw', repr(query))} AS keyword_score
FROM doc_chunks c
{kw_join.replace(':kw', repr(query))}
WHERE c.embedding IS NOT NULL
ORDER BY ({vector_weight} * (1 - vec_distance) + {keyword_weight} * keyword_score/100) DESC
FETCH FIRST {top_k} ROWS ONLY"""
        return sql, binds, display

    async def run(sql, binds):
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, binds)
                return await cursor.fetchall()

    keyword_mode = "contains" if ctx_query else "like"
    sql, binds, sql_display = build(keyword_mode)
    try:
        rows = await run(sql, binds)
    except Exception as e:
        if keyword_mode == "like":
            raise
        logger.warning("[hybrid] CONTAINS 실패 → LIKE 폴백: %s", str(e).splitlines()[0][:160])
        keyword_mode = "like"
        sql, binds, sql_display = build(keyword_mode)
        rows = await run(sql, binds)

    chunks = []
    for row in rows:
        chunk_text = await _lob_to_str(row[1]) if hasattr(row[1], 'read') else row[1]
        vec_distance = row[4] if row[4] else 0
        keyword_score_raw = row[5] if row[5] else 0
        vec_similarity = 1 - vec_distance
        hybrid_score = vector_weight * vec_similarity + keyword_weight * (keyword_score_raw / 100)
        chunks.append({
            "chunk_id": row[0],
            "chunk_text": chunk_text,
            "source_file": row[2],
            "page_num": row[3],
            "similarity": round(vec_similarity, 4),
            "keyword_score": round(keyword_score_raw, 1),
            "hybrid_score": round(hybrid_score, 4),
        })

    return {
        "chunks": chunks,
        "match_count": len(chunks),
        "sql_executed": sql_display,
        "elapsed_ms": int((time.time() - start) * 1000),
        "vector_weight": vector_weight,
        "keyword_weight": keyword_weight,
        "keyword_mode": keyword_mode,
    }


# === RAG Answer Generation ===

async def generate_rag_answer(query: str, chunks: list, provider: str = None) -> str:
    """검색된 청크를 컨텍스트로 외부 LLM API를 통해 답변을 생성한다."""
    from app.llm_client import call_llm

    context = "\n\n".join([c["chunk_text"] for c in chunks if c.get("chunk_text")])

    system_prompt = (
        "당신은 문서 기반 질의응답 AI 어시스턴트입니다. "
        "제공된 참고 문서 내용만을 근거로 한국어로 답변하세요. "
        "문서에 없는 내용은 답변하지 마세요."
    )

    prompt = f"""다음 문서 내용을 참고하여 질문에 한국어로 답변하세요.

[참고 문서]
{context}

[질문]
{query}

반드시 참고 문서에 있는 내용만을 근거로 답변하세요."""

    try:
        return await call_llm(prompt, provider=provider, system_prompt=system_prompt)
    except Exception as e:
        return f"LLM 답변 생성 중 오류: {str(e)}"


# === Document Management ===

async def list_documents(pool) -> list:
    """업로드된 문서 목록을 조회한다. 각 문서의 임베딩 차원 수도 포함."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT d.doc_id, d.filename, d.upload_date, d.status, d.chunks_count,
                       (SELECT VECTOR_DIMENSION_COUNT(c.embedding)
                        FROM doc_chunks c
                        WHERE c.doc_id = d.doc_id AND c.embedding IS NOT NULL
                        AND ROWNUM = 1) AS embed_dim
                FROM documents d
                ORDER BY d.upload_date DESC
            """)
            rows = await cursor.fetchall()
            return [
                {
                    "doc_id": row[0],
                    "filename": row[1],
                    "upload_date": row[2].isoformat() if row[2] else None,
                    "status": row[3],
                    "chunks_count": row[4],
                    "embed_dim": row[5],
                }
                for row in rows
            ]


async def delete_document(pool, doc_id: int) -> bool:
    """문서 및 관련 청크를 삭제한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("DELETE FROM doc_chunks WHERE doc_id = :doc_id", {"doc_id": doc_id})
            await cursor.execute("DELETE FROM documents WHERE doc_id = :doc_id", {"doc_id": doc_id})
            await conn.commit()
            return True


async def get_index_info(pool) -> dict:
    """벡터 인덱스 메타데이터를 조회한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # 총 청크 수
            await cursor.execute("SELECT COUNT(*) FROM doc_chunks")
            total_chunks = (await cursor.fetchone())[0]

            # 임베딩이 있는 청크 수
            await cursor.execute("SELECT COUNT(*) FROM doc_chunks WHERE embedding IS NOT NULL")
            embedded_chunks = (await cursor.fetchone())[0]

            # 총 문서 수
            await cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = (await cursor.fetchone())[0]

            # 벡터 인덱스 정보
            index_info = None
            try:
                await cursor.execute("""
                    SELECT index_name, index_type, status
                    FROM user_indexes
                    WHERE table_name = 'DOC_CHUNKS'
                    AND index_type LIKE '%VECTOR%'
                """)
                idx_row = await cursor.fetchone()
                if idx_row:
                    index_info = {
                        "index_name": idx_row[0],
                        "index_type": idx_row[1],
                        "status": idx_row[2],
                    }
            except Exception:
                pass

            return {
                "total_chunks": total_chunks,
                "embedded_chunks": embedded_chunks,
                "total_documents": total_docs,
                "embedding_model": settings.EMBEDDING_MODEL,
                "embedding_source": settings.EMBEDDING_SOURCE,
                "vector_dimensions": 768,
                "distance_metric": "COSINE",
                "index": index_info,
            }


async def get_embedding_info(pool, text: str) -> dict:
    """텍스트의 임베딩 과정 정보를 반환한다."""
    start = time.time()

    result = {
        "input_text": text[:200] + ("..." if len(text) > 200 else ""),
        "model": settings.EMBEDDING_MODEL,
        "source": settings.EMBEDDING_SOURCE,
        "dimensions": 768,
    }

    try:
        embedding = await get_embedding(pool, text)
        elapsed = int((time.time() - start) * 1000)
        result["processing_ms"] = elapsed
        result["success"] = True
        if embedding:
            result["vector_preview"] = str(embedding[:5]) + "..." if len(embedding) > 5 else str(embedding)
            result["dimensions"] = len(embedding)
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        result["processing_ms"] = elapsed
        result["success"] = False
        result["error"] = str(e)

    return result


# === ONNX Model Info ===

async def get_onnx_models(pool) -> list:
    """DB에 로드된 ONNX 임베딩 모델 목록을 조회한다 (USER_MINING_MODELS)."""
    models = []
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT model_name, mining_function, algorithm, creation_date
                    FROM user_mining_models
                    WHERE algorithm = 'ONNX'
                    ORDER BY creation_date DESC
                """)
                rows = await cursor.fetchall()
                for row in rows:
                    models.append({
                        "model_name": row[0],
                        "mining_function": row[1],
                        "algorithm": row[2],
                        "creation_date": str(row[3]) if row[3] else None,
                    })
    except Exception:
        # USER_MINING_MODELS 뷰가 없거나 권한 부족 시 무시
        pass
    return models


async def load_onnx_model(pool, model_name: str, onnx_data: bytes, metadata: dict = None) -> dict:
    """ONNX 파일(바이트)을 DB에 임베딩 모델로 적재한다.

    DBMS_VECTOR.LOAD_ONNX_MODEL(model_name, model_source(BLOB), metadata(JSON))
    """
    if metadata is None:
        metadata = {
            "function": "embedding",
            "embeddingOutput": "embedding",
            "input": {"input": ["DATA"]},
        }

    metadata_json = json.dumps(metadata)

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # 임시 BLOB 생성 후 데이터 기록
            temp_blob = await conn.createlob(oracledb.DB_TYPE_BLOB)
            await temp_blob.write(onnx_data)

            # Step 1: 임시 테이블에 BLOB 저장
            await cursor.execute("""
                DECLARE
                    v_cnt NUMBER;
                BEGIN
                    SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'ONNX_TEMP';
                    IF v_cnt = 0 THEN
                        EXECUTE IMMEDIATE 'CREATE TABLE onnx_temp (name VARCHAR2(200), data BLOB)';
                    END IF;
                END;
            """)

            # 기존 데이터 삭제 후 삽입
            await cursor.execute("DELETE FROM onnx_temp WHERE name = :n", {"n": model_name})
            await cursor.execute(
                "INSERT INTO onnx_temp (name, data) VALUES (:n, :d)",
                {"n": model_name, "d": temp_blob},
            )
            await conn.commit()

            # Step 2: PL/SQL 내에서 BLOB을 읽어서 LOAD_ONNX_MODEL 호출
            plsql = f"""
                DECLARE
                    v_blob BLOB;
                BEGIN
                    SELECT data INTO v_blob FROM onnx_temp WHERE name = '{model_name}';
                    DBMS_VECTOR.LOAD_ONNX_MODEL('{model_name}', v_blob, JSON('{metadata_json}'));
                    DELETE FROM onnx_temp WHERE name = '{model_name}';
                    COMMIT;
                END;
            """
            await cursor.execute(plsql)
            await conn.commit()

    return {
        "model_name": model_name,
        "metadata": metadata,
        "size_bytes": len(onnx_data),
    }


async def load_onnx_model_cloud(pool, model_name: str, location_uri: str, onnx_file_name: str) -> dict:
    """OCI Object Storage에서 ONNX 파일을 가져와 DB에 적재한다.

    PL/SQL 흐름:
      1. DBMS_DATA_MINING.DROP_MODEL (기존 모델 제거)
      2. DBMS_CLOUD.GET_OBJECT → DATA_PUMP_DIR 로 복사
      3. DBMS_VECTOR.LOAD_ONNX_MODEL → DB 적재
    """
    start = time.time()
    clean_name = model_name.strip().upper().replace("-", "_").replace(" ", "_")
    object_uri = location_uri.rstrip("/") + "/" + onnx_file_name

    plsql = f"""
        DECLARE
            v_model_name VARCHAR2(200) := '{clean_name}';
            v_file_name  VARCHAR2(200) := '{onnx_file_name}';
            v_uri        VARCHAR2(500) := '{object_uri}';
        BEGIN
            -- 기존 모델 삭제 (없으면 무시)
            BEGIN
                DBMS_DATA_MINING.DROP_MODEL(model_name => v_model_name);
            EXCEPTION WHEN OTHERS THEN NULL;
            END;

            -- Object Storage → DATA_PUMP_DIR
            DBMS_CLOUD.GET_OBJECT(
                credential_name => NULL,
                directory_name  => 'DATA_PUMP_DIR',
                object_uri      => v_uri
            );

            -- ONNX 모델 DB 적재
            DBMS_VECTOR.LOAD_ONNX_MODEL(
                directory  => 'DATA_PUMP_DIR',
                file_name  => v_file_name,
                model_name => v_model_name
            );
        END;
    """

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(plsql)
            await conn.commit()

    elapsed_ms = int((time.time() - start) * 1000)
    return {
        "model_name": clean_name,
        "onnx_file": onnx_file_name,
        "object_uri": object_uri,
        "elapsed_ms": elapsed_ms,
    }


async def drop_onnx_model(pool, model_name: str) -> dict:
    """DB에서 ONNX 모델을 삭제한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                BEGIN
                    DBMS_DATA_MINING.DROP_MODEL(:model_name);
                END;
            """, {"model_name": model_name})
            await conn.commit()

    return {"model_name": model_name, "status": "dropped"}


async def test_onnx_model(pool, model_name: str, sample_text: str = "테스트 문장입니다") -> dict:
    """ONNX 모델로 샘플 텍스트의 임베딩을 생성하여 정상 작동을 확인한다."""
    start = time.time()
    result = {
        "model_name": model_name,
        "sample_text": sample_text[:200],
        "sql_executed": f"SELECT VECTOR_EMBEDDING({model_name} USING '{sample_text[:50]}...' AS data) FROM dual",
    }

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"""
                    SELECT VECTOR_EMBEDDING({model_name} USING :text AS data) FROM dual
                """, {"text": sample_text})
                row = await cursor.fetchone()

                if row and row[0]:
                    vec = row[0]
                    dimensions = len(vec) if hasattr(vec, '__len__') else 0
                    result["success"] = True
                    result["dimensions"] = dimensions
                    result["vector_preview"] = str(vec[:5]) + "..." if dimensions > 5 else str(vec)
                    result["processing_ms"] = int((time.time() - start) * 1000)
                else:
                    result["success"] = False
                    result["error"] = "임베딩 결과가 없습니다."
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["processing_ms"] = int((time.time() - start) * 1000)

    return result


async def get_onnx_model_detail(pool, model_name: str) -> dict:
    """ONNX 모델의 상세 정보를 조회한다."""
    detail = {"model_name": model_name}

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # 기본 정보
            try:
                await cursor.execute("""
                    SELECT model_name, mining_function, algorithm,
                           build_duration, model_size, creation_date
                    FROM user_mining_models
                    WHERE model_name = :mn
                """, {"mn": model_name})
                row = await cursor.fetchone()
                if row:
                    detail["mining_function"] = row[1]
                    detail["algorithm"] = row[2]
                    detail["build_duration"] = row[3]
                    detail["model_size"] = row[4]
                    detail["creation_date"] = str(row[5]) if row[5] else None
            except Exception:
                pass

            # 모델 속성 (DM$VA 뷰)
            try:
                await cursor.execute("""
                    SELECT attribute_name, attribute_value
                    FROM user_mining_model_attributes
                    WHERE model_name = :mn
                    ORDER BY attribute_name
                """, {"mn": model_name})
                rows = await cursor.fetchall()
                detail["attributes"] = {row[0]: row[1] for row in rows}
            except Exception:
                detail["attributes"] = {}

    return detail


# === Vector Store Table Management ===

async def drop_vector_tables(pool) -> dict:
    """Vector Store 테이블(doc_chunks, documents)을 삭제한다."""
    results = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # doc_chunks 먼저 삭제 (외래키 의존성)
            for tbl in ["DOC_CHUNKS", "DOCUMENTS"]:
                try:
                    await cursor.execute(f"""
                        DECLARE v_cnt NUMBER;
                        BEGIN
                            SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = '{tbl}';
                            IF v_cnt > 0 THEN
                                EXECUTE IMMEDIATE 'DROP TABLE {tbl.lower()} CASCADE CONSTRAINTS PURGE';
                            END IF;
                        END;
                    """)
                    results.append({"table": tbl, "status": "dropped"})
                except Exception as e:
                    results.append({"table": tbl, "status": "error", "message": str(e)})
            await conn.commit()
    return {
        "tables": results,
        "sql_executed": "DROP TABLE doc_chunks CASCADE CONSTRAINTS PURGE;\nDROP TABLE documents CASCADE CONSTRAINTS PURGE;",
    }


async def create_vector_tables_explicit(pool) -> dict:
    """Vector Store 테이블을 생성(또는 기존 테이블 연결)한다. HNSW 인덱스 포함."""
    results = []
    created = []
    existing = []

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # documents 테이블
            await cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = 'DOCUMENTS'")
            cnt = (await cursor.fetchone())[0]
            if cnt == 0:
                await cursor.execute("""
                    CREATE TABLE documents (
                        doc_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        filename    VARCHAR2(500),
                        upload_date TIMESTAMP DEFAULT SYSTIMESTAMP,
                        status      VARCHAR2(20) DEFAULT 'processing',
                        chunks_count NUMBER DEFAULT 0
                    )
                """)
                created.append("DOCUMENTS")
                results.append({"table": "DOCUMENTS", "status": "created"})
            else:
                existing.append("DOCUMENTS")
                results.append({"table": "DOCUMENTS", "status": "existing"})

            # doc_chunks 테이블
            await cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = 'DOC_CHUNKS'")
            cnt = (await cursor.fetchone())[0]
            if cnt == 0:
                await cursor.execute("""
                    CREATE TABLE doc_chunks (
                        chunk_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        doc_id      NUMBER NOT NULL,
                        chunk_text  CLOB,
                        source_file VARCHAR2(500),
                        page_num    NUMBER,
                        embedding   VECTOR
                    )
                """)
                created.append("DOC_CHUNKS")
                results.append({"table": "DOC_CHUNKS", "status": "created"})
            else:
                existing.append("DOC_CHUNKS")
                results.append({"table": "DOC_CHUNKS", "status": "existing"})

            # HNSW 벡터 인덱스
            await cursor.execute("SELECT COUNT(*) FROM user_indexes WHERE index_name = 'DOC_CHUNKS_HNSW_IDX'")
            idx_cnt = (await cursor.fetchone())[0]
            if idx_cnt == 0:
                try:
                    await cursor.execute("""
                        CREATE VECTOR INDEX doc_chunks_hnsw_idx
                        ON doc_chunks(embedding)
                        ORGANIZATION INMEMORY NEIGHBOR GRAPH
                        DISTANCE COSINE
                        WITH TARGET ACCURACY 95
                    """)
                    results.append({"table": "DOC_CHUNKS_HNSW_IDX", "status": "created"})
                except Exception as e:
                    results.append({"table": "DOC_CHUNKS_HNSW_IDX", "status": "error", "message": str(e)})
            else:
                results.append({"table": "DOC_CHUNKS_HNSW_IDX", "status": "existing"})

            await conn.commit()

    sql_list = []
    if "DOC_CHUNKS" in created:
        sql_list.append("""CREATE TABLE doc_chunks (
    chunk_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id      NUMBER NOT NULL,
    chunk_text  CLOB,
    source_file VARCHAR2(500),
    page_num    NUMBER,
    embedding   VECTOR
)""")
    sql_list.append("""CREATE VECTOR INDEX doc_chunks_hnsw_idx
ON doc_chunks(embedding)
ORGANIZATION INMEMORY NEIGHBOR GRAPH
DISTANCE COSINE
WITH TARGET ACCURACY 95""")

    return {
        "tables": results,
        "created": created,
        "existing": existing,
        "sql_executed": ";\n\n".join(sql_list) if sql_list else "-- 모든 테이블이 이미 존재합니다.",
    }


# === Table Inspection Queries ===

async def query_table_definition(pool, table_name: str = "DOC_CHUNKS") -> dict:
    """테이블 컬럼 정의를 USER_TAB_COLUMNS에서 조회한다."""
    sql = """SELECT COLUMN_ID, COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
FROM USER_TAB_COLUMNS
WHERE TABLE_NAME = :table_name
ORDER BY COLUMN_ID"""
    sql_display = sql.replace(":table_name", f"'{table_name}'")

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"table_name": table_name.upper()})
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = [dict(zip(columns, row, strict=True)) for row in rows]
        return {"sql_executed": sql_display, "columns": columns, "data": data, "row_count": len(data)}
    except Exception as e:
        return {"sql_executed": sql_display, "columns": [], "data": [], "row_count": 0, "error": str(e)}


async def query_table_data(pool, table_name: str = "DOC_CHUNKS", limit: int = 50) -> dict:
    """테이블 데이터를 조회한다. 임베딩은 축약 표시."""
    if table_name.upper() == "DOC_CHUNKS":
        sql = """SELECT chunk_id, doc_id,
       DBMS_LOB.SUBSTR(chunk_text, 80) AS chunk_text,
       source_file, page_num,
       CASE WHEN embedding IS NOT NULL THEN 'VECTOR' ELSE NULL END AS embedding
FROM doc_chunks
FETCH FIRST :lmt ROWS ONLY"""
        sql_display = sql.replace(":lmt", str(limit))
    elif table_name.upper() == "DOCUMENTS":
        sql = """SELECT doc_id, filename, upload_date, status, chunks_count
FROM documents
ORDER BY upload_date DESC
FETCH FIRST :lmt ROWS ONLY"""
        sql_display = sql.replace(":lmt", str(limit))
    else:
        return {"sql_executed": "", "columns": [], "data": [], "row_count": 0, "error": "Unknown table"}

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"lmt": limit})
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if hasattr(val, 'read'):
                            val = await _lob_to_str(val)
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        row_dict[columns[i]] = val
                    data.append(row_dict)
        return {"sql_executed": sql_display, "columns": columns, "data": data, "row_count": len(data)}
    except Exception as e:
        return {"sql_executed": sql_display, "columns": [], "data": [], "row_count": 0, "error": str(e)}


async def query_table_indexes(pool, table_name: str = "DOC_CHUNKS") -> dict:
    """테이블 인덱스 정보를 조회한다."""
    sql = """SELECT i.INDEX_NAME, i.INDEX_TYPE, i.UNIQUENESS, i.STATUS,
       c.COLUMN_POSITION, c.COLUMN_NAME
FROM USER_INDEXES i
LEFT JOIN USER_IND_COLUMNS c ON i.INDEX_NAME = c.INDEX_NAME
WHERE i.TABLE_NAME = :table_name
ORDER BY i.INDEX_NAME, c.COLUMN_POSITION"""
    sql_display = sql.replace(":table_name", f"'{table_name}'")

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"table_name": table_name.upper()})
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = [dict(zip(columns, row, strict=True)) for row in rows]
        return {"sql_executed": sql_display, "columns": columns, "data": data, "row_count": len(data)}
    except Exception as e:
        return {"sql_executed": sql_display, "columns": [], "data": [], "row_count": 0, "error": str(e)}


# === V$SQL & Explain Plan ===

async def query_recent_sql(pool) -> dict:
    """V$SQL에서 최근 실행된 벡터 관련 쿼리를 조회한다."""
    sql = """SELECT SQL_ID, PARSING_SCHEMA_NAME,
       SUBSTR(SQL_TEXT, 1, 200) AS SQL_TEXT,
       LAST_ACTIVE_TIME, EXECUTIONS, ELAPSED_TIME
FROM V$SQL
WHERE (LOWER(SQL_TEXT) LIKE '%doc_chunks%' OR LOWER(SQL_TEXT) LIKE '%vector_distance%')
  AND SQL_TEXT NOT LIKE '%V$SQL%'
ORDER BY LAST_ACTIVE_TIME DESC
FETCH FIRST 10 ROWS ONLY"""

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, val in enumerate(row):
                        if hasattr(val, 'read'):
                            val = await _lob_to_str(val)
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        row_dict[columns[i]] = val
                    data.append(row_dict)
        return {"sql_executed": sql, "columns": columns, "data": data, "row_count": len(data)}
    except Exception as e:
        return {"sql_executed": sql, "columns": [], "data": [], "row_count": 0, "error": str(e)}


async def query_explain_plan(pool) -> dict:
    """대표적인 벡터 검색 SQL의 실행 계획을 조회한다."""
    model_name = settings.EMBEDDING_MODEL

    target_sql = f"""SELECT chunk_text, source_file, page_num,
       VECTOR_DISTANCE(embedding,
           VECTOR_EMBEDDING({model_name} USING 'sample query' AS data),
           COSINE) AS distance
FROM doc_chunks
WHERE embedding IS NOT NULL
ORDER BY distance
FETCH FIRST 5 ROWS ONLY"""

    explain_sql = f"EXPLAIN PLAN FOR {target_sql}"

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # EXPLAIN PLAN 실행
                await cursor.execute(explain_sql)

                # DBMS_XPLAN.DISPLAY로 실행 계획 조회
                await cursor.execute("SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY())")
                rows = await cursor.fetchall()
                plan_lines = [str(row[0]) for row in rows]
                plan_text = "\n".join(plan_lines)

        return {
            "target_sql": target_sql,
            "explain_sql": explain_sql,
            "plan_text": plan_text,
            "plan_lines": plan_lines,
        }
    except Exception as e:
        return {
            "target_sql": target_sql,
            "explain_sql": explain_sql,
            "plan_text": "",
            "plan_lines": [],
            "error": str(e),
        }


# === Vector 2D Visualization (Simple PCA) ===

def _query_centric_2d(vectors, query_idx):
    """쿼리 벡터를 중심으로 한 2D 투영.
    X축 = 쿼리와의 코사인 유사도 (가까울수록 오른쪽)
    Y축 = 잔차 벡터의 1차 주성분 (의미적 다양성)
    """
    import math

    n = len(vectors)
    if n == 0 or query_idx is None or query_idx >= n:
        return []

    dim = len(vectors[0])
    qvec = vectors[query_idx]
    q_norm = math.sqrt(sum(x * x for x in qvec)) or 1e-10

    # 1단계: 코사인 유사도(X축) + 잔차 벡터 계산
    cos_sims = []
    residuals = []
    for i in range(n):
        v = vectors[i]
        v_norm = math.sqrt(sum(x * x for x in v)) or 1e-10
        dot = sum(qvec[j] * v[j] for j in range(dim))
        cos_sim = dot / (q_norm * v_norm)
        cos_sims.append(cos_sim)

        # 쿼리 방향 성분 제거 → 잔차
        proj_scale = dot / (q_norm * q_norm)
        residual = [v[j] - proj_scale * qvec[j] for j in range(dim)]
        residuals.append(residual)

    # 2단계: 잔차 벡터들의 1차 주성분 (power iteration)
    import random
    random.seed(42)
    pc = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in pc)) or 1e-10
    pc = [x / norm for x in pc]

    for _ in range(20):
        new_pc = [0.0] * dim
        for res in residuals:
            dot = sum(res[j] * pc[j] for j in range(dim))
            for j in range(dim):
                new_pc[j] += dot * res[j]
        norm = math.sqrt(sum(x * x for x in new_pc)) or 1e-10
        pc = [x / norm for x in new_pc]

    # 3단계: 잔차를 주성분에 투영 → Y값
    y_vals = []
    for res in residuals:
        y = sum(res[j] * pc[j] for j in range(dim))
        y_vals.append(y)

    # 4단계: 결과 조립
    result = []
    for i in range(n):
        result.append([round(cos_sims[i], 4), round(y_vals[i], 4)])

    return result


async def get_vector_visualization(pool, query: str, matched_chunk_ids: list = None, max_points: int = 200) -> dict:
    """청크 임베딩을 2D로 축소하여 시각화 데이터를 반환한다."""
    # 1. 모든 청크의 임베딩을 조회 (최대 max_points개)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT chunk_id, source_file, page_num, embedding
                FROM doc_chunks
                WHERE embedding IS NOT NULL
                FETCH FIRST :max_points ROWS ONLY
            """, {"max_points": max_points})
            rows = await cursor.fetchall()

    if not rows:
        return {"error": "임베딩된 청크가 없습니다.", "points": []}

    chunk_ids = []
    source_files = []
    page_nums = []
    vectors = []

    for row in rows:
        chunk_ids.append(row[0])
        source_files.append(row[1])
        page_nums.append(row[2])
        # oracledb VECTOR → list
        vec = row[3]
        if isinstance(vec, (list, tuple)):
            vectors.append(list(vec))
        elif hasattr(vec, '__iter__'):
            vectors.append([float(x) for x in vec])
        else:
            continue

    # 2. 쿼리 임베딩 생성
    query_vec = await get_embedding(pool, query)
    if query_vec is not None:
        if isinstance(query_vec, (list, tuple)):
            query_vec_list = list(query_vec)
        elif hasattr(query_vec, '__iter__'):
            query_vec_list = [float(x) for x in query_vec]
        else:
            query_vec_list = None
    else:
        query_vec_list = None

    # 3. 쿼리 벡터를 포함하여 PCA
    all_vectors = vectors[:]
    query_idx = None
    if query_vec_list and len(query_vec_list) == len(vectors[0]):
        query_idx = len(all_vectors)
        all_vectors.append(query_vec_list)

    if query_idx is None:
        return {"error": "쿼리 임베딩을 생성할 수 없습니다.", "points": []}

    coords_2d = _query_centric_2d(all_vectors, query_idx)

    # 4. 결과 조립
    points = []
    for i in range(len(vectors)):
        is_matched = bool(matched_chunk_ids) and chunk_ids[i] in matched_chunk_ids
        points.append({
            "chunk_id": chunk_ids[i],
            "source_file": source_files[i],
            "page_num": page_nums[i],
            "x": coords_2d[i][0],
            "y": coords_2d[i][1],
            "matched": is_matched,
        })

    query_point = {
        "x": coords_2d[query_idx][0],  # 코사인 유사도 1.0 (자기 자신)
        "y": coords_2d[query_idx][1],   # 잔차 0
        "label": query,
    }

    return {
        "points": points,
        "query_point": query_point,
        "total_chunks": len(points),
    }
