"""Unit tests for the provider-isolated Strands model factory (Phase 5, Batch 0).

``src/model_factory.py`` is the only module in ``src/`` permitted to import a
concrete model provider. These tests are offline: constructing an
``OpenAIModel`` only stores configuration and opens no socket.
"""

import socket

import pytest
from strands.models.model import Model

from src.credentials import CredentialManager
from src.model_factory import build_model

_EXPLICIT_VALUES: dict[str, str] = {
    "HSE_MODEL_FAST_ENDPOINT": "https://fast.example.invalid/openai/v1/",
    "HSE_MODEL_FAST_API_KEY": "fast-secret-key",
    "HSE_MODEL_FAST_DEPLOYMENT": "fast-deployment",
    "HSE_MODEL_STRONG_ENDPOINT": "https://strong.example.invalid/openai/v1/",
    "HSE_MODEL_STRONG_API_KEY": "strong-secret-key",
    "HSE_MODEL_STRONG_DEPLOYMENT": "strong-deployment",
}


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every ``HSE_MODEL_*`` variable from the OS environment (D16).

    Explicit init kwargs already outrank the environment, so this is a guard
    against a future test in this file relying on file or environment sources
    and silently picking up a developer's real credentials instead.
    """
    for name in _EXPLICIT_VALUES:
        monkeypatch.delenv(name, raising=False)


def _credentials() -> CredentialManager:
    """Build a manager from explicit values with the .env file disabled."""
    return CredentialManager(_env_file=None, **_EXPLICIT_VALUES)


def test_build_model_returns_strands_model() -> None:
    """The factory returns an instance of the abstract Strands Model ABC."""
    model = build_model("gpt-5-mini", credentials=_credentials())

    assert isinstance(model, Model)


def test_build_model_passes_endpoint_and_key_as_client_args() -> None:
    """The endpoint and API key reach the provider as client_args, verbatim."""
    model = build_model("gpt-5.4", credentials=_credentials())

    client_args = model.client_args
    assert client_args["base_url"] == "https://strong.example.invalid/openai/v1/"
    assert client_args["api_key"] == "strong-secret-key"


def test_build_model_sets_model_id_to_deployment() -> None:
    """model_id is the deployment name, not the pipeline model ID."""
    fast = build_model("gpt-5-mini", credentials=_credentials())
    strong = build_model("gpt-5.4", credentials=_credentials())

    assert fast.get_config()["model_id"] == "fast-deployment"
    assert strong.get_config()["model_id"] == "strong-deployment"


def test_build_model_makes_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction alone reaches no socket (D16: zero-cost tests)."""

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("build_model must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    model = build_model("gpt-5-mini", credentials=_credentials())

    assert isinstance(model, Model)
