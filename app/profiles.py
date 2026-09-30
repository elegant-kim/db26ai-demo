"""프로필 생성 도우미 + 프로바이더 메타 (PoC 3-A, 2026-09-30) — 「환경」 탭 「새 프로필 만들기」.

DBMS_CLOUD_AI.CREATE_PROFILE(profile_name, attributes JSON, status, description). 속성 키는 패키지 상수(ATTR_*)에서 실측
(docs/verified-signatures.md): provider · credential_name · model · provider_endpoint · object_list · annotations · comments · constraints ·
conversation · embedding_model · region · oci_compartment_id · oci_endpoint_id · oci_apiformat · oci_runtimetype · azure_resource_name …
OCI Generative AI 는 provider_endpoint 대신 region 으로 호스트가 정해진다: inference.generativeai.<region>.oci.oraclecloud.com.
"""
from __future__ import annotations

import json
import re

from app.select_ai import _lob_to_str

# 패키지 PROVIDER_* 상수 (2026-09-30 실측). 벡터 DB 프로바이더(qdrant 등)는 여기 아님
PROVIDERS = [
    {"id": "openai", "label": "OpenAI 호환 (OpenAI · Gemini · Groq …)", "endpoint": True, "hint": "provider_endpoint 에 호환 엔드포인트, 크리덴셜은 API 키(bearer)"},
    {"id": "oci", "label": "OCI Generative AI", "endpoint": False, "hint": "region 필수. 크리덴셜은 OCI API Key(user_ocid·tenancy_ocid·fingerprint·private_key) 또는 Resource Principal"},
    {"id": "google", "label": "Google (Gemini 네이티브)", "endpoint": False, "hint": "크리덴셜은 Google API 키"},
    {"id": "anthropic", "label": "Anthropic", "endpoint": False, "hint": "크리덴셜은 Anthropic API 키"},
    {"id": "cohere", "label": "Cohere", "endpoint": False, "hint": ""},
    {"id": "azure", "label": "Azure OpenAI", "endpoint": False, "hint": "azure_resource_name · azure_deployment_name 필요"},
    {"id": "aws", "label": "AWS Bedrock", "endpoint": False, "hint": "region · aws_apiformat"},
    {"id": "huggingface", "label": "Hugging Face", "endpoint": True, "hint": ""},
    {"id": "vertexai", "label": "Google Vertex AI", "endpoint": False, "hint": "vertexai_project_id"},
]

