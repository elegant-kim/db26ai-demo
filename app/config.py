import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ORACLE_DSN: str = os.getenv("ORACLE_DSN", "")
    ORACLE_USER: str = os.getenv("ORACLE_USER", "")
    ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")
    ORACLE_WALLET_DIR: str = os.getenv("ORACLE_WALLET_DIR", "")
    ORACLE_WALLET_PASSWORD: str = os.getenv("ORACLE_WALLET_PASSWORD", "")

    SELECT_AI_PROFILE: str = os.getenv("SELECT_AI_PROFILE", "GROQ_PROFILE")

    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))


settings = Settings()
