"""Select AI Agent — DBMS_CLOUD_AI_AGENT (고객사 PoC 확장 Phase 4, 2026-09-30). 정의(툴·에이전트·태스크·팀) · 실행(RUN_TEAM) · 히스토리 뷰.

실측(docs/verified-signatures.md §8): 팀은 `RUN_TEAM(team_name, user_prompt, params => '{"conversation_id": …}')` — conversation_id 없으면 ORA-20053.
SQL 툴은 `{"tool_type":"SQL","tool_params":{"profile_name":…,"action":"runsql"}}`, 태스크는 `{"instruction":…,"tools":[…]}`(`input` 자리표시자는 ORA-20051),
팀은 `{"agents":[{"name":…,"task":…}],"process":"sequential"}`. **OpenAI 호환(Gemini) 프로필로는 마지막 LLM 호출이 HTTP 400
"Requests ending with a model turn are not supported" → provider=google 네이티브 프로필(GEMINI_SH_NATIVE)이 필요하다.**
히스토리: USER_AI_AGENT_TEAM_HISTORY(TEAM_EXEC_ID·STATE·시각·CONVERSATION_ID) · _TASK_HISTORY(단계) · _TOOL_HISTORY(툴 호출 입력/출력 = "Thinking").
"""
from __future__ import annotations

import json
import logging
import time

from app.ai_log import _FEEDBACK_JOIN, _rows
from app.select_ai import _insert_query_log, _lob_to_str, get_profile_attributes

logger = logging.getLogger(__name__)

DEMO = {"team": "DEMO_NL2SQL_TEAM", "agent": "DEMO_NL2SQL_AGENT", "task": "DEMO_NL2SQL_TASK", "tool": "DEMO_SQL_TOOL", "native_profile": "GEMINI_SH_NATIVE"}


def _parse(v):
    if v is None:
        return None
    s = str(v)
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return s


async def _attrs(cur, view: str, name_col: str) -> dict[str, dict]:
    await cur.execute(f"SELECT {name_col}, attribute_name, attribute_value FROM {view} ORDER BY {name_col}, attribute_name")
    out: dict[str, dict] = {}
    for name, k, v in await cur.fetchall():
        out.setdefault(name, {})[k] = _parse(await _lob_to_str(v) if hasattr(v, "read") else v)
    return out


