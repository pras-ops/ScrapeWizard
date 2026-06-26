import json
from typing import Dict, Any, Optional
from scrapewizard.core.config import ConfigManager
from scrapewizard.core.logging import log
from scrapewizard.utils.security import SecurityManager
from scrapewizard.llm.routing import LLMTask

class LLMClient:
    """
    Unified client for interacting with LLM providers.
    Supports OpenAI-compatible APIs (OpenAI, OpenRouter, Local).
    """
    
    # Class-level usage tracking to accumulate across all instances (agents)
    _usage_stats = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    
    # Approximate pricing per 1M tokens ($USD)
    PRICING = {
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "local": {"input": 0.0, "output": 0.0},
        "local-embedded": {"input": 0.0, "output": 0.0},
    }

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        self.config = ConfigManager.load_config()
        self.provider = provider or self.config.get("provider", "openai")
        self.api_key = api_key or self.config.get("api_key")
        self.model = model or self.config.get("model", "gpt-4-turbo")
        self.client = None
        
        self._setup_client()

    def _create_provider(self, provider_id: str):
        from scrapewizard.llm.providers import OpenAIProvider, AnthropicProvider, OllamaProvider, EmbeddedProvider
        from scrapewizard.core.config import ConfigManager
        
        # Check API key if not a local provider
        key = None
        if provider_id not in ("local", "local-embedded"):
            key = ConfigManager.get_api_key(provider_id)
            if provider_id == self.provider and self.api_key:
                key = self.api_key
            if not key:
                raise RuntimeError(f"API Key missing for provider '{provider_id}'. Please configure it using 'scrapewizard setup'.")
                
        if provider_id == "openai":
            return OpenAIProvider(api_key=key)
        elif provider_id == "anthropic":
            return AnthropicProvider(api_key=key)
        elif provider_id == "openrouter":
            return OpenAIProvider(api_key=key, base_url="https://openrouter.ai/api/v1")
        elif provider_id == "local":
            base_url = self.config.get("local_base_url", "http://localhost:11434")
            return OllamaProvider(base_url=base_url)
        elif provider_id == "local-embedded":
            return EmbeddedProvider()
        else:
            raise ValueError(f"Unknown provider: {provider_id}")

    def _setup_client(self) -> None:
        # Legacy client setup for backward compatibility
        try:
            provider = self._create_provider(self.provider)
            if hasattr(provider, "_get_client"):
                self.client = provider._get_client()
        except Exception:
            # Ignore initialization errors in __init__ (like missing API keys)
            # to prevent breaking initialization when only utility methods (like parse_json) are called.
            pass

    @classmethod
    def get_usage_stats(cls) -> Dict[str, Any]:
        """Get the global usage statistics."""
        return cls._usage_stats

    def get_estimated_cost(self) -> Any:
        """Calculate estimated cost based on tracked usage or return local cost indicator."""
        if self.provider in ("local", "local-embedded"):
            return "$0 — runs locally"
            
        model_pricing = self.PRICING.get(self.model, {"input": 0.0, "output": 0.0})
        stats = self._usage_stats
        input_cost = (stats["input_tokens"] / 1_000_000) * model_pricing["input"]
        output_cost = (stats["output_tokens"] / 1_000_000) * model_pricing["output"]
        return input_cost + output_cost

    def call(self, system_prompt: str, user_prompt: str, json_mode: bool = True, task: Optional[LLMTask] = None, force_cloud: bool = False) -> str:
        """
        Execute an LLM call.
        """
        # Resolve provider and model (potentially with routing)
        if task is not None:
            from scrapewizard.llm.routing import RoutingPolicy
            provider_id, model = RoutingPolicy().route(task, self.config, force_cloud=force_cloud)
        else:
            provider_id = self.provider
            model = self.model

        provider = self._create_provider(provider_id)
        
        # Security redaction
        clean_user = SecurityManager.redact_text(user_prompt)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": clean_user}
        ]
        
        # Resolve JSON schema if task has one
        json_schema = None
        if json_mode and task is not None:
            from scrapewizard.llm.schemas import TASK_SCHEMAS
            json_schema = TASK_SCHEMAS.get(task)
            
        try:
            response = provider.call(
                messages=messages,
                model=model,
                temperature=0.1,
                json_schema=json_schema
            )
            
            # Track Usage
            LLMClient._usage_stats["input_tokens"] += response.input_tokens
            LLMClient._usage_stats["output_tokens"] += response.output_tokens
            LLMClient._usage_stats["calls"] += 1

            content = response.content
            if not content:
                log("LLM returned empty content.", level="warning")
                return "{}" if json_mode else ""
            return content
        except Exception as e:
            error_msg = str(e).lower()
            is_bad_request = "badrequesterror" in type(e).__name__.lower() or "400" in error_msg
            is_json_mode_error = "response_format" in error_msg or "json_schema" in error_msg
            
            if "authenticationerror" in type(e).__name__.lower():
                log(f"Authentication failed for {provider_id} ({model}). Check API key.", level="error")
            elif (is_bad_request or is_json_mode_error) and json_mode:
                log(f"LLM Provider {provider_id} rejected JSON mode/schema. Retrying as plain text...", level="warning")
                return self.call(system_prompt, user_prompt, json_mode=False, task=task, force_cloud=force_cloud)
            else:
                log(f"LLM Call failed ({model}): {type(e).__name__}: {e}", level="error")
            raise

    def parse_json(self, content: str) -> Dict[str, Any]:
        """Clean and parse JSON from LLM response with deep robustness."""
        if not content or not isinstance(content, str):
            return {}
            
        try:
            # 1. Clean whitespace
            cleaned = content.strip()
            
            # 2. Extract from markdown fences if present
            import re
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
            if fence_match:
                cleaned = fence_match.group(1).strip()
            
            # 3. Aggressive isolation: Find FIRST { and LAST }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            
            if start != -1 and end != -1:
                json_candidate = cleaned[start:end+1]
                try:
                    return json.loads(json_candidate)
                except json.JSONDecodeError:
                    # If direct slice failed, try finding balanced braces (harder)
                    pass
            
            # 4. Fallback: direct parse (maybe it's already pure JSON)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
                
            # 5. Last resort: If we're here, we failed to find valid JSON
            log(f"Final fallback failed to parse JSON from: {content[:100]}...", level="debug")
            return {}
            
        except Exception as e:
            log(f"Critical error in parse_json: {e}", level="error")
            return {}

    @staticmethod
    def extract_python_code(text: str) -> str:
        """
        Extract Python code from LLM response, handling markdown fences 
        and preamble text robustly.
        """
        import re
        # Try to find code in markdown fence
        pattern = r"```(?:python)?\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)
        if matches:
            # Return the longest match (likely the full script)
            code = max(matches, key=len)
            return code.strip()
        
        # If no fence, try to find where code actually starts
        lines = text.split('\n')
        code_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ', 'class ', 'def ', 'async def ', '#!')):
                code_start = i
                break
        
        code = '\n'.join(lines[code_start:])
        code = code.strip()
        
        # Post-extraction fixes for common LLM hallucinations
        code = re.sub(r'from\s+scrapewizard\.runtime\b', 'from scrapewizard_runtime', code, flags=re.IGNORECASE)
        code = re.sub(r'\bfrom\s+async_playwright\.async_api\b', 'from playwright.async_api', code, flags=re.IGNORECASE)
        code = re.sub(r'\bfrom\s+async_playwright\b', 'from playwright.async_api', code, flags=re.IGNORECASE)
        code = re.sub(r'\bimport\s+async_playwright\b', 'from playwright.async_api import async_playwright', code, flags=re.IGNORECASE)
        code = re.sub(r'from\s+playwright\.async_api\s+import\s+async_playwright\.async_api', 'from playwright.async_api import async_playwright', code, flags=re.IGNORECASE)
        code = re.sub(r'import\s+playwright\.async_api', 'from playwright.async_api import async_playwright', code, flags=re.IGNORECASE)
        code = re.sub(r'\basync_playwright\.async_api\b', 'playwright.async_api', code, flags=re.IGNORECASE)
        code = re.sub(r'\basync_playwright\b', 'playwright.async_api', code, flags=re.IGNORECASE)
        code = re.sub(r'playwright\.async_api\.async_playwright', 'async_playwright', code, flags=re.IGNORECASE)

        return code
