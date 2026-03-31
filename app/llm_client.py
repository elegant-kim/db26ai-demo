"""
공통 LLM 클라이언트 (AWR 분석, RAG 답변 생성 등)
- Groq, Google Gemini, OpenAI, Anthropic, xAI(Grok) 지원 (OpenAI 호환 API)
- DBMS_CLOUD_AI.GENERATE와 무관 (Select AI 전용은 별도)
"""

import json
import re
import httpx

from app.config import settings

# 제공자별 API 설정 (모두 OpenAI 호환 chat/completions 엔드포인트)
LLM_CONFIGS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_attr": "GROQ_API_KEY",
        "model_attr": "GROQ_MODEL",
        "display_name": "Groq (Llama 3.3 70B)",
        "max_tokens": 16000,
        "max_input_chars": 12000,
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/v1/chat/completions",
        "api_key_attr": "GOOGLE_API_KEY",
        "model_attr": "GOOGLE_MODEL",
        "display_name": "Google Gemini 2.5 Flash",
        "max_tokens": 32000,
        "max_input_chars": 80000,
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key_attr": "OPENAI_API_KEY",
        "model_attr": "OPENAI_MODEL",
        "display_name": "OpenAI (GPT-4o)",
        "max_tokens": 16000,
        "max_input_chars": 50000,
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "api_key_attr": "ANTHROPIC_API_KEY",
        "model_attr": "ANTHROPIC_MODEL",
        "display_name": "Anthropic (Claude Sonnet 4)",
        "max_tokens": 16000,
        "max_input_chars": 80000,
        "custom_format": True,  # Anthropic은 OpenAI 호환이 아닌 자체 포맷
    },
    "xai": {
        "url": "https://api.x.ai/v1/chat/completions",
        "api_key_attr": "XAI_API_KEY",
        "model_attr": "XAI_MODEL",
        "display_name": "xAI (Grok-3)",
        "max_tokens": 16000,
        "max_input_chars": 50000,
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
    LLM 채팅 API 호출
    Args:
        prompt: 사용자 프롬프트
        provider: "groq", "google", "openai", "anthropic", "xai" (None이면 기본값)
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

    # Anthropic은 자체 Messages API 포맷 사용
    if config.get("custom_format") and provider == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": config.get("max_tokens", 8000),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(config["url"], json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["content"][0]["text"]

    # OpenAI 호환 포맷 (groq, google, openai, xai)
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

    # 2) ``` ... ``` 블록 (json 태그 없는 코드블록)
    match = re.search(r"```\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        text = match.group(1).strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

    # 3) 가장 바깥쪽 { ... } 쌍 찾기 (중첩 브레이스 대응)
    start_idx = raw.find("{")
    if start_idx != -1:
        depth = 0
        end_idx = start_idx
        in_string = False
        escape_next = False
        for i in range(start_idx, len(raw)):
            c = raw[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if depth == 0:
            try:
                return json.loads(raw[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

    # 4) 파싱 실패
    return {"raw_response": raw, "parse_error": "JSON 파싱에 실패했습니다."}
