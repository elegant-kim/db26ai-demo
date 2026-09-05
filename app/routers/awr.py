"""AWR 분석 라우터 — /api/awr/* (계획서 5-4 에서 routes.py 에서 분리, 2026-09-05).

경로·응답은 routes.py 에 있던 그대로다. 분석 본체는 app/awr_analyzer_v2.py.
주의: /analyze 는 SSE 가 아니라 **분석이 끝난 뒤 JSON 한 번**을 돌려준다(30~120초). 화면의 진행 표시는 타이머 연출이다.
"""
import time

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.awr_analyzer_v2 import (
    analyze_awr_v2,
    build_analysis_prompt_v2,
    build_followup_prompt_v2,
    followup_question_v2,
    parse_awr_html_v2,
)

router = APIRouter(prefix="/api/awr", tags=["awr"])

MAX_AWR_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB
MAX_FOLLOWUP_CHARS = 40_000  # 후속 답변 상한 — 정상 답변은 2~6천 자


_awr_cache: dict = {}


class AWRFollowupRequest(BaseModel):
    question: str
    session_id: str = "default"
    provider: str = ""


@router.post("/analyze")
async def awr_analyze_v2(file: UploadFile = File(...), provider: str = Form("")):
    """AWR HTML 파일 업로드 → 파싱 (23개 섹션) → LLM 분석 (8개 섹션 보고서)"""
    if not file.filename.lower().endswith((".html", ".htm")):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "HTML 파일만 업로드 가능합니다."},
        )

    content = await file.read()
    if len(content) > MAX_AWR_UPLOAD_SIZE:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "파일 크기가 20MB를 초과합니다."},
        )

    start = time.time()
    try:
        # 1) HTML 파싱
        html_text = content.decode("utf-8", errors="replace")
        parsed = parse_awr_html_v2(html_text)

        if parsed["section_count"] == 0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "AWR 리포트에서 분석 가능한 섹션을 찾지 못했습니다. 유효한 AWR HTML 파일인지 확인해 주세요."},
            )

        parse_ms = int((time.time() - start) * 1000)

        # 2) LLM 분석 프롬프트 생성 및 호출
        from app.llm_client import get_max_input_chars
        llm_provider = provider or None
        max_chars = get_max_input_chars(llm_provider)
        prompt = build_analysis_prompt_v2(parsed, max_input_chars=max_chars)
        llm_result = await analyze_awr_v2(prompt, provider=llm_provider)
        total_ms = int((time.time() - start) * 1000)

        # JSON 파싱 실패 감지
        if "parse_error" in llm_result:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "LLM 응답의 JSON 파싱에 실패했습니다. 다시 시도해 주세요.",
                    "raw_response": llm_result.get("raw_response", "")[:500],
                    "elapsed_ms": total_ms,
                },
            )

        # 캐싱
        session_id = f"awr_{int(time.time())}"
        _awr_cache[session_id] = {
            "parsed": parsed,
            "sections": llm_result,
            "provider": provider,
            "html": html_text,
        }

        return {
            "success": True,
            "session_id": session_id,
            "analysis": llm_result,
            "parse_info": {
                "section_count": parsed["section_count"],
                "is_rac": parsed["is_rac"],
                "is_exadata": parsed["is_exadata"],
                "parse_ms": parse_ms,
                "extracted_sections": list(parsed["sections"].keys()),
                "raw_text_length": len(parsed["raw_text"]),
                "max_input_chars": max_chars,
            },
            "elapsed_ms": total_ms,
            "filename": file.filename,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.post("/followup")
async def awr_followup(req: AWRFollowupRequest):
    """AWR 분석 결과에 대한 후속 질문"""
    cached = _awr_cache.get(req.session_id)
    if not cached:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "이전 AWR 분석 세션을 찾을 수 없습니다. 파일을 다시 업로드해 주세요."},
        )

    start = time.time()
    try:
        prompt = build_followup_prompt_v2(
            cached["parsed"],
            cached["sections"],
            req.question,
        )
        llm_provider = req.provider or cached.get("provider") or None
        answer = await followup_question_v2(prompt, provider=llm_provider)
        elapsed_ms = int((time.time() - start) * 1000)

        # 2026-09-05 실측: 918,828자짜리 답변이 와서 화면이 굳었다(마크다운 렌더). LLM 이상 출력 방어 — 상한 + 안내.
        if len(answer) > MAX_FOLLOWUP_CHARS:
            answer = answer[:MAX_FOLLOWUP_CHARS] + f"\n\n> ⚠ 답변이 비정상적으로 길어({len(answer):,}자) 앞 {MAX_FOLLOWUP_CHARS:,}자만 표시합니다. 질문을 좁혀 다시 물어보세요."
        return {
            "success": True,
            "answer": answer,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "elapsed_ms": elapsed_ms},
        )


@router.get("/source/{session_id}")
async def awr_source_html_v2(session_id: str, section: str = ""):
    """AWR HTML 원문 보기"""
    cached = _awr_cache.get(session_id)
    if not cached or "html" not in cached:
        return HTMLResponse(
            "<h2>AWR 원문을 찾을 수 없습니다. 파일을 다시 업로드해 주세요.</h2>",
            status_code=404,
        )

    html = cached["html"]

    if "<meta" not in html[:500].lower() or "charset" not in html[:500].lower():
        html = '<meta charset="UTF-8">\n' + html

    if section:
        section_lower = section.lower()
        anchor_id = "awr_highlight_target"
        highlight_css = (
            '<style>#awr_highlight_target { '
            'outline: 3px solid #f59e0b !important; '
            'outline-offset: 4px !important; '
            'background-color: #fff3cd !important; '
            '}</style>'
        )

        search_pos = html.lower().find(section_lower)
        if search_pos >= 0:
            anchor_tag = f'<a id="{anchor_id}"></a>'
            html = html[:search_pos] + anchor_tag + html[search_pos:]

            scroll_script = f"""
{highlight_css}
<script>
document.addEventListener('DOMContentLoaded', function() {{
    var el = document.getElementById('{anchor_id}');
    if (el) {{
        var target = el.nextElementSibling || el.parentElement;
        if (target && target.tagName === 'TABLE') {{
            target.id = '{anchor_id}';
            el.remove();
        }} else {{
            var parent = el.parentElement;
            while (parent && parent.tagName !== 'TABLE' && parent.tagName !== 'BODY') {{
                parent = parent.parentElement;
            }}
            if (parent && parent.tagName === 'TABLE') {{
                parent.id = '{anchor_id}';
                el.remove();
            }}
        }}
        var highlighted = document.getElementById('{anchor_id}');
        if (highlighted) {{
            setTimeout(function() {{ highlighted.scrollIntoView({{ behavior: 'smooth', block: 'start' }}); }}, 300);
        }}
    }}
}});
</script>
"""
            if "</body>" in html.lower():
                idx = html.lower().rfind("</body>")
                html = html[:idx] + scroll_script + html[idx:]
            else:
                html += scroll_script

    return HTMLResponse(html, media_type="text/html; charset=utf-8")
