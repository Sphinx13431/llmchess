"""Provider-independent model interface and Ollama implementation."""

from dataclasses import dataclass
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama


class LLMProvider(Protocol):
    """Interface implemented by each model provider strategy."""

    def generate(self, prompt: str) -> str:
        """Return the model's raw text response for a prompt."""


class ModelProviderError(RuntimeError):
    """Base error for failures communicating with a configured model."""


class ModelInvocationError(ModelProviderError):
    """Raised when a provider cannot complete a model invocation."""


class ModelResponseError(ModelProviderError):
    """Raised when a provider returns a response that is not plain text."""


@dataclass(frozen=True)
class OllamaConfig:
    """Ollama model settings used by the proof-of-concept provider."""

    model: str = "gemma4:e2b"
    temperature: float = 0.2


class OllamaProvider:
    """Generate text through LangChain's ChatOllama integration."""

    def __init__(
        self,
        config: OllamaConfig = OllamaConfig(),
        *,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self._config = config
        self._chat_model = (
            chat_model
            if chat_model is not None
            else ChatOllama(model=config.model, temperature=config.temperature)
        )

    def generate(self, prompt: str) -> str:
        """Invoke Ollama and return its text without parsing the response."""
        try:
            response = self._chat_model.invoke(prompt)
        except Exception as exc:
            raise ModelInvocationError(
                f"Failed to invoke Ollama model {self._config.model!r}."
            ) from exc

        if not isinstance(response.content, str):
            raise ModelResponseError(
                f"Ollama model {self._config.model!r} returned non-text content."
            )
        return response.content
