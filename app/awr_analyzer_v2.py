"""
AWR HTML Report Analyzer V2
- 섹션 제목 문자열 검색 기반 HTML 파싱 (23개 섹션)
- 8개 섹션 구조의 분석 보고서 생성 프롬프트
"""

import re
from html.parser import HTMLParser

from app.llm_client import call_llm, call_llm_json


# ── 섹션 제목 → 카테고리 매핑 (23개 섹션) ─────────────────────

SECTION_TITLES = [
    # 1. Report Header
    ("This table displays database instance information", "report_header"),
    ("Database Instance Information", "report_header"),
    ("DB Name", "report_header"),
    # 2. Host Info
    ("Host Information", "host_info"),
    ("host information", "host_info"),
    # 3. ADDM Findings
    ("Top ADDM Findings", "addm_findings"),
    ("ADDM Findings", "addm_findings"),
    # 4. Load Profile
    ("Load Profile", "load_profile"),
    # 5. Instance Efficiency
    ("Instance Efficiency", "instance_efficiency"),
    # 6. Top 10 Foreground Events
    ("Top 10 Foreground Events", "top_foreground_events"),
    ("Top Timed Events", "top_foreground_events"),
    # 7. Wait Classes by Total Wait Time
    ("Wait Classes by Total Wait Time", "wait_classes"),
    ("Foreground Wait Class", "wait_classes"),
    # 8. Host CPU
    ("Host CPU", "host_cpu"),
    # 9. Instance CPU
    ("Instance CPU", "instance_cpu"),
    # 10. IO Profile
    ("IO Profile", "io_profile"),
    ("IOStat by Function", "io_profile"),
    # 11. Memory Statistics
    ("Memory Statistics", "memory_statistics"),
    # 12. SQL ordered by Elapsed Time
    ("SQL ordered by Elapsed Time", "sql_elapsed"),
    # 13. Segments by Logical Reads
    ("Segments by Logical Reads", "segments_logical"),
    # 14. Segments by Physical Reads
    ("Segments by Physical Reads", "segments_physical"),
    # 15. SGA Memory Summary
    ("SGA Memory Summary", "sga_summary"),
    # 16. Buffer Pool Advisory
    ("Buffer Pool Advisory", "buffer_pool_advisory"),
    # 17. SGA Target Advisory
    ("SGA Target Advisory", "sga_target_advisory"),
    # 18. PGA Memory Advisory
    ("PGA Memory Advisory", "pga_memory_advisory"),
    ("PGA Target Advisory", "pga_memory_advisory"),
    # 19. Tablespace IO Stats
    ("Tablespace IO Stats", "tablespace_io"),
    # 20. Global Cache Efficiency (RAC)
    ("Global Cache Efficiency", "gc_efficiency"),
    ("Global Cache and Enqueue Services - Workload Characteristics", "gc_efficiency"),
    # 21. Global Cache and Enqueue (RAC)
    ("Global Cache and Enqueue", "gc_enqueue"),
    # 22. Global Cache Transfer (RAC)
    ("Global Cache Transfer Stats", "gc_transfer"),
    ("Interconnect Ping", "gc_transfer"),
    # 23. Interconnect Statistics (RAC)
    ("Interconnect Statistics", "interconnect_stats"),
    ("Dynamic Remastering Stats", "interconnect_stats"),
]

# 스냅샷 정보 관련 패턴 (Report Header 보조)
SNAPSHOT_PATTERNS = [
    ("Snap Id", "snapshot_info"),
    ("Snapshots", "snapshot_info"),
    ("Begin Snap", "snapshot_info"),
    ("End Snap", "snapshot_info"),
    ("Elapsed", "snapshot_info"),
    ("DB Time", "snapshot_info"),
]

# SQL 행 최대 수
MAX_SQL_ROWS = 15
MAX_SEGMENT_ROWS = 5
MAX_ADVISORY_ROWS = 20
MAX_DEFAULT_ROWS = 30


