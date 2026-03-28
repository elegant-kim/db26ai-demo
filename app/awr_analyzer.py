"""
AWR HTML Report Analyzer
- AWR HTML 파일을 파싱하여 핵심 섹션 추출
- 외부 LLM API(Groq/Gemini)를 통해 구조화된 JSON 분석 결과 생성
- 후속 질문 지원
"""

import re
from html.parser import HTMLParser

from app.llm_client import call_llm, call_llm_json


# ── AWR HTML 파싱 ──────────────────────────────────────────────

# AWR 헤더 테이블 패턴 (summary 속성, 캡션, 또는 셀 내용 기준)
HEADER_PATTERNS = [
    (r"database instance information", "db_info"),
    (r"host information", "host_info"),
    (r"snap(shot)? information", "snapshot_info"),
    (r"snap(shot)? set", "snapshot_info"),
    (r"Begin Snap|End Snap|Elapsed|DB Time", "snapshot_info"),
    # AWR 헤더에 있는 DB 정보 테이블 (헤더: DB Name, DB Id 등)
    (r"DB Name.*DB Id|DB Id.*DB Name", "db_info"),
    (r"Instance.*Inst Num|Inst Num.*Instance", "instance_info"),
    (r"Host Name.*Platform|Platform.*Host Name", "host_info"),
    (r"Release.*RAC|RAC.*Release|Edition.*Release", "db_info"),
]

# 추출 대상 섹션 패턴 (AWR HTML의 <h3> 또는 테이블 캡션 기준)
SECTION_PATTERNS = [
    # Report Summary & Load Profile
    (r"Load Profile", "load_profile"),
    (r"Instance Efficiency", "instance_efficiency"),
    (r"Host CPU", "host_cpu"),
    (r"Instance CPU", "instance_cpu"),
    # Time Model (DB Time 분석의 핵심)
    (r"Time Model", "time_model"),
    (r"Operating System Statistics", "os_stats"),
    # Top Events
    (r"Top \d+ Foreground Events", "top_foreground_events"),
    (r"Top 10 Foreground Events", "top_foreground_events"),
    (r"Top Timed Events", "top_foreground_events"),
    (r"Foreground Wait Class", "foreground_wait_class"),
    (r"Wait Classes by Total Wait Time", "foreground_wait_class"),
    (r"Wait Event Histogram", "wait_event_histogram"),
    # SQL Statistics (수치만, SQL Text 제외)
    (r"SQL ordered by Elapsed Time", "sql_by_elapsed"),
    (r"SQL ordered by CPU Time", "sql_by_cpu"),
    (r"SQL ordered by Gets", "sql_by_gets"),
    (r"SQL ordered by Reads", "sql_by_reads"),
    (r"SQL ordered by Executions", "sql_by_executions"),
    # I/O
    (r"Tablespace IO Stats", "tablespace_io"),
    (r"File IO Stats", "file_io"),
    (r"IOStat by Function", "io_by_function"),
    # Memory
    (r"SGA Target Advisory", "sga_advisory"),
    (r"SGA Memory Summary", "sga_summary"),
    (r"PGA Target Advisory", "pga_advisory"),
    (r"PGA Memory Summary", "pga_summary"),
    # Segments
    (r"Segments by Logical Reads", "segments_logical_reads"),
    (r"Segments by Physical Reads", "segments_physical_reads"),
    # Exadata
    (r"Exadata", "exadata"),
    (r"Cell Server", "cell_server"),
    (r"Cell Physical IO", "cell_physical_io"),
    (r"Smart (Scan|Flash)", "smart_scan"),
    (r"Offload", "offload"),
    (r"cell physical IO interconnect", "cell_interconnect"),
]

# 제외 대상 섹션 (SQL Text, Plan 등)
EXCLUDE_PATTERNS = [
    r"Complete List of SQL Text",
    r"SQL Text",
    r"Execution Plan",
]


