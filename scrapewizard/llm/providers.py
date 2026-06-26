from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from scrapewizard.core.logging import log

@dataclass
class ProviderResponse:
    content: str
    input_tokens: int
    output_tokens: int

class BaseProvider(ABC):
    @abstractmethod
    def call(self, messages: List[Dict[str, str]], model: str, temperature: float, json_schema: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Execute the LLM call using the specific provider strategy."""
        pass

    @abstractmethod
    def supports_json_schema(self) -> bool:
        """Return True if the provider natively supports JSON schema constraints."""
        pass


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.client = None

    def _get_client(self):
        if not self.client:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self.client

    def call(self, messages: List[Dict[str, str]], model: str, temperature: float, json_schema: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        client = self._get_client()
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response_schema",
                    "strict": True,
                    "schema": json_schema
                }
            }

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            # If the specific endpoint doesn't support json_schema (e.g. OpenRouter or older OpenAI models),
            # fallback to generic json_object mode.
            if json_schema and ("response_format" in err_str or "json_schema" in err_str or "400" in err_str or "bad_request" in err_str):
                log("JSON schema not supported by endpoint. Falling back to generic json_object mode.", level="warning")
                kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
            else:
                raise e

        content = response.choices[0].message.content or ""
        input_tokens = 0
        output_tokens = 0
        if getattr(response, "usage", None):
            input_tokens = getattr(response.usage, "prompt_tokens", 0)
            output_tokens = getattr(response.usage, "completion_tokens", 0)

        return ProviderResponse(content, input_tokens, output_tokens)

    def supports_json_schema(self) -> bool:
        return True


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None

    def _get_client(self):
        if not self.client:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        return self.client

    def call(self, messages: List[Dict[str, str]], model: str, temperature: float, json_schema: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        client = self._get_client()
        
        # Anthropic has a separate 'system' parameter for system prompts.
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)

        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "messages": user_messages,
            "temperature": temperature,
        }
        if system_content:
            kwargs["system"] = system_content

        response = client.messages.create(**kwargs)
        
        # Extract text content
        content = ""
        if response.content:
            content = response.content[0].text

        input_tokens = getattr(response.usage, "input_tokens", 0)
        output_tokens = getattr(response.usage, "output_tokens", 0)

        return ProviderResponse(content, input_tokens, output_tokens)

    def supports_json_schema(self) -> bool:
        return False


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def call(self, messages: List[Dict[str, str]], model: str, temperature: float, json_schema: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        import httpx
        from scrapewizard.core.constants import LOCAL_LLM_COLD_START_TIMEOUT

        payload = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature
            },
            "stream": False
        }

        if json_schema:
            payload["format"] = json_schema

        url = f"{self.base_url}/api/chat"
        try:
            response = httpx.post(url, json=payload, timeout=LOCAL_LLM_COLD_START_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            # Fallback for older Ollama versions that might not support structured JSON schema dicts
            if json_schema and e.response.status_code == 400:
                log("Ollama returned 400 for structured schema. Falling back to generic format='json'.", level="warning")
                payload["format"] = "json"
                response = httpx.post(url, json=payload, timeout=LOCAL_LLM_COLD_START_TIMEOUT)
                response.raise_for_status()
                data = response.json()
            else:
                raise e
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")

        content = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return ProviderResponse(content, input_tokens, output_tokens)

    def supports_json_schema(self) -> bool:
        return True


class EmbeddedProvider(BaseProvider):
    def call(self, messages: List[Dict[str, str]], model: str, temperature: float, json_schema: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        raise NotImplementedError("Embedded llama.cpp provider is not implemented yet.")

    def supports_json_schema(self) -> bool:
        return False