class _TableParser(HTMLParser):
    """특정 위치부터 테이블 <tr> 태그를 파싱하여 행(row) 목록을 추출"""

    def __init__(self):
        super().__init__()
        self.tables = []         # [{headers: [], rows: []}]
        self._cur_table = None
        self._cur_row = []
        self._cur_cell = ""
        self._cur_headers = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._is_header_cell = False
        self._depth = 0          # table nesting depth

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._in_table = True
                self._cur_table = {"headers": [], "rows": []}
                self._cur_headers = []
        elif tag == "tr" and self._in_table and self._depth == 1:
            self._in_row = True
            self._cur_row = []
        elif tag in ("th", "td") and self._in_row:
            self._in_cell = True
            self._is_header_cell = (tag == "th")
            self._cur_cell = ""

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table":
            if self._depth == 1 and self._cur_table:
                self._cur_table["headers"] = self._cur_headers
                if self._cur_table["headers"] or self._cur_table["rows"]:
                    self.tables.append(self._cur_table)
                self._cur_table = None
                self._in_table = False
            self._depth = max(0, self._depth - 1)
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._cur_row and self._cur_table:
                self._cur_table["rows"].append(self._cur_row)
        elif tag in ("th", "td") and self._in_cell:
            self._in_cell = False
            cell_text = re.sub(r"\s+", " ", self._cur_cell.strip())
            if self._is_header_cell and self._cur_table:
                self._cur_headers.append(cell_text)
            self._cur_row.append(cell_text)

    def handle_data(self, data):
        if self._in_cell:
            self._cur_cell += data


def _find_section_pos(html_lower: str, title: str) -> int:
    """
    HTML(소문자)에서 섹션 제목 위치를 찾는다.
    목차(TOC)의 <li>/<a href=> 링크를 건너뛰고,
    실제 섹션 헤더(<h3>, <h2>) 또는 테이블 summary/caption 근처를 찾는다.
    """
    title_lower = title.lower()
    start = 0
    while True:
        pos = html_lower.find(title_lower, start)
        if pos < 0:
            return -1

        # pos 앞쪽 300자를 확인하여 목차 링크인지 판별
        context_start = max(0, pos - 300)
        before = html_lower[context_start:pos]

        # 목차 링크 패턴: <li 또는 <a href= 가 가장 가까운 태그이고
        # <h2, <h3, <table, summary= 가 없는 경우 → 목차이므로 건너뜀
        last_li = before.rfind("<li")
        last_a_href = before.rfind("<a ")  # <a class="awr" href="#400">
        last_h2 = before.rfind("<h2")
        last_h3 = before.rfind("<h3")
        last_table = before.rfind("<table")
        last_summary = before.rfind("summary=")
        last_caption = before.rfind("<caption")

        # 가장 가까운 태그 유형 판별
        toc_pos = max(last_li, last_a_href)
        content_pos = max(last_h2, last_h3, last_table, last_summary, last_caption)

        if toc_pos > content_pos and content_pos < 0:
            # 목차 링크에서 찾은 것 → 건너뛰고 다음 위치 검색
            start = pos + len(title_lower)
            continue

        return pos


def _extract_tables_at(html: str, pos: int, max_tables: int = 3) -> list:
    """주어진 위치 이후의 HTML에서 테이블들을 추출 (최대 max_tables개)"""
    html_lower = html.lower()

    # 해당 위치에서 앞쪽 약간 포함하여 시작 (테이블이 제목 바로 뒤에 올 수 있음)
    search_start = max(0, pos - 100)

    # 다음 섹션까지의 범위를 추정 (보통 <h2> 또는 <h3>으로 구분)
    # pos+100 이후의 다음 h2/h3를 찾되, 너무 가까운 것은 건너뜀
    # (현재 섹션의 <h3> 자체를 잡지 않도록 pos 이후 첫 <table> 너머에서 찾음)
    first_table = html_lower.find("<table", pos)
    scan_from = first_table + 50 if first_table > 0 else pos + 200

    next_section = len(html)
    for marker in ["<h2", "<h3"]:
        idx = html_lower.find(marker, scan_from)
        if idx > 0 and idx < next_section:
            next_section = idx

    # 범위 내 HTML 추출
    chunk = html[search_start:next_section]

    parser = _TableParser()
    try:
        parser.feed(chunk)
    except Exception:
        pass

    return parser.tables[:max_tables]