class AWRTableExtractor(HTMLParser):
    """AWR HTML에서 테이블 데이터를 추출하는 파서"""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = None
        self.current_row = []
        self.current_cell = ""
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_header = False
        self.current_headers = []
        self.section_titles = []
        self.current_section = ""
        self.capture_text = False
        self.text_buffer = ""
        self.in_h2 = False
        self.in_h3 = False
        self.in_caption = False
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.tag_stack.append(tag)

        if tag == "h2":
            self.in_h2 = True
            self.text_buffer = ""
        elif tag == "h3":
            self.in_h3 = True
            self.text_buffer = ""
        elif tag == "caption":
            self.in_caption = True
            self.text_buffer = ""
        elif tag == "table":
            attrs_dict = dict(attrs)
            # summary 속성이 있으면 섹션명으로 활용 (AWR 헤더 테이블 식별에 유용)
            summary = attrs_dict.get("summary", "")
            table_section = summary if summary else self.current_section
            self.in_table = True
            self.current_table = {
                "section": table_section,
                "headers": [],
                "rows": [],
            }
            self.current_headers = []
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
            self.in_header = False
        elif tag in ("th", "td") and self.in_row:
            self.in_cell = True
            self.in_header = tag == "th"
            self.current_cell = ""

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        if tag == "h2" and self.in_h2:
            self.in_h2 = False
            self.current_section = self.text_buffer.strip()
            self.section_titles.append(self.current_section)
        elif tag == "h3" and self.in_h3:
            self.in_h3 = False
            title = self.text_buffer.strip()
            if title:
                self.current_section = title
                self.section_titles.append(title)
        elif tag == "caption" and self.in_caption:
            self.in_caption = False
            title = self.text_buffer.strip()
            if title:
                self.current_section = title
        elif tag == "table" and self.in_table:
            self.in_table = False
            if self.current_table and (self.current_table["headers"] or self.current_table["rows"]):
                self.current_table["headers"] = self.current_headers
                self.tables.append(self.current_table)
            self.current_table = None
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.current_row and self.current_table:
                if not self.current_headers and all(self.in_header for _ in []):
                    pass
                self.current_table["rows"].append(self.current_row)
        elif tag in ("th", "td") and self.in_cell:
            self.in_cell = False
            cell_text = self.current_cell.strip()
            cell_text = re.sub(r"\s+", " ", cell_text)
            if self.in_header and self.current_table:
                self.current_headers.append(cell_text)
            self.current_row.append(cell_text)

    def handle_data(self, data):
        if self.in_h2 or self.in_h3 or self.in_caption:
            self.text_buffer += data
        if self.in_cell:
            self.current_cell += data


def _should_include_section(section_name: str) -> bool:
    """이 섹션을 포함해야 하는지 판단"""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, section_name, re.IGNORECASE):
            return False
    for pattern, _ in SECTION_PATTERNS:
        if re.search(pattern, section_name, re.IGNORECASE):
            return True
    return False


def _classify_section(section_name: str) -> str:
    """섹션 이름을 카테고리로 분류"""
    for pattern, category in SECTION_PATTERNS:
        if re.search(pattern, section_name, re.IGNORECASE):
            return category
    return "other"


def _table_to_text(table: dict, max_rows: int = 25) -> str:
    """테이블 데이터를 텍스트로 변환 (LLM 전송용)"""
    lines = []
    section = table.get("section", "")
    if section:
        lines.append(f"[{section}]")

    headers = table.get("headers", [])
    rows = table.get("rows", [])

    # SQL 텍스트가 포함된 행 제거 (SQL_ID + 긴 텍스트 패턴)
    filtered_rows = []
    for row in rows:
        # SQL 텍스트 행 건너뛰기 (한 셀이 200자 이상이면 SQL 텍스트로 간주)
        if any(len(cell) > 200 for cell in row):
            continue
        filtered_rows.append(row)

    rows = filtered_rows[:max_rows]

    if headers:
        lines.append(" | ".join(headers))
        lines.append("-" * 40)

    for row in rows:
        lines.append(" | ".join(row))

    return "\n".join(lines)


def _is_header_table(table: dict) -> str:
    """AWR 헤더 테이블(DB 정보, 호스트 정보, 스냅샷 정보)인지 판별"""
    section = table.get("section", "")
    all_text = section + " " + " ".join(table.get("headers", []))
    # rows의 첫 번째 셀들도 검사 (AWR 헤더는 캡션 없이 테이블만 있는 경우도 있음)
    for row in table.get("rows", [])[:3]:
        all_text += " " + " ".join(row)
    for pattern, category in HEADER_PATTERNS:
        if re.search(pattern, all_text, re.IGNORECASE):
            return category
    return ""


