"""Fail-closed prod guard + CORS parsing (ADR-009, config validation)."""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

import app.main as app_main
from app.core.config import Settings
from tests.conftest import TEST_API_KEY


class _CaptureHandler(logging.Handler):
    """Collect records emitted on the root logger during a block."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _messages_during_create_app() -> list[str]:
    # Attach to the module's own logger (app.main). The in-process Alembic run
    # (migration fixture) calls fileConfig(disable_existing_loggers=True), which
    # disables app loggers in the test process only — re-enable for the capture.
    handler = _CaptureHandler()
    target = logging.getLogger("app.main")
    prev_level, prev_propagate, prev_disabled = (
        target.level,
        target.propagate,
        target.disabled,
    )
    target.addHandler(handler)
    target.setLevel(logging.DEBUG)
    target.propagate = False
    target.disabled = False
    try:
        app_main.create_app()
    finally:
        target.removeHandler(handler)
        target.setLevel(prev_level)
        target.propagate = prev_propagate
        target.disabled = prev_disabled
    return [r.getMessage() for r in handler.records]


# --- APP_ENV fail-closed guard ---------------------------------------------
def test_prod_without_api_key_raises_config_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="prod", api_key="")
    message = str(exc_info.value)
    assert "API_KEY must be set when APP_ENV=prod" in message
    # The guard message must not embed any secret value.
    assert TEST_API_KEY not in message


def test_prod_with_api_key_constructs() -> None:
    settings = Settings(app_env="prod", api_key="some-prod-key")
    assert settings.app_env == "prod"
    assert settings.api_key == "some-prod-key"


def test_local_without_api_key_constructs() -> None:
    settings = Settings(app_env="local", api_key="")
    assert settings.app_env == "local"
    assert settings.api_key == ""


def test_default_app_env_is_local() -> None:
    # env has no APP_ENV (popped in conftest) -> default local.
    assert Settings().app_env == "local"


# --- create_app behaviour around the guard ---------------------------------
def test_create_app_warns_once_when_key_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_main, "get_settings", lambda: Settings(app_env="local", api_key=""))
    messages = _messages_during_create_app()
    assert messages.count("app_level_api_key_auth_disabled") == 1


def test_create_app_no_disabled_warning_when_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_main, "get_settings", lambda: Settings(app_env="prod", api_key="k-prod")
    )
    messages = _messages_during_create_app()
    assert "app_level_api_key_auth_disabled" not in messages


# --- CORS parsing (regression of the empty-value bug) ----------------------
def test_cors_empty_string_is_empty_list() -> None:
    assert Settings(cors_allow_origins="").cors_allow_origins == []


def test_cors_comma_separated_parses_to_list() -> None:
    settings = Settings(cors_allow_origins="https://a.com, https://b.com")
    assert settings.cors_allow_origins == ["https://a.com", "https://b.com"]


def test_cors_json_array_parses_to_list() -> None:
    settings = Settings(cors_allow_origins='["https://a.com","https://b.com"]')
    assert settings.cors_allow_origins == ["https://a.com", "https://b.com"]
