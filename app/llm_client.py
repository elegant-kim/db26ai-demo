"""
공통 LLM 클라이언트 (AWR 분석, RAG 답변 생성 등)
- Groq, Google Gemini 지원 (OpenAI 호환 API)
- DBMS_CLOUD_AI.GENERATE와 무관 (Select AI 전용은 별도)
"""

import json
import re
import httpx

from app.config import settings

# 제공자별 API 설정
LLM_CONFIGS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_attr": "GROQ_API_KEY",
        "model_attr": "GROQ_MODEL",
        "display_name": "Groq (Llama 3.3 70B)",
        "max_tokens": 16000,
        "max_input_chars": 12000,   # 요청 크기 제한 대응
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/v1/chat/completions",
        "api_key_attr": "GOOGLE_API_KEY",
        "model_attr": "GOOGLE_MODEL",
        "display_name": "Google Gemini 2.5 Flash",
        "max_tokens": 16000,
        "max_input_chars": 30000,   # 넉넉한 컨텍스트 활용
    },
}


def get_available_providers() -> list:
    """설정된 API 키가 있는 LLM 제공자 목록 반환"""
    providers = []
    for key, config in LLM_CONFIGS.items():
        api_key = getattr(settings, config["api_key_attr"], "")
        if api_key:
            providers.append({
                "id": key,
                "name": config["display_name"],
                "model": getattr(settings, config["model_attr"], ""),
            })
    return providers


def get_max_input_chars(provider: str = None) -> int:
    """제공자별 최대 입력 글자 수 반환"""
    provider = provider or settings.LLM_PROVIDER
    config = LLM_CONFIGS.get(provider, {})
    return config.get("max_input_chars", 12000)


async def call_llm(prompt: str, provider: str = None, system_prompt: str = None) -> str:
    """
    LLM 채팅 API 호출 (OpenAI 호환)
    Args:
        prompt: 사용자 프롬프트
        provider: "groq" 또는 "google" (None이면 기본값 사용)
        system_prompt: 시스템 프롬프트 (선택)
    Returns:
        LLM 응답 텍스트
    """
    provider = provider or settings.LLM_PROVIDER
    if provider not in LLM_CONFIGS:
        raise ValueError(f"지원하지 않는 LLM 제공자: {provider}")

    config = LLM_CONFIGS[provider]
    api_key = getattr(settings, config["api_key_attr"], "")
    model = getattr(settings, config["model_attr"], "")

    if not api_key:
        raise ValueError(f"{provider} API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": config.get("max_tokens", 8000),
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(config["url"], json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]


async def call_llm_json(prompt: str, provider: str = None, system_prompt: str = None) -> dict:
    """
    LLM 호출 후 응답에서 JSON을 추출
    Returns:
        파싱된 JSON dict
    """
    raw = await call_llm(prompt, provider, system_prompt)
    return extract_json_from_response(raw)


def extract_json_from_response(raw: str) -> dict:
    """LLM 응답에서 JSON을 추출"""
    # 1) ```json ... ``` 블록
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2) { ... } 전체
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 3) 파싱 실패
    return {"raw_response": raw, "parse_error": "JSON 파싱에 실패했습니다."}