def parse_awr_html(html_content: str) -> dict:
    """
    AWR HTML을 파싱하여 핵심 섹션을 추출한다.
    Returns: {
        "header_info": "DB/호스트/스냅샷 정보 텍스트",
        "sections": { category: [table_text, ...] },
        "raw_text": "전체 추출 텍스트 (header_info 포함)",
        "is_exadata": bool,
        "section_count": int
    }
    """
    parser = AWRTableExtractor()
    parser.feed(html_content)

    header_parts = []
    sections = {}
    all_text_parts = []
    is_exadata = False

    for table in parser.tables:
        section_name = table.get("section", "")

        # 1) 헤더 테이블 (DB 정보, 스냅샷 정보) — 항상 포함
        header_cat = _is_header_table(table)
        if header_cat:
            text = _table_to_text(table, max_rows=20)
            if text.strip():
                header_parts.append(text)
            continue

        # 2) 일반 섹션 — 패턴 매칭
        if not _should_include_section(section_name):
            continue

        category = _classify_section(section_name)
        text = _table_to_text(table)

        if not text.strip():
            continue

        if category not in sections:
            sections[category] = []
        sections[category].append(text)
        all_text_parts.append(text)

        # Exadata 감지
        if category in ("exadata", "cell_server", "cell_physical_io", "smart_scan", "offload", "cell_interconnect"):
            is_exadata = True

    # HTML 본문에서 Exadata 키워드 추가 감지
    if not is_exadata and re.search(r"exadata|cell server|smart scan|offload", html_content, re.IGNORECASE):
        is_exadata = True

    header_info = "\n\n".join(header_parts)
    raw_text = header_info + "\n\n" + "\n\n".join(all_text_parts) if header_info else "\n\n".join(all_text_parts)

    return {
        "header_info": header_info,
        "sections": sections,
        "raw_text": raw_text,
        "is_exadata": is_exadata,
        "section_count": len(sections),
        "total_tables": len(all_text_parts),
    }


# ── LLM 프롬프트 생성 ──────────────────────────────────────────

