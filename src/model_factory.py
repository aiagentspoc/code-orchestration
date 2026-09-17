"""The single module in `src/` permitted to import a concrete model provider.

Every other module — notably :mod:`src.agents` — sees only the abstract
:class:`strands.models.model.Model`. Swapping providers therefore means editing
this file alone.

The configured endpoints are the OpenAI **v1-compatible surface** of Azure AI
Foundry, so this is a plain ``base_url`` + ``api_key`` pass-through: no path
rewriting and no ``api-version`` handling. Construction opens no socket;
Strands builds a fresh HTTP client per request.
"""

from strands.models.model import Model
from strands.models.openai import OpenAIModel

from .credentials import CredentialManager

__all__ = ["build_model"]


def build_model(model_id: str, credentials: CredentialManager | None = None) -> Model:
    """Construct a Strands ``Model`` for the given pipeline model ID.

    Args:
        model_id: A pipeline model ID from ARCHITECTURE §3 (``gpt-5-mini`` or ``gpt-5.4``).
        credentials: Pre-resolved credentials. When omitted, they are loaded
            from the environment and the project ``.env`` file.

    Returns:
        A provider-agnostic ``Model`` pointed at the configured endpoint.

    Raises:
        ValueError: If ``model_id`` is not a known pipeline model ID.
    """
    resolved = (credentials or CredentialManager()).for_model(model_id)
    return OpenAIModel(
        client_args={
            "base_url": resolved.endpoint,
            "api_key": resolved.api_key.get_secret_value(),
        },
        model_id=resolved.deployment,
    )
