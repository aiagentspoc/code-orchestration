"""Unit tests for the .env-backed model credential manager (Phase 5, Batch 0).

Every test builds ``CredentialManager`` with either ``_env_file=None`` or a
``tmp_path`` file, so a developer's real ``.env`` can never leak into an
assertion, and the autouse ``_isolate_environment`` fixture below strips the
``HSE_MODEL_*`` OS variables that would otherwise outrank both (D16: zero-cost,
hermetic, offline tests).
"""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from src.credentials import CredentialManager, ModelCredentials

_EXPLICIT_VALUES: dict[str, str] = {
    "HSE_MODEL_FAST_ENDPOINT": "https://fast.example.invalid/openai/v1/",
    "HSE_MODEL_FAST_API_KEY": "fast-secret-key",
    "HSE_MODEL_FAST_DEPLOYMENT": "gpt-5-mini",
    "HSE_MODEL_STRONG_ENDPOINT": "https://strong.example.invalid/openai/v1/",
    "HSE_MODEL_STRONG_API_KEY": "strong-secret-key",
    "HSE_MODEL_STRONG_DEPLOYMENT": "gpt-5.4",
}


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every ``HSE_MODEL_*`` variable from the OS environment (D16).

    ``pydantic-settings`` ranks OS environment variables *above* dotenv values,
    so without this a developer's exported credentials silently override the
    ``tmp_path`` ``.env`` these tests construct — and, worse, satisfy the very
    required-field check ``test_credential_manager_missing_vars_raises`` exists
    to prove. Keyed off ``_EXPLICIT_VALUES`` so it cannot drift out of sync.
    """
    for name in _EXPLICIT_VALUES:
        monkeypatch.delenv(name, raising=False)


def _manager() -> CredentialManager:
    """Build a manager from explicit values with the .env file disabled."""
    return CredentialManager(_env_file=None, **_EXPLICIT_VALUES)


def test_credential_manager_constructs_from_explicit_values() -> None:
    """Explicit aliased values populate every credential slot without touching disk."""
    manager = _manager()

    assert manager.fast_endpoint == "https://fast.example.invalid/openai/v1/"
    assert manager.fast_api_key.get_secret_value() == "fast-secret-key"
    assert manager.fast_deployment == "gpt-5-mini"
    assert manager.strong_endpoint == "https://strong.example.invalid/openai/v1/"
    assert manager.strong_api_key.get_secret_value() == "strong-secret-key"
    assert manager.strong_deployment == "gpt-5.4"


def test_credential_manager_reads_env_file(tmp_path: Path) -> None:
    """Values are sourced from an explicitly supplied .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "HSE_MODEL_FAST_ENDPOINT=https://file-fast.example.invalid/openai/v1/",
                "HSE_MODEL_FAST_API_KEY=file-fast-key",
                "HSE_MODEL_STRONG_ENDPOINT=https://file-strong.example.invalid/openai/v1/",
                "HSE_MODEL_STRONG_API_KEY=file-strong-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manager = CredentialManager(_env_file=env_file)

    assert manager.fast_endpoint == "https://file-fast.example.invalid/openai/v1/"
    assert manager.fast_api_key.get_secret_value() == "file-fast-key"
    assert manager.strong_api_key.get_secret_value() == "file-strong-key"
    # Deployments fall back to the ARCHITECTURE §3 defaults when absent from the file.
    assert manager.fast_deployment == "gpt-5-mini"
    assert manager.strong_deployment == "gpt-5.4"


def test_credential_manager_missing_vars_raises(tmp_path: Path) -> None:
    """A missing required key raises ValidationError naming it, never at import time."""
    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")

    with pytest.raises(ValidationError) as excinfo:
        CredentialManager(_env_file=empty_env)

    message = str(excinfo.value)
    assert "HSE_MODEL_FAST_ENDPOINT" in message
    assert "HSE_MODEL_STRONG_API_KEY" in message


def test_api_key_is_masked_in_str_and_repr() -> None:
    """SecretStr keeps API keys out of logs and tracebacks (Rule 6 logging safety)."""
    manager = _manager()

    assert "fast-secret-key" not in str(manager)
    assert "fast-secret-key" not in repr(manager)
    assert "strong-secret-key" not in str(manager)
    assert "strong-secret-key" not in repr(manager)
    assert str(manager.fast_api_key) == "**********"

    credentials = manager.for_model("gpt-5-mini")
    assert "fast-secret-key" not in str(credentials)
    assert "fast-secret-key" not in repr(credentials)


def test_for_model_returns_fast_credentials() -> None:
    """The fast model ID resolves to the fast credential slot."""
    credentials = _manager().for_model("gpt-5-mini")

    assert isinstance(credentials, ModelCredentials)
    assert credentials.endpoint == "https://fast.example.invalid/openai/v1/"
    assert isinstance(credentials.api_key, SecretStr)
    assert credentials.api_key.get_secret_value() == "fast-secret-key"
    assert credentials.deployment == "gpt-5-mini"


def test_for_model_returns_strong_credentials() -> None:
    """The strong model ID resolves to the strong credential slot."""
    credentials = _manager().for_model("gpt-5.4")

    assert isinstance(credentials, ModelCredentials)
    assert credentials.endpoint == "https://strong.example.invalid/openai/v1/"
    assert credentials.api_key.get_secret_value() == "strong-secret-key"
    assert credentials.deployment == "gpt-5.4"


def test_for_model_rejects_unknown_model_id() -> None:
    """An unrecognised model ID raises ValueError naming the offending ID."""
    with pytest.raises(ValueError) as excinfo:
        _manager().for_model("gpt-nonexistent")

    assert "gpt-nonexistent" in str(excinfo.value)