AWR_ANALYSIS_PROMPT = """당신은 20년 경력의 Oracle Database 성능 튜닝 전문가(Oracle ACE)입니다.
아래 AWR 리포트 데이터를 **Top-Down 방법론**에 따라 체계적으로 분석하세요.

## Top-Down 분석 방법론
반드시 다음 순서로 분석하세요:
1단계) DB Time 분석 → DB가 실제로 얼마나 바쁜지, CPU vs Wait 비율 판단
2단계) Top Timed Events → 가장 많은 시간을 소비하는 대기 이벤트가 무엇인지 (이것이 핵심 병목)
3단계) Load Profile → 워크로드 특성 파악 (OLTP/DWH/Mixed, 트랜잭션 패턴)
4단계) Instance Efficiency → 메모리(캐시) 효율성
5단계) I/O 분석 → 테이블스페이스/파일별 I/O 분포
6단계) Memory Advisory → SGA/PGA 적정 크기
7단계) (Exadata인 경우) Smart Scan / Cell Offload 효율

## 중요 분석 원칙
- severity 판단은 **전체 DB Time 대비 비중**으로 결정하세요. 개별 지표의 절대값이 아니라, 전체 성능에 미치는 영향도가 기준입니다.
- Wait Event 분석 시 **Total Wait Time이 높아도 Avg Wait가 낮으면** 건수가 많을 뿐 심각하지 않을 수 있습니다. 반대로 건수가 적어도 Avg Wait가 극단적으로 높으면 문제입니다.
- critical은 DB Time의 30% 이상을 차지하는 명백한 병목에만 부여하세요.
- DB CPU가 Top 1 이벤트이고 %Idle CPU가 충분하면, 이는 건강한 상태입니다 (CPU bound ≠ 항상 나쁨).

## AWR 데이터
{awr_data}

## Exadata 환경 여부
{exadata_info}

## 응답 JSON 형식
반드시 아래 JSON 구조만 출력하세요. JSON 외의 텍스트는 절대 포함하지 마세요.
모든 해석/설명은 한국어로 작성하되, Oracle 기술 용어(Wait Event 이름, 파라미터명 등)는 영문 그대로 유지하세요.

```json
{{
  "snapshotInfo": {{
    "dbName": "AWR 데이터에서 추출한 DB Name (예: HNC)",
    "instanceName": "인스턴스명 (예: HNC1)",
    "hostName": "호스트명",
    "platform": "플랫폼 (예: AIX-Based Systems (64-bit))",
    "cpus": "CPU 수",
    "memory": "메모리 크기",
    "startTime": "Begin Snap 시간",
    "endTime": "End Snap 시간",
    "elapsed": "Elapsed 시간",
    "dbTime": "DB Time 값",
    "isExadata": false,
    "isRAC": false,
    "dbVersion": "DB 버전"
  }},
  "dbTimeAnalysis": {{
    "dbTimeSec": 0,
    "elapsedSec": 0,
    "avgActiveSessions": 0.0,
    "cpuTimePct": 0.0,
    "waitTimePct": 0.0,
    "interpretation": "DB Time 분석: Elapsed 대비 DB Time 비율, Average Active Sessions 의미, CPU vs Wait 비율이 의미하는 바를 상세히 설명 (3문장 이상)"
  }},
  "categoryScores": {{
    "dbTime": {{ "score": 80, "label": "DB Time 효율", "detail": "점수 근거를 수치와 함께 설명" }},
    "waitEvents": {{ "score": 70, "label": "Wait Events", "detail": "Top Event의 DB Time 비중과 심각도 근거" }},
    "cpuUsage": {{ "score": 85, "label": "CPU 사용", "detail": "Host CPU %Idle, Instance CPU % 근거" }},
    "instanceEfficiency": {{ "score": 90, "label": "인스턴스 효율", "detail": "Buffer Hit, Library Cache Hit, Soft Parse % 근거" }},
    "ioPerformance": {{ "score": 75, "label": "I/O 성능", "detail": "Physical Reads, Avg Read Time 근거" }},
    "memoryUsage": {{ "score": 80, "label": "메모리", "detail": "SGA/PGA Advisory 기반 근거" }}
  }},
  "summary": "종합 소견 (최소 4문단): 1)DB 환경/워크로드 특성 2)DB Time 기준 핵심 병목 3)카테고리별 상태 요약 4)종합적 개선 방향",
  "findings": [
    {{
      "severity": "critical | warning | info",
      "category": "DB Time | Wait Events | CPU | Memory | I/O | SQL | Exadata",
      "title": "발견사항 제목",
      "detail": "반드시 AWR 수치를 인용하며 상세 설명 (예: 'db file sequential read가 DB Time의 45.2%를 차지')",
      "recommendation": "구체적 개선 조치 (파라미터, SQL 힌트, 구조 변경 등 실행 가능한 수준)"
    }}
  ],
  "waitEvents": [
    {{
      "event": "이벤트명",
      "waitClass": "Wait Class (User I/O, System I/O, Concurrency 등)",
      "waits": 0,
      "totalTime": "총 대기 시간",
      "avgWait": "평균 대기 시간",
      "pctDbTime": 0.0,
      "interpretation": "이 이벤트가 의미하는 바와 영향도"
    }}
  ],
  "loadProfile": {{
    "dbTimePerSec": 0.0,
    "dbCpuPerSec": 0.0,
    "logicalReadsPerSec": 0,
    "physicalReadsPerSec": 0,
    "physicalWritesPerSec": 0,
    "redoPerSec": "0 MB",
    "parsesPerSec": 0,
    "hardParsesPerSec": 0,
    "executionsPerSec": 0,
    "transactionsPerSec": 0,
    "interpretation": "워크로드 특성 해석: OLTP/DWH/Mixed 판단, Hard Parse 비율, Per Sec vs Per Txn 비교 분석"
  }},
  "instanceEfficiency": {{
    "bufferHitPct": 0.0,
    "libraryCacheHitPct": 0.0,
    "softParsePct": 0.0,
    "executeToParseRatio": 0.0,
    "latchHitPct": 0.0,
    "interpretation": "각 지표별 권장 기준 대비 현재 상태 평가"
  }},
  "memoryAdvisory": {{
    "sgaCurrent": "현재 SGA 크기",
    "sgaRecommended": "Advisory 기반 권장 크기",
    "pgaCurrent": "현재 PGA 크기",
    "pgaRecommended": "Advisory 기반 권장 크기",
    "interpretation": "Advisory 데이터 기반 구체적 조정 권고"
  }},
  "ioAnalysis": {{
    "topTablespaces": [
      {{ "name": "이름", "reads": 0, "writes": 0, "avgReadTime": "0ms" }}
    ],
    "interpretation": "I/O 패턴 해석: Hot 테이블스페이스, 읽기/쓰기 비율"
  }},
  "topSegments": [
    {{ "segment": "OWNER.NAME", "type": "TABLE|INDEX", "logicalReads": 0, "physicalReads": 0 }}
  ],
  "exadata": {{
    "cellOffloadPct": 0.0,
    "smartScanPct": 0.0,
    "flashCacheHitPct": 0.0,
    "cellInterconnectBytes": "0",
    "eligibleOffloadBytes": "0",
    "interpretation": "Exadata 오프로딩 효율 분석: Smart Scan이 전체 I/O에서 차지하는 비중, Cell Offload 효과, Flash Cache 활용도를 평가. 오프로딩 효율이 낮다면 원인(인덱스 스캔 위주, passthrough, 비지원 데이터 타입 등)을 추정"
  }},
  "actionItems": [
    {{
      "priority": 1,
      "action": "구체적 조치 사항 (실행 가능한 수준: 파라미터 변경, SQL 튜닝, 구조 변경 등)",
      "expectedImpact": "기대 효과 (가능하면 수치로, 예: 'DB Time 20% 감소 예상')",
      "category": "DB Time | Wait Events | CPU | Memory | I/O | SQL | Exadata"
    }}
  ]
}}
```

## 점수 산정 기준 (각 카테고리 0~100)
- **DB Time 효율**: DB Time / Elapsed 비율, Average Active Sessions 기반. AAS < CPU cores이면 양호
- **Wait Events**: Top 1 이벤트가 DB CPU이면 높은 점수. Concurrency wait class 비중이 크면 감점
- **CPU 사용**: Host %Idle 50% 이상이면 양호, 10% 미만이면 위험
- **인스턴스 효율**: Buffer Hit > 95%, Library Cache Hit > 99%, Soft Parse > 95%이면 양호
- **I/O 성능**: Avg Single Block Read < 10ms이면 양호, > 20ms이면 주의
- **메모리**: SGA/PGA Advisory에서 현재 크기 대비 Size Factor 1.0의 Physical Reads가 크게 감소하지 않으면 양호

## 추가 지침
- snapshotInfo의 각 필드는 AWR 데이터 상단의 DB 정보/스냅샷 테이블에서 정확히 추출하세요
- findings는 최대 12개, severity는 전체 DB Time 영향도 기준으로 판단
- waitEvents는 상위 10개까지
- topSegments는 상위 7개까지
- actionItems는 priority 순으로 최대 10개
- Exadata 환경이 아니면 exadata 필드는 null"""


