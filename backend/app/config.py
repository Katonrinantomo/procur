from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "Procur.AI"

    DATABASE_URL: str = "postgresql+psycopg2://procur:procur@localhost:5432/procur"
    LANGFLOW_URL: str = "http://localhost:7860"
    LANGFLOW_API_KEY: str = ""
    LANGFLOW_ORGANIZE_FLOW_ID: str = ""
    LANGFLOW_WEBCHECK_FLOW_ID: str = ""

    # ---------------------------------------------------------------------------
    # Check engine thresholds
    # ---------------------------------------------------------------------------

    # matcher.py — minimum token_set_ratio score to count as a match
    MATCH_THRESHOLD: float = 85.0

    # pricing.py — how many recent purchases to average for the reference price
    HISTORY_WINDOW: int = 3

    # flags.py — PRICE_ABOVE_REF fires when diff_pct exceeds this value (%)
    FLAG_PRICE_ABOVE_REF_PCT: float = 15.0

    # flags.py — STOCK_COVER_HIGH fires when cover exceeds this many months
    FLAG_STOCK_COVER_MONTHS: float = 1.0

    # flags.py — QTY_UNUSUAL fires when qty > multiplier × median past qty
    FLAG_QTY_UNUSUAL_MULTIPLIER: float = 2.0

    # web_check.py — reuse cached web quotes up to this many days old
    WEB_QUOTE_MAX_AGE_DAYS: int = 60


settings = Settings()
