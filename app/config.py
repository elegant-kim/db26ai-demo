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
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Vector Embedding 설정
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "minilm_l12_v2")
    EMBEDDING_SOURCE: str = os.getenv("EMBEDDING_SOURCE", "database")  # "database" or "external"
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")


settings = Settings()