FOLLOWUP_PROMPT = """당신은 Oracle Database 성능 전문가입니다. 이전에 분석한 AWR 리포트에 대해 사용자가 후속 질문을 합니다.

## 이전 AWR 데이터
{awr_data}

## 이전 분석 결과 요약
{previous_summary}

## 사용자 질문
{question}

한국어로 답변하되, Oracle 기술 용어는 영문 그대로 유지하세요. 가능한 한 구체적이고 실행 가능한 조언을 제공하세요."""


def build_analysis_prompt(parsed_awr: dict, max_input_chars: int = 12000) -> str:
    """파싱된 AWR 데이터로 LLM 분석 프롬프트를 생성"""
    exadata_info = "이 시스템은 Exadata 환경입니다. Exadata 관련 지표도 분석해 주세요." if parsed_awr["is_exadata"] else "Exadata 환경이 아닙니다."

    return AWR_ANALYSIS_PROMPT.format(
        awr_data=parsed_awr["raw_text"][:max_input_chars],
        exadata_info=exadata_info,
    )


def build_followup_prompt(parsed_awr: dict, previous_summary: str, question: str) -> str:
    """후속 질문 프롬프트를 생성"""
    return FOLLOWUP_PROMPT.format(
        awr_data=parsed_awr["raw_text"][:15000],
        previous_summary=previous_summary[:3000],
        question=question,
    )


# ── LLM 호출 (외부 API: Groq / Gemini) ────────────────────────

async def analyze_awr_with_llm(prompt: str, provider: str = None) -> dict:
    """
    외부 LLM API를 사용하여 AWR 분석 실행.
    Returns: 파싱된 JSON dict 또는 에러 정보
    """
    return await call_llm_json(prompt, provider=provider)


async def followup_question(prompt: str, provider: str = None) -> str:
    """후속 질문에 대한 LLM 응답 (자유 형식 텍스트)"""
    return await call_llm(prompt, provider=provider)
