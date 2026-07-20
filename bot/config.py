import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _as_bool(v: str, default=False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    bot_token: str
    bot_username: str
    owner_telegram_id: int
    currency: str
    db_path: str
    force_join_channel: str
    force_join_group: str
    log_chat_id: int
    support_chat_id: int
    dispute_window_hours: int
    low_stock_threshold_default: int
    tos_version: int

    payment_stripe_enabled: bool
    payment_tg_enabled: bool
    payment_binance_pay_enabled: bool
    payment_crypto_enabled: bool
    payment_upi_enabled: bool
    payment_binance_id_enabled: bool


def load_settings() -> Settings:
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        bot_username=os.getenv("BOT_USERNAME", ""),
        owner_telegram_id=int(os.getenv("OWNER_TELEGRAM_ID", "0")),
        currency=os.getenv("CURRENCY", "USD"),
        db_path=os.getenv("DB_PATH", "./data/bot.db"),
        force_join_channel=os.getenv("FORCE_JOIN_CHANNEL", ""),
        force_join_group=os.getenv("FORCE_JOIN_GROUP", ""),
        log_chat_id=int(os.getenv("LOG_CHAT_ID", "0")),
        support_chat_id=int(os.getenv("SUPPORT_CHAT_ID", "0")),
        dispute_window_hours=int(os.getenv("DISPUTE_WINDOW_HOURS", "24")),
        low_stock_threshold_default=int(os.getenv("LOW_STOCK_THRESHOLD_DEFAULT", "5")),
        tos_version=int(os.getenv("TOS_VERSION", "1")),
        payment_stripe_enabled=_as_bool(os.getenv("PAYMENT_STRIPE_ENABLED", "0")),
        payment_tg_enabled=_as_bool(os.getenv("PAYMENT_TG_ENABLED", "0")),
        payment_binance_pay_enabled=_as_bool(os.getenv("PAYMENT_BINANCE_PAY_ENABLED", "0")),
        payment_crypto_enabled=_as_bool(os.getenv("PAYMENT_CRYPTO_ENABLED", "0")),
        payment_upi_enabled=_as_bool(os.getenv("PAYMENT_UPI_ENABLED", "1")),
        payment_binance_id_enabled=_as_bool(os.getenv("PAYMENT_BINANCE_ID_ENABLED", "1")),
    )
