import json
import os
import tempfile
import time

import oracledb

from app.config import settings
from app.select_ai import _lob_to_str


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
                                embedding   VECTOR(768, FLOAT32)
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
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT VECTOR_EMBEDDING(:model_name USING :text_data AS data)
                FROM dual
            """, {"model_name": model_name, "text_data": text})
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None


async def get_embedding_external(text: str) -> list:
    """외부 API를 사용하여 임베딩을 생성한다."""
    import urllib.request
    import urllib.error

    api_url = settings.EMBEDDING_API_URL
    api_key = settings.EMBEDDING_API_KEY
    model = settings.EMBEDDING_MODEL

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = json.dumps({
        "input": text,
        "model": model,
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"][0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"외부 임베딩 API 호출 실패: {e}")


async def get_embedding(pool, text: str) -> list:
    """설정에 따라 DB 내부 또는 외부 API로 임베딩을 생성한다."""
    if settings.EMBEDDING_SOURCE == "database":
        return await get_embedding_from_db(pool, text, settings.EMBEDDING_MODEL)
    else:
        return await get_embedding_external(text)


# === Document Upload Pipeline ===

async def upload_document(pool, file_path: str, filename: str) -> dict:
    """PDF 파일을 처리하여 청킹 -> 임베딩 -> DB 저장 파이프라인을 실행한다."""
    pipeline = []
    start_total = time.time()

    # Step 1: 문서 레코드 생성
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

    try:
        # Step 2: PDF 텍스트 추출
        step_start = time.time()
        pages = extract_text_from_pdf(file_path)
        pipeline.append({
            "step": "문서 로드",
            "sql": "-- Python pdfplumber로 PDF 텍스트 추출",
            "duration_ms": int((time.time() - step_start) * 1000),
        })

        if not pages:
            raise ValueError("PDF에서 텍스트를 추출할 수 없습니다.")

        # Step 3: 청킹
        step_start = time.time()
        all_chunks = []
        for page in pages:
            # DB 청킹 시도, 실패 시 Python 청킹
            db_chunks = await try_db_chunking(pool, page["text"])
            if db_chunks:
                for chunk in db_chunks:
                    all_chunks.append({"text": chunk, "page_num": page["page_num"]})
            else:
                py_chunks = chunk_text_python(page["text"])
                for chunk in py_chunks:
                    all_chunks.append({"text": chunk, "page_num": page["page_num"]})

        chunking_sql = "SELECT DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS(:text, JSON('{\"max_chunk_size\": 500, \"overlap\": 50}')) FROM dual"
        pipeline.append({
            "step": "청크 분할",
            "sql": chunking_sql,
            "duration_ms": int((time.time() - step_start) * 1000),
        })

        # Step 4: 임베딩 생성 + DB 저장
        step_start_embed = time.time()
        embed_count = 0
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for chunk_info in all_chunks:
                    try:
                        embedding = await get_embedding(pool, chunk_info["text"])
                        if embedding is not None:
                            await cursor.execute("""
                                INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num, embedding)
                                VALUES (:doc_id, :chunk_text, :source_file, :page_num, :embedding)
                            """, {
                                "doc_id": doc_id,
                                "chunk_text": chunk_info["text"],
                                "source_file": filename,
                                "page_num": chunk_info["page_num"],
                                "embedding": embedding,
                            })
                            embed_count += 1
                        else:
                            # 임베딩 없이 텍스트만 저장
                            await cursor.execute("""
                                INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num)
                                VALUES (:doc_id, :chunk_text, :source_file, :page_num)
                            """, {
                                "doc_id": doc_id,
                                "chunk_text": chunk_info["text"],
                                "source_file": filename,
                                "page_num": chunk_info["page_num"],
                            })
                            embed_count += 1
                    except Exception:
                        # 개별 청크 실패 시 임베딩 없이 저장
                        await cursor.execute("""
                            INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num)
                            VALUES (:doc_id, :chunk_text, :source_file, :page_num)
                        """, {
                            "doc_id": doc_id,
                            "chunk_text": chunk_info["text"],
                            "source_file": filename,
                            "page_num": chunk_info["page_num"],
                        })
                        embed_count += 1

                await conn.commit()

        if settings.EMBEDDING_SOURCE == "database":
            embed_sql = f"SELECT VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING :text AS data) FROM dual"
        else:
            embed_sql = f"-- 외부 API ({settings.EMBEDDING_MODEL}) 호출 후 벡터 INSERT"

        pipeline.append({
            "step": "임베딩 생성",
            "sql": embed_sql,
            "duration_ms": int((time.time() - step_start_embed) * 1000),
        })

        step_start_save = time.time()
        pipeline.append({
            "step": "DB 저장",
            "sql": "INSERT INTO doc_chunks (doc_id, chunk_text, source_file, page_num, embedding) VALUES (:1, :2, :3, :4, :5)",
            "duration_ms": int((time.time() - step_start_save) * 1000),
        })

        # Step 5: 문서 상태 업데이트
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE documents
                    SET status = 'indexed', chunks_count = :cnt
                    WHERE doc_id = :doc_id
                """, {"cnt": embed_count, "doc_id": doc_id})
                await conn.commit()

        return {
            "success": True,
            "filename": filename,
            "doc_id": doc_id,
            "chunks_count": embed_count,
            "pipeline": pipeline,
            "total_ms": int((time.time() - start_total) * 1000),
        }

    except Exception as e:
        # 실패 시 문서 상태를 error로 업데이트
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE documents SET status = 'error' WHERE doc_id = :doc_id
                    """, {"doc_id": doc_id})
                    await conn.commit()
        except Exception:
            pass
        raise e


# === Search Functions ===

async def vector_search(pool, query: str, top_k: int = 5) -> dict:
    """벡터 유사도 검색을 수행한다."""
    start = time.time()

    if settings.EMBEDDING_SOURCE == "database":
        # DB 내 임베딩 모델 사용
        sql = f"""
            SELECT chunk_text, source_file, page_num,
                   VECTOR_DISTANCE(embedding,
                       VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING :query AS data),
                       COSINE) AS distance
            FROM doc_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = sql.replace(":query", f"'{query}'").replace(":top_k", str(top_k))

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"query": query, "top_k": top_k})
                rows = await cursor.fetchall()
                columns = [col[0] for col in cursor.description]
    else:
        # 외부 임베딩 사용
        query_vector = await get_embedding_external(query)
        sql = """
            SELECT chunk_text, source_file, page_num,
                   VECTOR_DISTANCE(embedding, :query_vector, COSINE) AS distance
            FROM doc_chunks
            WHERE embedding IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""SELECT chunk_text, source_file, page_num,
       VECTOR_DISTANCE(embedding,
           VECTOR_EMBEDDING({settings.EMBEDDING_MODEL} USING '{query}' AS data),
           COSINE) AS distance
FROM doc_chunks
WHERE embedding IS NOT NULL
ORDER BY distance
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, {"query_vector": query_vector, "top_k": top_k})
                rows = await cursor.fetchall()
                columns = [col[0] for col in cursor.description]

    chunks = []
    for row in rows:
        chunk_text = await _lob_to_str(row[0]) if hasattr(row[0], 'read') else row[0]
        similarity = 1 - (row[3] if row[3] else 0)  # cosine distance -> similarity
        chunks.append({
            "chunk_text": chunk_text,
            "source_file": row[1],
            "page_num": row[2],
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

    try:
        # Oracle Text CONTAINS 시도
        sql_contains = """
            SELECT chunk_text, source_file, page_num, SCORE(1) AS relevance
            FROM doc_chunks
            WHERE CONTAINS(chunk_text, :query, 1) > 0
            ORDER BY relevance DESC
            FETCH FIRST :top_k ROWS ONLY
        """
        sql_executed = f"""SELECT chunk_text, source_file, page_num, SCORE(1) AS relevance