def _table_to_text(table: dict, max_rows: int = MAX_DEFAULT_ROWS) -> str:
    """테이블을 텍스트로 변환"""
    lines = []
    headers = table.get("headers", [])
    rows = table.get("rows", [])[:max_rows]

    if headers:
        lines.append(" | ".join(headers))
        lines.append("-" * 40)

    for row in rows:
        # 200자 초과 셀은 잘라냄 (SQL Text 등)
        trimmed = [c[:200] if len(c) > 200 else c for c in row]
        lines.append(" | ".join(trimmed))

    return "\n".join(lines)


def parse_awr_html_v2(html_content: str) -> dict:
    """
    AWR HTML을 섹션 제목 검색 방식으로 파싱한다.
    전체를 한번에 읽지 않고, 섹션 제목 문자열을 검색하여
    해당 위치의 HTML <tr> 태그를 파싱하는 방식.

    Returns: {
        "sections": { category: "텍스트" },
        "raw_text": "전체 추출 텍스트",
        "is_rac": bool,
        "is_exadata": bool,
        "section_count": int,
    }
    """
    html_lower = html_content.lower()
    sections = {}
    found_positions = {}  # category -> pos (중복 방지)

    # 1) 메인 23개 섹션 추출
    for title, category in SECTION_TITLES:
        if category in found_positions:
            continue  # 이미 찾은 카테고리는 건너뜀

        pos = _find_section_pos(html_lower, title)
        if pos < 0:
            continue

        found_positions[category] = pos

        # 카테고리별 최대 행 수 조절
        if category == "sql_elapsed":
            max_rows = MAX_SQL_ROWS
        elif category in ("segments_logical", "segments_physical"):
            max_rows = MAX_SEGMENT_ROWS
        elif category in ("buffer_pool_advisory", "sga_target_advisory", "pga_memory_advisory"):
            max_rows = MAX_ADVISORY_ROWS
        else:
            max_rows = MAX_DEFAULT_ROWS

        tables = _extract_tables_at(html_content, pos)
        if tables:
            texts = []
            for t in tables:
                text = _table_to_text(t, max_rows=max_rows)
                if text.strip():
                    texts.append(text)
            if texts:
                sections[category] = "\n\n".join(texts)

    # 2) 스냅샷 정보 보충 (Report Header에 없는 경우)
    if "snapshot_info" not in sections:
        for title, category in SNAPSHOT_PATTERNS:
            pos = _find_section_pos(html_lower, title)
            if pos >= 0:
                tables = _extract_tables_at(html_content, pos, max_tables=2)
                if tables:
                    texts = [_table_to_text(t, max_rows=10) for t in tables]
                    combined = "\n\n".join(t for t in texts if t.strip())
                    if combined:
                        sections["snapshot_info"] = combined
                        break

    # 3) RAC / Exadata 감지
    is_rac = any(cat.startswith("gc_") or cat == "interconnect_stats" for cat in sections)
    # RAC 키워드 추가 감지
    if not is_rac and re.search(r"global cache|interconnect|gc cr|gc current", html_lower):
        is_rac = True

    is_exadata = bool(re.search(r"exadata|cell server|smart scan|cell offload|cell physical", html_lower))

    # 4) 전체 텍스트 조립
    section_order = [
        "report_header", "host_info", "snapshot_info",
        "addm_findings", "load_profile", "instance_efficiency",
        "top_foreground_events", "wait_classes",
        "host_cpu", "instance_cpu", "io_profile",
        "memory_statistics", "sql_elapsed",
        "segments_logical", "segments_physical",
        "sga_summary", "buffer_pool_advisory", "sga_target_advisory", "pga_memory_advisory",
        "tablespace_io",
        "gc_efficiency", "gc_enqueue", "gc_transfer", "interconnect_stats",
    ]

    raw_parts = []
    for cat in section_order:
        if cat in sections:
            label = cat.upper().replace("_", " ")
            raw_parts.append(f"=== {label} ===\n{sections[cat]}")

    raw_text = "\n\n".join(raw_parts)

    return {
        "sections": sections,
        "raw_text": raw_text,
        "is_rac": is_rac,
        "is_exadata": is_exadata,
        "section_count": len(sections),
    }


