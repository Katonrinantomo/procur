import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "Procur.AI"

    # No default value — must be set in .env or environment.
    # The app will refuse to start without a valid DATABASE_URL.
    DATABASE_URL: str = ""

    # JWT signing secret — required, at least 32 characters.
    # The app will refuse to start without it.
    JWT_SECRET: str = ""

    # Demo password used by seed.py to create demo users.
    DEMO_PASSWORD: str = "password123"

    # Comma-separated list of allowed Host header values for TrustedHostMiddleware.
    # Override in tests or staging by setting ALLOWED_HOSTS env var.
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    LANGFLOW_URL: str = "http://localhost:7860"
    LANGFLOW_API_KEY: str = ""
    LANGFLOW_ORGANIZE_FLOW_ID: str = ""
    LANGFLOW_WEBCHECK_FLOW_ID: str = ""
    LANGFLOW_MAKER_FLOW_ID: str = ""
    LANGFLOW_CHECKER_FLOW_ID: str = ""
    LANGFLOW_NARRATOR_FLOW_ID: str = ""

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

    # pricing.py — a web reference needs at least this many kept quotes
    WEB_MIN_QUOTES: int = 3

    # pricing.py — price bands by diff_pct (%), each edge inclusive
    PRICE_BAND_KOMPETITIF_PCT: float = -10.0
    PRICE_BAND_WAJAR_PCT: float = 5.0
    PRICE_BAND_PERHATIAN_PCT: float = 15.0

    # pricing.py — TIDAK WAJAR above this diff_pct (%) is TOLAK, not NEGOSIASI
    RECOMMEND_TOLAK_PCT: float = 30.0

    # decisions — approving a row at or above this risk score is an override
    # (reason and outcome tag required), like approving a flagged row
    OVERRIDE_RISK_SCORE: int = 50

    # quotations — maximum upload size
    QUOTATION_MAX_BYTES: int = 10 * 1024 * 1024


settings = Settings()

# Flow name -> Settings attribute holding its Langflow flow ID.
# Used by the startup warning, flowcheck and /api/health/flows.
FLOW_ID_SETTINGS: dict[str, str] = {
    "organize": "LANGFLOW_ORGANIZE_FLOW_ID",
    "web_check": "LANGFLOW_WEBCHECK_FLOW_ID",
    "maker": "LANGFLOW_MAKER_FLOW_ID",
    "checker": "LANGFLOW_CHECKER_FLOW_ID",
    "narrator": "LANGFLOW_NARRATOR_FLOW_ID",
}


def validate_settings() -> None:
    """Exit with a clear message if required settings are missing.

    Called from main.py lifespan startup.
    """
    if not settings.DATABASE_URL:
        logger.critical(
            "DATABASE_URL tidak dikonfigurasi. Set di backend/.env atau env var."
        )
        sys.exit(1)

    if not settings.JWT_SECRET:
        logger.critical(
            "JWT_SECRET tidak dikonfigurasi. Set di backend/.env atau env var."
        )
        sys.exit(1)

    if len(settings.JWT_SECRET) < 32:
        logger.critical(
            "JWT_SECRET harus minimal 32 karakter."
        )
        sys.exit(1)
