import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB

    reset_token_expire_minutes: int = 15

    mail_server: str = ""
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = ""
    mail_use_tls: bool = True

    front_end_url: str = "http://localhost:8000"


settings = Settings()


def is_email_configured() -> bool:
    """Return whether required mail settings are configured and non-empty."""
    required_settings = {
        "MAIL_SERVER": "mail_server",
        "MAIL_USERNAME": "mail_username",
        "MAIL_PASSWORD": "mail_password",
        "MAIL_FROM": "mail_from",
    }

    for env_key, field_name in required_settings.items():
        value = getattr(settings, field_name, None)
        if value is None:
            return False
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if not str(value).strip():
            return False

    configured_fields = getattr(settings, "model_fields_set", set())
    if configured_fields:
        normalized_fields = {field.lower() for field in configured_fields}
        return {"mail_server", "mail_username", "mail_password", "mail_from"}.issubset(
            normalized_fields
        )

    return all(os.environ.get(env_key, "").strip() for env_key in required_settings)