# OCI Generative AI 제공 리전 (2026-09 기준 문서·콘솔 확인분). 한국(ap-seoul-1·ap-chuncheon-1)은 GenAI 미제공 — 오사카가 가장 가깝다.
OCI_GENAI_REGIONS = [
    {"id": "ap-osaka-1", "label": "일본 오사카 (ap-osaka-1) — 한국에서 가장 가까움"},
    {"id": "ap-tokyo-1", "label": "일본 도쿄 (ap-tokyo-1)"},
    {"id": "us-chicago-1", "label": "미국 시카고 (us-chicago-1)"},
    {"id": "us-ashburn-1", "label": "미국 애슈번 (us-ashburn-1)"},
    {"id": "uk-london-1", "label": "영국 런던 (uk-london-1)"},
    {"id": "eu-frankfurt-1", "label": "독일 프랑크푸르트 (eu-frankfurt-1)"},
    {"id": "sa-saopaulo-1", "label": "브라질 상파울루 (sa-saopaulo-1)"},
    {"id": "ap-mumbai-1", "label": "인도 뭄바이 (ap-mumbai-1)"},
]
OCI_MODELS = ["cohere.command-r-plus-08-2024", "cohere.command-r-08-2024", "meta.llama-3.3-70b-instruct", "meta.llama-3.1-405b-instruct", "xai.grok-3"]
DEFAULT_ENDPOINTS = {"openai": "https://api.openai.com/v1"}
ENDPOINT_PRESETS = [
    {"label": "OpenAI", "url": "https://api.openai.com/v1"},
    {"label": "Google Gemini (OpenAI 호환)", "url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    {"label": "Groq", "url": "https://api.groq.com/openai/v1"},
]

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def oci_host(region: str) -> str:
    return f"inference.generativeai.{region}.oci.oraclecloud.com"


def build_attributes(form: dict) -> tuple[dict, list[str]]:
    """화면 폼 → CREATE_PROFILE attributes JSON. 반환 (attributes, 오류 목록). 빈 값은 넣지 않는다."""
    errs: list[str] = []
    provider = (form.get("provider") or "").strip().lower()
    if provider not in {p["id"] for p in PROVIDERS}:
        errs.append(f"provider 가 올바르지 않습니다: {provider or '(없음)'}")
    attrs: dict = {"provider": provider}
    cred = (form.get("credential_name") or "").strip()
    if not cred:
        errs.append("credential_name 이 필요합니다")
    else:
        attrs["credential_name"] = cred
    model = (form.get("model") or "").strip()
    if model:
        attrs["model"] = model
    elif provider != "oci" or not (form.get("oci_endpoint_id") or "").strip():
        errs.append("model 이 필요합니다 (OCI 전용 클러스터는 oci_endpoint_id 로 대신)")
    ep = (form.get("provider_endpoint") or "").strip()
    if ep:
        attrs["provider_endpoint"] = ep
    if provider == "oci":
        region = (form.get("region") or "").strip()
        if not region:
            errs.append("OCI 는 region 이 필수입니다 (한국 리전엔 GenAI 가 없어 ap-osaka-1 등 제공 리전만)")
        else:
            attrs["region"] = region
        for k in ("oci_compartment_id", "oci_endpoint_id", "oci_apiformat", "oci_runtimetype"):
            v = (form.get(k) or "").strip()
            if v:
                attrs[k] = v
    if provider == "azure":
        for k in ("azure_resource_name", "azure_deployment_name"):
            v = (form.get(k) or "").strip()
            if v:
                attrs[k] = v
            else:
                errs.append(f"Azure 는 {k} 가 필요합니다")
    objs = form.get("object_list") or []
    if isinstance(objs, list) and objs:
        attrs["object_list"] = [{"owner": (o.get("owner") or "ADMIN").upper(), "name": (o.get("name") or "").upper()} for o in objs if o.get("name")]
    for k in ("annotations", "comments", "constraints", "conversation"):
        if k in form and form[k] is not None:
            attrs[k] = bool(form[k])
    emb = (form.get("embedding_model") or "").strip()
    if emb:
        attrs["embedding_model"] = emb
    for k in ("temperature", "max_tokens"):
        v = form.get(k)
        if v not in (None, ""):
            try:
                attrs[k] = float(v) if k == "temperature" else int(v)
            except (TypeError, ValueError):
                errs.append(f"{k} 는 숫자여야 합니다")
    return attrs, errs


def plsql_for(profile_name: str, attrs: dict, description: str = "") -> str:
    body = json.dumps(attrs, ensure_ascii=False, indent=2).replace("'", "''")
    desc = f",\n    description  => '{description.replace(chr(39), chr(39) * 2)}'" if description else ""
    return f"BEGIN\n  DBMS_CLOUD_AI.CREATE_PROFILE(\n    profile_name => '{profile_name}',\n    attributes   => '{body}'{desc});\nEND;"


def validate_name(name: str) -> str | None:
    if not name or not _NAME_RE.match(name):
        return "프로필 이름은 영문으로 시작하고 영문·숫자·_ 만, 128자까지입니다"
    return None


async def create_profile(pool, profile_name: str, attrs: dict, description: str = "") -> None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN DBMS_CLOUD_AI.CREATE_PROFILE(profile_name => :n, attributes => :a, description => :d); END;",
                              {"n": profile_name, "a": json.dumps(attrs, ensure_ascii=False), "d": description or None})


async def drop_profile(pool, profile_name: str) -> None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("BEGIN DBMS_CLOUD_AI.DROP_PROFILE(profile_name => :n, force => TRUE); END;", {"n": profile_name})


async def wizard_meta(pool) -> dict:
    """폼이 고를 것들 — 크리덴셜 목록(유형 추정), 테이블 목록(현재 스키마), 프로바이더·리전·엔드포인트 프리셋."""
    creds, tables = [], []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT credential_name, username, enabled FROM user_credentials ORDER BY credential_name")
            for name, user, enabled in await cur.fetchall():
                creds.append({"credential_name": name, "username": user, "enabled": enabled, "kind": credential_kind(name, user)})
            await cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
            owner = (await cur.fetchone())[0]
            await cur.execute("""SELECT table_name, num_rows, DBMS_LOB.SUBSTR(comments, 200, 1) FROM user_tables t
                                 LEFT JOIN user_tab_comments c USING (table_name)
                                 WHERE table_name NOT LIKE 'DR$%' AND table_name NOT LIKE 'VECTOR$%' AND table_name NOT LIKE 'DM$%'
                                   AND table_name NOT LIKE '%$VECTAB' AND table_name NOT LIKE 'DBTOOLS$%' AND table_name NOT LIKE 'AI\\_%' ESCAPE '\\'
                                 ORDER BY table_name""")
            for name, n, cmt in await cur.fetchall():
                tables.append({"owner": owner, "name": name, "num_rows": n, "comment": (await _lob_to_str(cmt)) if hasattr(cmt, "read") else cmt})
    return {"providers": PROVIDERS, "oci_regions": OCI_GENAI_REGIONS, "oci_models": OCI_MODELS, "endpoint_presets": ENDPOINT_PRESETS,
            "credentials": creds, "tables": tables}


def credential_kind(name: str, username: str | None) -> str:
    """크리덴셜 유형 추정 — 값(키)은 어떤 뷰에도 안 나오므로 이름·username 으로만."""
    n = (name or "").upper()
    u = username or ""
    if n == "OCI$RESOURCE_PRINCIPAL" or "RESOURCE_PRINCIPAL" in n:
        return "resource_principal"
    if u.startswith("ocid1.user."):
        return "oci_api_key"
    return "api_key"