async def list_definitions(pool) -> dict:
    """팀·에이전트·태스크·툴 목록 + 속성(JSON 파싱). Oracle 제공(ORA$…)은 제외."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            teams_a, agents_a, tasks_a, tools_a = (await _attrs(cur, "user_ai_agent_team_attributes", "agent_team_name"), await _attrs(cur, "user_ai_agent_attributes", "agent_name"),
                                                   await _attrs(cur, "user_ai_agent_task_attributes", "task_name"), await _attrs(cur, "user_ai_agent_tool_attributes", "tool_name"))

            async def objs(sql, key):
                await cur.execute(sql)
                return [{"name": r[0], "status": r[1], "description": (await _lob_to_str(r[2])) if hasattr(r[2], "read") else r[2], "created": r[3].isoformat(timespec="seconds") + "Z" if r[3] else None,
                         "attributes": key.get(r[0], {})} for r in await cur.fetchall()]
            teams = await objs("SELECT agent_team_name, status, description, created FROM user_ai_agent_teams WHERE NVL(oracle_maintained,'NO') <> 'YES' ORDER BY 1", teams_a)
            agents = await objs("SELECT agent_name, status, description, created FROM user_ai_agents WHERE NVL(oracle_maintained,'NO') <> 'YES' ORDER BY 1", agents_a)
            tasks = await objs("SELECT task_name, status, description, created FROM user_ai_agent_tasks WHERE NVL(oracle_maintained,'NO') <> 'YES' ORDER BY 1", tasks_a)
            tools = await objs("SELECT tool_name, status, description, created FROM user_ai_agent_tools WHERE NVL(oracle_maintained,'NO') <> 'YES' ORDER BY 1", tools_a)
    return {"teams": teams, "agents": agents, "tasks": tasks, "tools": tools}


def demo_team_plsql(profile: str) -> list[tuple[str, str, dict]]:
    """샘플 팀 4단계 — (라벨, PL/SQL, 바인드). 화면에 그대로 보여주고 같은 것을 실행한다."""
    tool = {"tool_type": "SQL", "tool_params": {"profile_name": profile, "action": "runsql"}, "instruction": "자연어 질문을 SQL 로 바꿔 실행하고 결과를 돌려준다"}
    agent = {"profile_name": profile, "role": "당신은 판매 데이터를 분석하는 데이터 분석가다. SQL 도구로 데이터를 조회해 한국어로 간결히 답한다.", "enable_human_tool": "false"}
    task = {"instruction": "사용자 질문에 SQL 도구를 써서 데이터를 조회하고, 결과를 한국어로 간결하게 요약해 답한다. 조회한 SQL 도 함께 보여준다.", "tools": [DEMO["tool"]]}
    team = {"agents": [{"name": DEMO["agent"], "task": DEMO["task"]}], "process": "sequential"}
    return [
        ("① 툴 (SQL_TOOL)", f"BEGIN DBMS_CLOUD_AI_AGENT.CREATE_TOOL(tool_name => '{DEMO['tool']}', attributes => :a, description => 'NL2SQL 도구'); END;", {"a": json.dumps(tool, ensure_ascii=False)}),
        ("② 에이전트", f"BEGIN DBMS_CLOUD_AI_AGENT.CREATE_AGENT(agent_name => '{DEMO['agent']}', attributes => :a, description => '데이터 분석 에이전트'); END;", {"a": json.dumps(agent, ensure_ascii=False)}),
        ("③ 태스크", f"BEGIN DBMS_CLOUD_AI_AGENT.CREATE_TASK(task_name => '{DEMO['task']}', attributes => :a, description => '질문에 답하기'); END;", {"a": json.dumps(task, ensure_ascii=False)}),
        ("④ 팀", f"BEGIN DBMS_CLOUD_AI_AGENT.CREATE_TEAM(team_name => '{DEMO['team']}', attributes => :a, description => 'NL2SQL 데모 팀'); END;", {"a": json.dumps(team, ensure_ascii=False)}),
    ]


async def ensure_native_profile(pool, base_profile: str) -> tuple[str, bool]:
    """Agent 용 provider=google 프로필. base(openai 호환) 프로필의 크리덴셜·object_list·모델을 복사해 GEMINI_SH_NATIVE 를 만든다(없을 때만). 반환 (이름, 새로 만들었나)."""
    a = await get_profile_attributes(pool, base_profile)
    attrs = {r.get("ATTRIBUTE_NAME"): r.get("ATTRIBUTE_VALUE") for r in (a.get("data") or [])}
    if (attrs.get("provider") or "").lower() == "google":
        return base_profile, False
    name = DEMO["native_profile"]
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM user_cloud_ai_profiles WHERE profile_name = :n", {"n": name})
            if int((await cur.fetchone())[0]):
                return name, False
            obj = _parse(attrs.get("object_list")) or []
            body = {"provider": "google", "credential_name": attrs.get("credential_name"), "model": attrs.get("model") or "gemini-3.8-flash",
                    "object_list": obj, "annotations": True, "comments": True, "conversation": True}
            await cur.execute("BEGIN DBMS_CLOUD_AI.CREATE_PROFILE(profile_name => :n, attributes => :a, description => :d); END;",
                              {"n": name, "a": json.dumps(body, ensure_ascii=False), "d": f"Agent 용 Gemini 네이티브(provider=google) — {base_profile} 의 크리덴셜·테이블 복사. OpenAI 호환 엔드포인트는 Agent 의 마지막 LLM 호출이 HTTP 400"})
    return name, True


async def create_demo_team(pool, base_profile: str) -> dict:
    profile, created = await ensure_native_profile(pool, base_profile)
    steps = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for s in (f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TEAM(team_name => '{DEMO['team']}', force => TRUE); END;", f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TASK(task_name => '{DEMO['task']}', force => TRUE); END;",
                      f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_AGENT(agent_name => '{DEMO['agent']}', force => TRUE); END;", f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TOOL(tool_name => '{DEMO['tool']}', force => TRUE); END;"):
                await cur.execute(s)
            for label, plsql, binds in demo_team_plsql(profile):
                await cur.execute(plsql, binds)
                steps.append({"label": label, "plsql": plsql.replace(":a", "'" + binds["a"].replace("'", "''") + "'")})
    return {"team": DEMO["team"], "profile": profile, "profile_created": created, "steps": steps}


async def drop_demo_team(pool) -> None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            for s in (f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TEAM(team_name => '{DEMO['team']}', force => TRUE); END;", f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TASK(task_name => '{DEMO['task']}', force => TRUE); END;",
                      f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_AGENT(agent_name => '{DEMO['agent']}', force => TRUE); END;", f"BEGIN DBMS_CLOUD_AI_AGENT.DROP_TOOL(tool_name => '{DEMO['tool']}', force => TRUE); END;"):
                await cur.execute(s)


async def _exec_steps(cur, exec_id: str) -> tuple[list[dict], list[dict]]:
    await cur.execute("""SELECT task_order, agent_name, task_name, state, start_date, end_date, input, result FROM user_ai_agent_task_history WHERE team_exec_id = :x ORDER BY task_order""", {"x": exec_id})
    tasks = await _rows(cur)
    await cur.execute("""SELECT invocation_id, task_order, tool_name, agent_name, start_date, end_date, input, output, tool_output FROM user_ai_agent_tool_history WHERE team_exec_id = :x ORDER BY start_date, invocation_id""", {"x": exec_id})
    tools = await _rows(cur)
    for r in tasks + tools:
        try:
            if r.get("START_DATE") and r.get("END_DATE"):
                from datetime import datetime
                a = datetime.fromisoformat(r["START_DATE"].rstrip("Z"))
                b = datetime.fromisoformat(r["END_DATE"].rstrip("Z"))
                r["ELAPSED_MS"] = int((b - a).total_seconds() * 1000)
        except Exception:
            r["ELAPSED_MS"] = None
        for k in ("INPUT", "OUTPUT", "TOOL_OUTPUT"):
            if k in r:
                r[k + "_JSON"] = _parse(r[k])
    return tasks, tools


def _extract_sql(tools: list[dict]) -> str | None:
    for r in reversed(tools):
        o = r.get("OUTPUT_JSON")
        inp = r.get("INPUT_JSON") or {}
        if isinstance(o, dict) and o.get("status") == "success" and str(inp.get("ACTION") or "").upper() == "SHOWSQL":
            return str(o.get("result"))
    return None


async def team_profile(pool, team: str) -> str | None:
    """팀 → 첫 툴의 profile_name (피드백·이력의 프로필)."""
    d = await list_definitions(pool)
    t = next((x for x in d["teams"] if x["name"] == team), None)
    if not t:
        return None
    for ag in (t["attributes"].get("agents") or []):
        task = next((x for x in d["tasks"] if x["name"] == ag.get("task")), None)
        for tool_name in ((task or {}).get("attributes", {}).get("tools") or []):
            tool = next((x for x in d["tools"] if x["name"] == tool_name), None)
            tp = (tool or {}).get("attributes", {}).get("tool_params")
            if isinstance(tp, dict) and tp.get("profile_name"):
                return tp["profile_name"]
        agent = next((x for x in d["agents"] if x["name"] == ag.get("name")), None)
        if agent and agent["attributes"].get("profile_name"):
            return agent["attributes"]["profile_name"]
    return None


async def run_team(pool, team: str, prompt: str, conversation_id: str) -> dict:
    """RUN_TEAM 한 번 → 답 + team_exec_id → 태스크/툴 히스토리(단계 시간·Thinking) → AI_QUERY_LOG(source RUN_TEAM, exec_id)."""
    t0 = time.time()
    profile = await team_profile(pool, team)
    async with pool.acquire() as conn:
        conn.call_timeout = 300000
        async with conn.cursor() as cur:
            import oracledb
            out = cur.var(oracledb.DB_TYPE_CLOB)
            xid = cur.var(str)
            try:
                await cur.execute("BEGIN :r := DBMS_CLOUD_AI_AGENT.RUN_TEAM(team_name => :t, user_prompt => :p, params => :prm, team_exec_id => :x); END;",
                                  {"r": out, "t": team, "p": prompt, "prm": json.dumps({"conversation_id": conversation_id}), "x": xid})
                v = out.getvalue()
                answer = str(await _lob_to_str(v) if hasattr(v, "read") else v or "")
                exec_id = xid.getvalue()
                elapsed = int((time.time() - t0) * 1000)
                tasks, tools = await _exec_steps(cur, exec_id) if exec_id else ([], [])
                sql = _extract_sql(tools)
                log_id = await _insert_query_log(conn, source="RUN_TEAM", profile_name=profile, action="run_team", question=prompt, generated_sql=sql,
                                                 response_text=answer, status="SUCCEEDED", elapsed_ms=elapsed, conversation_id=conversation_id, exec_id=exec_id)
                return {"answer": answer, "team_exec_id": exec_id, "elapsed_ms": elapsed, "tasks": tasks, "tools": tools, "sql": sql, "log_id": log_id, "profile": profile, "conversation_id": conversation_id}
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                msg = str(e)
                # 실패해도 exec id 가 있으면 히스토리에서 단계를 찾는다
                exec_id = None
                try:
                    await cur.execute("SELECT team_exec_id FROM user_ai_agent_team_history WHERE team_name = :t AND conversation_id = :c ORDER BY start_date DESC FETCH FIRST 1 ROWS ONLY", {"t": team, "c": conversation_id})
                    row = await cur.fetchone()
                    exec_id = row[0] if row else None
                except Exception as e2:
                    logger.warning("[agent] exec id 조회 실패: %s", e2)
                tasks, tools = await _exec_steps(cur, exec_id) if exec_id else ([], [])
                log_id = await _insert_query_log(conn, source="RUN_TEAM", profile_name=profile, action="run_team", question=prompt, status="FAILED", error_msg=msg,
                                                 elapsed_ms=elapsed, conversation_id=conversation_id, exec_id=exec_id)
                hint = ""
                if "model turn" in msg:
                    hint = " — 이 팀의 프로필이 OpenAI 호환 엔드포인트입니다. Agent 는 provider=google 네이티브 프로필이 필요합니다(정의 탭 「샘플 팀 만들기」가 만들어 줍니다)"
                elif "ORA-20053" in msg and "Conversation" in msg:
                    hint = " — conversation_id 가 없습니다"
                return {"error": msg + hint, "team_exec_id": exec_id, "elapsed_ms": elapsed, "tasks": tasks, "tools": tools, "log_id": log_id, "profile": profile, "conversation_id": conversation_id}


async def team_history(pool, q: str = "", date_from: str = "", date_to: str = "", team: str = "", state: str = "", page: int = 1, size: int = 20) -> dict:
    conds, binds = [], {}
    if q:
        conds.append("UPPER(DBMS_LOB.SUBSTR(l.question, 4000, 1)) LIKE '%' || UPPER(:q) || '%'")
        binds["q"] = q
    if date_from:
        conds.append("h.start_date >= TO_TIMESTAMP(:date_from, 'YYYY-MM-DD\"T\"HH24:MI')")
        binds["date_from"] = date_from[:16]
    if date_to:
        conds.append("h.start_date < TO_TIMESTAMP(:date_to, 'YYYY-MM-DD\"T\"HH24:MI') + INTERVAL '1' MINUTE")
        binds["date_to"] = date_to[:16]
    if team:
        conds.append("h.team_name = :team")
        binds["team"] = team
    if state:
        conds.append("h.state = :state")
        binds["state"] = state
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    size = max(1, min(int(size), 100))
    page = max(1, int(page))
    base = f"""FROM user_ai_agent_team_history h
