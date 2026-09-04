import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    ORACLE_DSN: str = os.getenv("ORACLE_DSN", "")
    ORACLE_USER: str = os.getenv("ORACLE_USER", "")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")
    ORACLE_WALLET_DIR: str = os.getenv("ORACLE_WALLET_DIR", "")
    ORACLE_WALLET_PASSWORD: str = os.getenv("ORACLE_WALLET_PASSWORD", "")

    SELECT_AI_PROFILE: str = os.getenv("SELECT_AI_PROFILE", "")  # 빈 값이면 DB에서 동적 결정

    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8247"))

    # Vector Embedding 설정
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "MULTI_MINILM_L12_V2")
    EMBEDDING_SOURCE: str = os.getenv("EMBEDDING_SOURCE", "database")  # "database" or "external"
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))  # 벡터 차원 (외부 API: 768, ONNX 384 등)

    # LLM 채팅 설정 (AWR 분석, RAG 답변 생성용)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "google")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    XAI_MODEL: str = os.getenv("XAI_MODEL", "grok-3")


settings = Settings()
