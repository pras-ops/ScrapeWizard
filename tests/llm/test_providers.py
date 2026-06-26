import sys
from unittest.mock import MagicMock, patch
# Mock anthropic module to avoid import issues
sys.modules['anthropic'] = MagicMock()

import pytest
import httpx
from scrapewizard.llm.providers import OpenAIProvider, AnthropicProvider, OllamaProvider, EmbeddedProvider, ProviderResponse

class TestOpenAIProvider:
    @patch('openai.OpenAI')
    def test_call_success(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello OpenAI"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="test-key")
        res = provider.call(
            messages=[{"role": "user", "content": "ping"}],
            model="gpt-4-turbo",
            temperature=0.1
        )

        assert res.content == "Hello OpenAI"
        assert res.input_tokens == 10
        assert res.output_tokens == 20
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.1
        )

    @patch('openai.OpenAI')
    def test_call_json_schema(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="{}"))]
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="test-key")
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        
        provider.call(
            messages=[{"role": "user", "content": "ping"}],
            model="gpt-4-turbo",
            temperature=0.1,
            json_schema=schema
        )

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "response_schema",
                    "strict": True,
                    "schema": schema
                }
            }
        )

    @patch('openai.OpenAI')
    def test_call_json_schema_fallback(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Raise error on first call (strict schema error), succeed on second (generic json_object)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="{}"))]
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=5)
        
        mock_client.chat.completions.create.side_effect = [
            Exception("400 BadRequest: response_format is not supported"),
            mock_response
        ]

        provider = OpenAIProvider(api_key="test-key")
        schema = {"type": "object"}
        
        res = provider.call(
            messages=[{"role": "user", "content": "ping"}],
            model="gpt-4-turbo",
            temperature=0.1,
            json_schema=schema
        )

        assert res.content == "{}"
        assert mock_client.chat.completions.create.call_count == 2


class TestAnthropicProvider:
    @patch('anthropic.Anthropic')
    def test_call_success(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello Anthropic")]
        mock_response.usage = MagicMock(input_tokens=15, output_tokens=25)
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key="test-key")
        messages = [
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "ping"}
        ]
        res = provider.call(
            messages=messages,
            model="claude-3-5-sonnet",
            temperature=0.1
        )

        assert res.content == "Hello Anthropic"
        assert res.input_tokens == 15
        assert res.output_tokens == 25
        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet",
            max_tokens=4096,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.1,
            system="you are helpful"
        )


class TestOllamaProvider:
    @patch('httpx.post')
    def test_call_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Hello Ollama"},
            "prompt_eval_count": 8,
            "eval_count": 12
        }
        mock_post.return_value = mock_response

        provider = OllamaProvider(base_url="http://localhost:11434")
        res = provider.call(
            messages=[{"role": "user", "content": "ping"}],
            model="qwen2.5-coder:3b",
            temperature=0.1
        )

        assert res.content == "Hello Ollama"
        assert res.input_tokens == 8
        assert res.output_tokens == 12
        
        # Verify JSON payload
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/chat"
        assert kwargs["json"]["model"] == "qwen2.5-coder:3b"
        assert kwargs["json"]["messages"] == [{"role": "user", "content": "ping"}]

    @patch('httpx.post')
    def test_call_schema_fallback(self, mock_post):
        # First POST fails with 400 (unsupported schema), second succeeds with format='json'
        fail_response = MagicMock()
        fail_response.status_code = 400
        fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="400 Bad Request",
            request=MagicMock(),
            response=fail_response
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "message": {"content": "{}"},
            "prompt_eval_count": 10,
            "eval_count": 10
        }

        mock_post.side_effect = [fail_response, success_response]

        provider = OllamaProvider(base_url="http://localhost:11434")
        res = provider.call(
            messages=[{"role": "user", "content": "ping"}],
            model="qwen2.5-coder:3b",
            temperature=0.1,
            json_schema={"type": "object"}
        )

        assert res.content == "{}"
        assert mock_post.call_count == 2
        # Verify second call used format: "json"
        second_call_kwargs = mock_post.call_args_list[1][1]
        assert second_call_kwargs["json"]["format"] == "json"


class TestEmbeddedProvider:
    def test_not_implemented(self):
        provider = EmbeddedProvider()
        with pytest.raises(NotImplementedError):
            provider.call([], "model", 0.1)
        assert provider.supports_json_schema() is False
