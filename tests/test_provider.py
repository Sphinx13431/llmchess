import unittest
from unittest.mock import Mock, patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

from llmchess import (
    LLMProvider,
    ModelInvocationError,
    ModelResponseError,
    OllamaConfig,
    OllamaProvider,
)


class OllamaProviderTests(unittest.TestCase):
    def test_default_configuration_uses_selected_model_and_temperature(self) -> None:
        with patch("llmchess.provider.ChatOllama") as chat_ollama:
            OllamaProvider()

        chat_ollama.assert_called_once_with(model="gemma4:e2b", temperature=0.2)

    def test_custom_model_configuration_is_used(self) -> None:
        config = OllamaConfig(model="custom-model", temperature=0.5)
        with patch("llmchess.provider.ChatOllama") as chat_ollama:
            OllamaProvider(config)

        chat_ollama.assert_called_once_with(model="custom-model", temperature=0.5)

    def test_generate_returns_raw_text_response(self) -> None:
        provider: LLMProvider = OllamaProvider(
            chat_model=FakeListChatModel(responses=['{"move":"e2e4"}'])
        )

        response = provider.generate("Choose a legal move.")

        self.assertEqual(response, '{"move":"e2e4"}')

    def test_invocation_error_is_distinct_and_preserves_cause(self) -> None:
        model = Mock(spec=BaseChatModel)
        model.invoke.side_effect = ConnectionError("Ollama is unavailable")
        provider = OllamaProvider(chat_model=model)

        with self.assertRaises(ModelInvocationError) as raised:
            provider.generate("Choose a legal move.")

        self.assertIsInstance(raised.exception.__cause__, ConnectionError)
        self.assertIn("gemma4:e2b", str(raised.exception))

    def test_non_text_response_raises_response_error(self) -> None:
        model = Mock(spec=BaseChatModel)
        model.invoke.return_value = AIMessage(content=[{"type": "image"}])
        provider = OllamaProvider(chat_model=model)

        with self.assertRaises(ModelResponseError):
            provider.generate("Choose a legal move.")


if __name__ == "__main__":
    unittest.main()
