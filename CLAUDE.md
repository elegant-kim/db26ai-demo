# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Oracle AI Database 26ai demo application with two tabs: **NL2SQL (Select AI)** and **AI Vector Search**. Targets developers/DBAs new to natural language SQL generation. Runs on Oracle Autonomous Database with python-oracledb thin client.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit with DB credentials

# Run (auto-reloads on file changes)
python main.py
# → http://localhost:8000
```

No build step needed — Vue 3 and Chart.js load from CDN.

## Architecture

**Backend (Python FastAPI)**:
- `main.py` — FastAPI entry point, mounts static files, registers routes, initializes DB pool + vector tables on startup
- `app/config.py` — Settings from `.env` via `python-dotenv`
- `app/database.py` — Async oracledb connection pool (`create_pool_async`), 120s call timeout
- `app/select_ai.py` — Core Select AI logic: `DBMS_CLOUD_AI.GENERATE` calls, profile management (`DBA_CLOUD_AI_PROFILES`), raw SQL execution, schema info with annotations, EXPLAIN PLAN
- `app/routes.py` — All API endpoints under `/api` prefix (`APIRouter(prefix="/api")`)
- `app/vector_search.py` — Vector search: PDF upload/chunking, HNSW index (`ORGANIZATION INMEMORY NEIGHBOR GRAPH`), `VECTOR_EMBEDDING`/`VECTOR_DISTANCE`, RAG answer generation

**Frontend (Single-page, no build)**:
- `templates/index.html` — Jinja2 template, Vue 3 with `[[ ]]` delimiters (not `{{ }}` to avoid Jinja conflicts)
- `static/js/app.js` — Vue 3 Composition API app (`createApp` + `setup()`), all reactive state and API calls
- `static/css/style.css` — Custom styles with CSS variables

**Key patterns**:
- Oracle LOB values require `await _lob_to_str(val)` conversion before serialization
- All DB queries use `async with pool.acquire() as conn` → `async with conn.cursor() as cursor`
- Cache busting: `style.css?v=N` and `app.js?v=N` in index.html — increment on changes
- Profile-dependent behavior: example questions, annotation sets, and schema viewer switch based on profile name containing 'SH' or 'SSB'
- DDL statements (ALTER TABLE for annotations) cannot use bind variables — use string formatting with `replace("'", "''")`

## Key Oracle DB Dependencies

- `DBMS_CLOUD_AI.GENERATE(prompt, profile_name, action)` — NL2SQL core
- `DBMS_CLOUD_AI.SET_PROFILE(profile_name)` — Set active AI profile
- `DBA_CLOUD_AI_PROFILES` / `DBA_CLOUD_AI_PROFILE_ATTRIBUTES` — Profile metadata (fallback to USER_ views)
- `ALL_ANNOTATIONS_USAGE` — Column/table annotations (Oracle 23ai+ feature)
- `DBMS_XPLAN.DISPLAY()` — Execution plan display
- `V$SQL` — Recent SQL inspection
- Sample schemas: SH (Sales History), SSB (Star Schema Benchmark)

## Important Conventions

- All text in the UI is Korean (데모 target audience)
- `explainsql` action appends Korean instruction: `"(Please explain in Korean / 한국어로 설명해 주세요)"`
- `execute_raw_sql()` only allows SELECT statements (security)
- Frontend fetch calls use 120s `AbortController` timeout matching DB call timeout