# ── LLM 프롬프트 ───────────────────────────────────────────────

AWR_V2_PROMPT = """당신은 20년 경력의 Oracle Database 성능 튜닝 전문가(Oracle ACE)입니다.
아래 AWR 리포트 데이터를 분석하여 구조화된 보고서를 작성하세요.

## 입력 데이터
{awr_data}

## 환경 정보
{env_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[분석 보고서 작성 지시]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
추출한 데이터를 기반으로 아래 구조의 분석 보고서를 작성하세요.

### 보고서 구조

#### 1. 시스템 개요
- DB명, 인스턴스명, 스냅샷 구간, 호스트 정보를 표로 정리
- **DB Time / Elapsed Time 비율** 계산 → AAS(Average Active Sessions) 산출
- CPU 코어 수 대비 AAS가 얼마인지 평가하여 부하 수준 판단

#### 2. 핵심 병목 진단: Top Wait Events
- Top 10 Foreground Events를 표로 정리
- **DB CPU vs User I/O vs Cluster Wait 비율**을 분석하여
  워크로드 유형 판단 (CPU-bound / IO-bound / 혼합)
- 각 주요 이벤트가 의미하는 바를 설명:
  - cell smart table scan → Exadata Smart Scan (Full Table Scan)
  - cell single block physical read → 인덱스 기반 단일 블록 읽기
  - gc cr disk read / gc cr grant 2-way → RAC 클러스터 간 블록 전송
  - direct path read/write temp → PGA 부족으로 인한 디스크 정렬

#### 3. Top SQL 분석
- Elapsed Time 기준 상위 10개 SQL을 표로 정리
- 각 SQL에 대해 다음을 분석:
  - %CPU vs %IO 비율로 병목 유형 판단
  - 실행횟수와 1회 실행시간으로 튜닝 우선순위 판단
  - SQL Module로 실행 출처 파악 (ETL, JDBC, SQL Developer 등)
  - SQL Text로 DML 유형 파악 (SELECT/INSERT/DELETE/UPDATE)
- 동일 SQL ID가 반복 등장하거나, 특정 모듈에 편중된 패턴이 있으면 지적

#### 4. I/O 분석
- Physical Read/Write 초당 블록 수, MB 수 정리
- Buffer Cache Hit Ratio 평가 (95% 이하이면 경고)
- Direct Path Read 비율 → Full Table Scan 비중 판단
- Smart Scan vs Buffer Cache Read 비율 분석

#### 5. Hot Segments
- Physical Reads 기준 상위 5개 세그먼트를 표로 정리
- Logical Reads 기준 상위 5개도 함께 제시
- Top SQL과의 연관성 분석 (동일 테이블이 Top SQL에서 접근되는지)

#### 6. 메모리 분석
- SGA/PGA 현재 크기 및 Host Memory 대비 비율 정리
- **SGA Target Advisory 해석**:
  - 현재 Size Factor 1.0 대비 1.5배, 2.0배 시 Est DB Time 감소율 계산
  - SGA 증설 효과가 있는지 판단
- **PGA Memory Advisory 해석**:
  - 현재 Cache Hit % 확인
  - Size Factor 1.2 시 Cache Hit 개선폭 확인
  - PGA 증설 권고 여부 판단
- **Buffer Pool Advisory 해석**:
  - Est Phys Read Factor가 1.0 이하가 되는 Size Factor 확인
- ADDM의 Undersized SGA/PGA 지적이 있으면 Advisory 수치와 대조

#### 7. Host CPU
- %User, %System, %Idle 정리
- DB CPU / Total CPU, DB CPU / Busy CPU 비율 해석
- CPU 병목이 OS 수준인지, SQL 비효율인지 판단

#### 8. 종합 권고사항
아래 우선순위 체계로 분류하여 작성:
- **[긴급]**: 즉시 조치 필요 (성능에 큰 영향)
- **[높음]**: 단기 내 조치 권고
- **[중간]**: 중기 과제

각 권고에는 반드시 다음을 포함:
- 문제의 근거 (어떤 수치가 어떤 기준을 초과하는지)
- 구체적인 조치 방안 (SQL 튜닝, 파라미터 변경, 인덱스 추가 등)
- 기대 효과

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[형식 지시]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

한국어로 작성
각 섹션에 간결한 해석을 덧붙이되, 불필요한 일반론은 생략
수치의 단위(초, MB, %, blocks/sec 등)를 반드시 명시
비정상 수치는 ⚠️ 표시로 강조

## 출력 형식
반드시 아래 JSON 구조만 출력하세요. JSON 외의 텍스트는 절대 포함하지 마세요.
모든 해석/설명은 한국어로 작성하되, Oracle 기술 용어(Wait Event 이름, 파라미터명 등)는 영문 그대로 유지하세요.

### 섹션 렌더링 유형 설명
각 섹션은 아래 3가지 데이터 유형의 조합으로 구성됩니다:
- **data** (key-value 쌍): label:value 2컬럼 그리드로 압축 표현됩니다. 시스템 정보, 수치 지표 등에 사용.
- **table** (headers + rows 배열): HTML 테이블로 렌더링됩니다. 이벤트 목록, SQL 목록, 세그먼트 목록 등에 사용.
- **interpretation** (문자열): 섹션 하단의 서술형 해석 텍스트. 분석 의견, 판단 근거 등.

```json
{{
  "categoryScores": {{
    "systemLoad": {{ "score": 80, "label": "시스템 부하", "detail": "AAS vs CPU cores 기반 점수 근거" }},
    "waitEvents": {{ "score": 70, "label": "Wait Events", "detail": "Top Event의 DB Time 비중과 심각도 근거" }},
    "topSql": {{ "score": 75, "label": "Top SQL", "detail": "%CPU/%IO 편중도, Hard Parse 비율 근거" }},
    "ioPerformance": {{ "score": 75, "label": "I/O 성능", "detail": "Buffer Cache Hit %, Physical Reads 근거" }},
    "hotSegments": {{ "score": 80, "label": "Hot Segments", "detail": "Physical Reads 집중도, Top SQL 연관 근거" }},
    "memory": {{ "score": 80, "label": "메모리", "detail": "SGA/PGA Advisory 기반 근거" }},
    "hostCpu": {{ "score": 85, "label": "Host CPU", "detail": "%Idle, DB CPU/Busy CPU 비율 근거" }}
  }},
  "section1_system_overview": {{
    "title": "시스템 개요",
    "data": {{
      "DB명": "값",
      "인스턴스": "값",
      "호스트": "값",
      "플랫폼": "값",
      "CPU Cores": "값",
      "메모리": "값",
      "스냅샷 시작": "값",
      "스냅샷 종료": "값",
      "Elapsed Time": "값",
      "DB Time": "값",
      "AAS": "값",
      "부하 수준": "값 (예: AAS 2.0 / 16 cores = 12.5% → 낮음)"
    }},
    "interpretation": "DB Time / Elapsed Time 비율과 AAS 기반 부하 수준 판단 해석"
  }},
  "section2_bottleneck": {{
    "title": "핵심 병목 진단: Top Wait Events",
    "table": {{
      "headers": ["Event", "Wait Class", "Waits", "Total Wait Time", "Avg Wait", "%DB Time"],
      "rows": [
        ["이벤트명", "Wait Class", "건수", "총 시간", "평균 시간", "비율"]
      ]
    }},
    "interpretation": "DB CPU vs User I/O vs Cluster Wait 비율 분석, 워크로드 유형 판단, 주요 이벤트 의미 설명"
  }},
  "section3_top_sql": {{
    "title": "Top SQL 분석",
    "table": {{
      "headers": ["SQL ID", "Elapsed", "Execs", "Elapsed/Exec", "%CPU", "%IO", "Module", "SQL Text"],
      "rows": [
        ["SQL ID 값", "시간", "횟수", "1회 시간", "비율", "비율", "모듈", "SQL 앞부분"]
      ]
    }},
    "interpretation": "각 SQL별 병목 유형 판단, 튜닝 우선순위, 패턴 지적"
  }},
  "section4_io": {{
    "title": "I/O 분석",
    "data": {{
      "Physical Reads/s": "값",
      "Physical Writes/s": "값",
      "Read MB/s": "값",
      "Write MB/s": "값",
      "Buffer Cache Hit %": "값 ⚠️(95% 이하시)",
      "Direct Path Read %": "값"
    }},
    "interpretation": "Buffer Cache Hit Ratio 평가, Direct Path Read 비율, Smart Scan 비율 분석"
  }},
  "section5_hot_segments": {{
    "title": "Hot Segments",
    "tables": [
      {{
        "subtitle": "Physical Reads 기준 Top 5",
        "headers": ["Segment", "Type", "Physical Reads"],
        "rows": [["OWNER.NAME", "TABLE/INDEX", "값"]]
      }},
      {{
        "subtitle": "Logical Reads 기준 Top 5",
        "headers": ["Segment", "Type", "Logical Reads"],
        "rows": [["OWNER.NAME", "TABLE/INDEX", "값"]]
      }}
    ],
    "interpretation": "Top SQL과의 연관성 분석"
  }},
  "section6_memory": {{
    "title": "메모리 분석",
    "data": {{
      "Host Memory": "값",
      "SGA Size": "값",
      "PGA Size": "값",
      "SGA / Host Memory": "값%",
      "PGA / Host Memory": "값%"
    }},
    "interpretation": "SGA Target Advisory 해석 (Size Factor별 Est DB Time 감소율), PGA Memory Advisory 해석 (Cache Hit % 변화), Buffer Pool Advisory 해석 (Est Phys Read Factor), ADDM 대조"
  }},
  "section7_host_cpu": {{
    "title": "Host CPU",
    "data": {{
      "%User": "값",
      "%System": "값",
      "%WIO": "값",
      "%Idle": "값 ⚠️(10% 미만시)",
      "Load Average": "값",
      "DB CPU / Total CPU": "값%",
      "DB CPU / Busy CPU": "값%"
    }},
    "interpretation": "CPU 병목이 OS 수준인지 SQL 비효율인지 판단"
  }},
  "section8_recommendations": {{
    "title": "종합 권고사항",
    "interpretation": "[긴급]/[높음]/[중간] 우선순위별 권고사항 서술 (각각 근거+조치+기대효과)"
  }},
  "actionItems": [
    {{
      "priority": "[긴급]",
      "action": "구체적 조치 사항",
      "evidence": "문제의 근거 (어떤 수치가 어떤 기준을 초과하는지)",
      "expectedImpact": "기대 효과",
      "category": "시스템 부하 | Wait Events | Top SQL | I/O | Hot Segments | 메모리 | Host CPU"
    }}
  ]
}}
```

## 점수 산정 기준 (각 카테고리 0~100)
- **시스템 부하**: AAS < CPU cores이면 양호. AAS/cores 비율이 50% 이상이면 주의, 80% 이상이면 위험
- **Wait Events**: Top 1 이벤트가 DB CPU이면 높은 점수. Cluster/Concurrency wait class 비중이 크면 감점
- **Top SQL**: 상위 SQL의 %CPU/%IO 편중이 적으면 양호. Hard Parse 비율 높으면 감점
- **I/O 성능**: Buffer Cache Hit > 95%이면 양호. Direct Path Read 비율 과다 시 감점
- **Hot Segments**: Top Segment의 Physical Reads 집중도가 낮으면 양호. Top SQL과 연관 시 감점
- **메모리**: SGA/PGA Advisory에서 현재 크기가 적절하면 양호. ADDM Undersized 지적 시 감점
- **Host CPU**: %Idle 50% 이상이면 양호, 10% 미만이면 위험

## 추가 지침
- categoryScores의 각 score는 0~100 정수
- actionItems는 priority순([긴급]→[높음]→[중간])으로 최대 10개
- section2 table의 rows는 상위 10개까지
- section3 table의 rows는 상위 10개까지
- section5 tables의 각 rows는 상위 5개까지
- data의 값에 비정상 수치가 있으면 ⚠️를 값 뒤에 붙여주세요"""


