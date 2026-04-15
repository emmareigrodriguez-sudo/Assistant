"""Configuration management with validation and secure defaults."""

import logging
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ona mounts file secrets here by default
SECRETS_DIR = Path("/usr/local/secrets")


def _read_file_secret(name: str) -> str | None:
    """Read a secret from Ona file secrets if available."""
    path = SECRETS_DIR / name
    if path.is_file():
        return path.read_text().strip()
    return None


class JiraConfig(BaseSettings):
    """Jira Cloud API configuration.

    Loads credentials in order of priority:
      1. Environment variables (JIRA_LOGIN, JIRA_API_KEY)
      2. .env file
      3. Ona file secrets (/usr/local/secrets/JIRA_LOGIN, JIRA_API_KEY)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    jira_base_url: str = Field(description="Jira Cloud instance URL (e.g. https://x.atlassian.net)")
    jira_user_email: str = Field(
        default="",
        description="Email associated with the API token",
        validation_alias=AliasChoices("JIRA_LOGIN", "JIRA_USER_EMAIL", "jira_user_email"),
    )
    jira_api_token: str = Field(
        default="",
        description="Jira API token (from id.atlassian.com)",
        validation_alias=AliasChoices("JIRA_API_KEY", "JIRA_API_TOKEN", "jira_api_token"),
    )

    @model_validator(mode="after")
    def load_file_secrets(self) -> "JiraConfig":
        """Fall back to Ona file secrets if env vars are missing."""
        if not self.jira_user_email:
            value = _read_file_secret("JIRA_LOGIN")
            if value:
                self.jira_user_email = value
        if not self.jira_api_token:
            value = _read_file_secret("JIRA_API_KEY")
            if value:
                self.jira_api_token = value

        if not self.jira_user_email:
            raise ValueError("JIRA_LOGIN not found in env vars, .env, or /usr/local/secrets/")
        if not self.jira_api_token:
            raise ValueError("JIRA_API_KEY not found in env vars, .env, or /usr/local/secrets/")
        return self

    webhook_secret: str = Field(default="", description="Secret for validating webhook payloads")
    webhook_port: int = Field(default=5000, description="Port for the webhook listener")

    log_level: str = Field(default="INFO")

    # Request defaults
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    max_retries: int = Field(default=3, description="Max retries on transient failures")

    @field_validator("jira_base_url")
    @classmethod
    def normalize_base_url(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        if v not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {v}")
        return v


def setup_logging(config: JiraConfig) -> logging.Logger:
    """Configure structured logging. Avoids logging sensitive data."""
    logger = logging.getLogger("jira_integration")
    logger.setLevel(getattr(logging, config.log_level))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
