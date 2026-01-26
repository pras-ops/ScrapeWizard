import json
from typing import Dict, Any, Optional
from scrapewizard.core.config import ConfigManager
from scrapewizard.core.logging import log
from scrapewizard.utils.security import SecurityManager

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
    }

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        self.config = ConfigManager.load_config()
        self.provider = provider or self.config.get("provider", "openai")
        self.api_key = api_key or self.config.get("api_key")
        self.model = model or self.config.get("model", "gpt-4-turbo")
        self.client = None
        
        self._setup_client()

    def _setup_client(self) -> None:
        if not self.api_key and self.provider != "local":
            log("API Key missing or redacted for LLM client.", level="warning")
            return

        try:
            if self.provider == "anthropic":
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                log(f"Initialized Anthropic client with model: {self.model}")
                return

            import openai
            base_url = None
            if self.provider == "openrouter":
                base_url = "https://openrouter.ai/api/v1"
            elif self.provider == "local":
                base_url = "http://localhost:11434/v1" # Default Ollama
                self.api_key = "ollama" # Dummy key
                
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
        except ImportError as e:
            pkg = "anthropic" if self.provider == "anthropic" else "openai"
            log(f"{pkg} package not installed. Run 'pip install {pkg}'.", level="error")

    @classmethod
    def get_usage_stats(cls) -> Dict[str, Any]:
        """Get the global usage statistics."""
        return cls._usage_stats

    def get_estimated_cost(self) -> float:
        """Calculate estimated cost based on tracked usage."""
        model_pricing = self.PRICING.get(self.model, {"input": 0, "output": 0})
        stats = self._usage_stats
        input_cost = (stats["input_tokens"] / 1_000_000) * model_pricing["input"]
        output_cost = (stats["output_tokens"] / 1_000_000) * model_pricing["output"]
        return input_cost + output_cost

    def call(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """
        Execute an LLM call.
        """
        if not self.client:
            raise RuntimeError("LLM Client not initialized. Check API Key.")

        # Security redaction
        clean_user = SecurityManager.redact_text(user_prompt)
        
        # Determine if we should attempt JSON mode
        use_json_mode = json_mode and self.provider in ["openai", "openrouter", "local"]
        
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_user}
            ],
            "temperature": 0.1,
        }
        
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            
            # Track Usage
            if hasattr(response, 'usage') and response.usage:
                LLMClient._usage_stats["input_tokens"] += getattr(response.usage, 'prompt_tokens', 0)
                LLMClient._usage_stats["output_tokens"] += getattr(response.usage, 'completion_tokens', 0)
                LLMClient._usage_stats["calls"] += 1

            content = response.choices[0].message.content
            if not content:
                log("LLM returned empty content.", level="warning")
                return "{}" if json_mode else ""
            return content
        except Exception as e:
            error_msg = str(e).lower()
            # Broad check for JSON mode rejection (OpenRouter, older models, etc.)
            is_bad_request = "badrequesterror" in type(e).__name__.lower() or "400" in error_msg
            is_json_mode_error = "response_format" in error_msg or "json_object" in error_msg
            
            if "authenticationerror" in type(e).__name__.lower():
                log(f"Authentication failed for {self.provider} ({self.model}). Check API key.", level="error")
            elif (is_bad_request or is_json_mode_error) and json_mode:
                log(f"LLM Provider {self.provider} rejected JSON mode. Retrying as plain text...", level="warning")
                return self.call(system_prompt, user_prompt, json_mode=False)
            else:
                log(f"LLM Call failed ({self.model}): {type(e).__name__}: {e}", level="error")
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
                    # For now just log and move to step 4
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