FOLLOWUP_V2_PROMPT = """당신은 Oracle Database 성능 전문가입니다. 이전에 분석한 AWR 리포트에 대해 사용자가 후속 질문을 합니다.

## 이전 AWR 데이터
{awr_data}

## 이전 분석 결과 요약
{previous_sections}

## 사용자 질문
{question}

한국어로 답변하되, Oracle 기술 용어는 영문 그대로 유지하세요. 가능한 한 구체적이고 실행 가능한 조언을 제공하세요.
표를 활용하여 수치를 정리하고, 비정상 수치는 ⚠️ 표시로 강조하세요."""


def build_analysis_prompt_v2(parsed: dict, max_input_chars: int = 12000) -> str:
    """V2 파싱 결과로 LLM 프롬프트를 생성"""
    env_parts = []
    if parsed["is_rac"]:
        env_parts.append("이 시스템은 RAC(Real Application Clusters) 환경입니다. RAC 관련 지표(Global Cache, Interconnect)도 분석해 주세요.")
    if parsed["is_exadata"]:
        env_parts.append("이 시스템은 Exadata 환경입니다. Smart Scan, Cell Offload 관련 지표도 분석해 주세요.")
    if not env_parts:
        env_parts.append("단일 인스턴스, 비-Exadata 환경입니다.")

    return AWR_V2_PROMPT.format(
        awr_data=parsed["raw_text"][:max_input_chars],
        env_info="\n".join(env_parts),
    )


def build_followup_prompt_v2(parsed: dict, previous_sections: dict, question: str) -> str:
    """V2 후속 질문 프롬프트"""
    # 이전 분석 결과를 텍스트로 요약
    summary_parts = []
    for key in sorted(previous_sections.keys()):
        if not key.startswith("section"):
            continue
        sec = previous_sections[key]
        if isinstance(sec, dict):
            title = sec.get("title", key)
            interp = sec.get("interpretation", "")[:500]
            summary_parts.append(f"### {title}\n{interp}")

    return FOLLOWUP_V2_PROMPT.format(
        awr_data=parsed["raw_text"][:15000],
        previous_sections="\n\n".join(summary_parts)[:5000],
        question=question,
    )


# ── LLM 호출 ───────────────────────────────────────────────────

async def analyze_awr_v2(prompt: str, provider: str = None) -> dict:
    """V2 AWR 분석 LLM 호출 → JSON dict 반환"""
    return await call_llm_json(prompt, provider=provider)


async def followup_question_v2(prompt: str, provider: str = None) -> str:
    """V2 후속 질문 LLM 호출"""
    return await call_llm(prompt, provider=provider)