FROM doc_chunks
WHERE CONTAINS(chunk_text, '{query}', 1) > 0
ORDER BY relevance DESC
FETCH FIRST {top_k} ROWS ONLY"""

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql_contains, {"query": query, "top_k": top_k})
                rows = await cursor.fetchall()

    except Exception:
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


# === RAG Answer Generation ===

async def generate_rag_answer(pool, query: str, chunks: list, profile_name: str) -> str:
    """검색된 청크를 컨텍스트로 LLM 답변을 생성한다."""
    context = "\n\n".join([c["chunk_text"] for c in chunks if c.get("chunk_text")])

    prompt = f"""다음 문서 내용을 참고하여 질문에 답변하세요.

[참고 문서]
{context}

[질문]
{query}

문서에 없는 내용은 답변하지 마세요."""

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                sql = """
                    SELECT DBMS_CLOUD_AI.GENERATE(
                        prompt       => :prompt,
                        profile_name => :profile,
                        action       => 'chat'
                    ) FROM dual
                """
                await cursor.execute(sql, {
                    "prompt": prompt,
                    "profile": profile_name,
                })
                row = await cursor.fetchone()
                if row:
                    return await _lob_to_str(row[0])
                return "답변을 생성할 수 없습니다."
    except Exception as e:
        return f"LLM 답변 생성 중 오류: {str(e)}"


# === Document Management ===

async def list_documents(pool) -> list:
    """업로드된 문서 목록을 조회한다."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT doc_id, filename, upload_date, status, chunks_count
                FROM documents
                ORDER BY upload_date DESC
            """)
            rows = await cursor.fetchall()
            return [
                {
                    "doc_id": row[0],
                    "filename": row[1],
                    "upload_date": row[2].isoformat() if row[2] else None,
                    "status": row[3],
                    "chunks_count": row[4],
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
                        embedding   VECTOR(768, FLOAT32)
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
    embedding   VECTOR(768, FLOAT32)
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
                data = [dict(zip(columns, row)) for row in rows]
        return {"sql_executed": sql_display, "columns": columns, "data": data, "row_count": len(data)}
    except Exception as e:
        return {"sql_executed": sql_display, "columns": [], "data": [], "row_count": 0, "error": str(e)}


async def query_table_data(pool, table_name: str = "DOC_CHUNKS", limit: int = 50) -> dict:
    """테이블 데이터를 조회한다. 임베딩은 축약 표시."""
    if table_name.upper() == "DOC_CHUNKS":
        sql = """SELECT chunk_id, doc_id,
       DBMS_LOB.SUBSTR(chunk_text, 80) AS chunk_text,
       source_file, page_num,
       CASE WHEN embedding IS NOT NULL THEN 'VECTOR(768)' ELSE NULL END AS embedding
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
                data = [dict(zip(columns, row)) for row in rows]
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
