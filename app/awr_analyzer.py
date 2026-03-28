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

# 추출 대상 섹션 패턴 (AWR HTML의 <h3> 또는 테이블 캡션 기준)
SECTION_PATTERNS = [
    # Report Summary & Load Profile
    (r"This table displays snap(shot)? information", "snapshot_info"),
    (r"Load Profile", "load_profile"),
    (r"Instance Efficiency", "instance_efficiency"),
    (r"Host CPU", "host_cpu"),
    (r"Instance CPU", "instance_cpu"),
    # Top Events
    (r"Top \d+ Foreground Events", "top_foreground_events"),
    (r"Top 10 Foreground Events", "top_foreground_events"),
    (r"Foreground Wait Class", "foreground_wait_class"),
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
            # AWR 보고서의 데이터 테이블 (summary 속성이 있는 테이블)
            self.in_table = True
            self.current_table = {
                "section": self.current_section,
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


def _table_to_text(table: dict, max_rows: int = 15) -> str:
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


def parse_awr_html(html_content: str) -> dict:
    """
    AWR HTML을 파싱하여 핵심 섹션을 추출한다.
    Returns: {
        "sections": { category: [table_text, ...] },
        "raw_text": "전체 추출 텍스트",
        "is_exadata": bool,
        "section_count": int
    }
    """
    parser = AWRTableExtractor()
    parser.feed(html_content)

    sections = {}
    all_text_parts = []
    is_exadata = False

    for table in parser.tables:
        section_name = table.get("section", "")
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
        if category in ("exadata", "cell_server", "cell_physical_io", "smart_scan", "offload"):
            is_exadata = True

    # HTML 본문에서 Exadata 키워드 추가 감지
    if not is_exadata and re.search(r"exadata|cell server|smart scan|offload", html_content, re.IGNORECASE):
        is_exadata = True

    raw_text = "\n\n".join(all_text_parts)

    return {
        "sections": sections,
        "raw_text": raw_text,
        "is_exadata": is_exadata,
        "section_count": len(sections),
        "total_tables": len(all_text_parts),
    }


# ── LLM 프롬프트 생성 ──────────────────────────────────────────

AWR_ANALYSIS_PROMPT = """당신은 Oracle Database 성능 전문가입니다. 아래의 AWR(Automatic Workload Repository) 리포트 데이터를 분석하여, 반드시 아래 JSON 형식으로만 응답하세요. JSON 외의 텍스트는 절대 포함하지 마세요.

## AWR 데이터
{awr_data}

## Exadata 환경 여부
{exadata_info}

## 응답 JSON 형식
다음 JSON 구조를 정확히 따르세요. 모든 해석과 설명은 한국어로 작성하되, Oracle 기술 용어(Wait Event 이름, 파라미터명 등)는 영문 그대로 유지하세요.

```json
{{
  "summary": "전반적인 DB 상태 종합 소견 (2~3문단, 핵심 병목과 전체적인 건강 상태를 포함)",
  "overallScore": 75,
  "snapshotInfo": {{
    "dbName": "DB명",
    "instanceName": "인스턴스명",
    "startTime": "시작 시간",
    "endTime": "종료 시간",
    "elapsed": "경과 시간",
    "dbTime": "DB Time",
    "isExadata": false
  }},
  "findings": [
    {{
      "severity": "critical | warning | info",
      "category": "Wait Events | CPU | Memory | I/O | SQL | Exadata",
      "title": "발견사항 제목",
      "detail": "상세 설명",
      "recommendation": "구체적 개선 권고"
    }}
  ],
  "waitEvents": [
    {{
      "event": "이벤트명",
      "waits": 0,
      "totalTime": "총 대기 시간",
      "avgWait": "평균 대기 시간",
      "pctDbTime": 0.0,
      "interpretation": "해석"
    }}
  ],
  "loadProfile": {{
    "dbTimePerSec": 0.0,
    "logicalReadsPerSec": 0,
    "physicalReadsPerSec": 0,
    "redoPerSec": "0 MB",
    "parsesPerSec": 0,
    "hardParsesPerSec": 0,
    "interpretation": "부하 프로필 종합 해석"
  }},
  "instanceEfficiency": {{
    "bufferHitPct": 0.0,
    "libraryCacheHitPct": 0.0,
    "softParsePct": 0.0,
    "interpretation": "효율성 지표 해석"
  }},
  "memoryAdvisory": {{
    "sgaCurrent": "현재 SGA 크기",
    "sgaRecommended": "권장 SGA 크기",
    "pgaCurrent": "현재 PGA 크기",
    "pgaRecommended": "권장 PGA 크기",
    "interpretation": "메모리 설정 해석 및 권고"
  }},
  "ioAnalysis": {{
    "topTablespaces": [
      {{ "name": "이름", "reads": 0, "writes": 0, "avgReadTime": "0ms" }}
    ],
    "interpretation": "I/O 패턴 해석"
  }},
  "topSegments": [
    {{ "segment": "OWNER.NAME", "type": "TABLE|INDEX", "logicalReads": 0, "physicalReads": 0 }}
  ],
  "exadata": {{
    "cellOffloadPct": 0.0,
    "smartScanPct": 0.0,
    "flashCacheHitPct": 0.0,
    "interpretation": "Exadata 성능 해석"
  }},
  "actionItems": [
    {{
      "priority": 1,
      "action": "구체적 조치 사항",
      "expectedImpact": "기대 효과",
      "category": "Wait Events | CPU | Memory | I/O | SQL | Exadata"
    }}
  ]
}}
```

## 분석 지침
1. overallScore는 0~100 사이 정수로, DB 전반적 건강도를 나타냅니다 (100=최상)
2. findings는 severity 기준 critical → warning → info 순으로 정렬하세요
3. 데이터가 부족한 섹션은 해당 필드를 합리적 기본값으로 채우고 interpretation에 "데이터 부족"을 명시하세요
4. Exadata 환경이 아니면 exadata 필드는 null로 설정하세요
5. actionItems는 priority 1이 가장 시급한 항목이며, 최대 7개까지만 포함하세요
6. topSegments는 상위 5개까지만 포함하세요
7. waitEvents는 상위 5~7개까지만 포함하세요"""


FOLLOWUP_PROMPT = """당신은 Oracle Database 성능 전문가입니다. 이전에 분석한 AWR 리포트에 대해 사용자가 후속 질문을 합니다.

## 이전 AWR 데이터
{awr_data}

## 이전 분석 결과 요약
{previous_summary}

## 사용자 질문
{question}

한국어로 답변하되, Oracle 기술 용어는 영문 그대로 유지하세요. 가능한 한 구체적이고 실행 가능한 조언을 제공하세요."""


def build_analysis_prompt(parsed_awr: dict) -> str:
    """파싱된 AWR 데이터로 LLM 분석 프롬프트를 생성"""
    exadata_info = "이 시스템은 Exadata 환경입니다. Exadata 관련 지표도 분석해 주세요." if parsed_awr["is_exadata"] else "Exadata 환경이 아닙니다."

    return AWR_ANALYSIS_PROMPT.format(
        awr_data=parsed_awr["raw_text"][:12000],  # Groq API 크기 제한 대응
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