LEFT JOIN ai_query_log l ON l.exec_id = h.team_exec_id
{_FEEDBACK_JOIN}{where}"""
    sql = f"""SELECT h.team_exec_id, h.team_name, h.state, h.start_date, h.end_date, h.conversation_id,
       ROUND((CAST(h.end_date AS DATE) - CAST(h.start_date AS DATE)) * 86400000) AS elapsed_ms,
       DBMS_LOB.SUBSTR(l.question, 300, 1) AS question, l.id AS log_id, l.profile_name, fb.feedback_type, fb.feedback_id
{base}
ORDER BY h.start_date DESC
OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT COUNT(*) {base}", binds)
            total = int((await cur.fetchone())[0])
            await cur.execute(sql, {**binds, "off": (page - 1) * size, "lim": size})
            rows = await _rows(cur)
            await cur.execute("SELECT agent_team_name FROM user_ai_agent_teams ORDER BY 1")
            teams = [r[0] for r in await cur.fetchall()]
    shown = sql
    for k, v in binds.items():
        shown = shown.replace(f":{k}", f"'{str(v).replace(chr(39), chr(39) * 2)}'")
    return {"rows": rows, "total": total, "page": page, "size": size, "sql": shown, "teams": teams}


async def exec_detail(pool, exec_id: str) -> dict | None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT team_exec_id, team_name, state, start_date, end_date, conversation_id, params FROM user_ai_agent_team_history WHERE team_exec_id = :x", {"x": exec_id})
            rows = await _rows(cur)
            if not rows:
                return None
            head = rows[0]
            tasks, tools = await _exec_steps(cur, exec_id)
            await cur.execute("SELECT id, profile_name, question, generated_sql, response_text, status, error_msg, elapsed_ms FROM ai_query_log WHERE exec_id = :x ORDER BY id DESC FETCH FIRST 1 ROWS ONLY", {"x": exec_id})
            logs = await _rows(cur)
            feedback = []
            if logs:
                await cur.execute("SELECT id, feedback_type, feedback_content, corrected_sql, source, created_at, updated_at FROM ai_feedback_log WHERE log_id = :id ORDER BY created_at DESC, id DESC", {"id": logs[0]["ID"]})
                feedback = await _rows(cur)
    return {**head, "tasks": tasks, "tools": tools, "log": logs[0] if logs else None, "feedback": feedback}
