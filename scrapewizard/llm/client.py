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
    
    def __init__(self):
        self.config = ConfigManager.load_config()
        self.provider = self.config.get("provider", "openai")
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model", "gpt-4-turbo")
        self.client = None
        
        self._setup_client()

    def _setup_client(self) -> None:
        if not self.api_key and self.provider != "local":
            log("API Key missing or redacted for LLM client.", level="warning")
            return

        try:
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
        except ImportError:
            log("OpenAI package not installed. Run 'pip install openai'.", level="error")

    def call(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """
        Execute an LLM call.
        """
        if not self.client:
            raise RuntimeError("LLM Client not initialized. Check API Key.")

        # Security redaction
        clean_user = SecurityManager.redact_text(user_prompt)
        
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_user}
            ],
            "temperature": 0.1,
        }
        
        if json_mode and self.provider in ["openai", "openrouter", "local"]:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            import openai
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content
        except Exception as e:
            if "AuthenticationError" in type(e).__name__:
                log(f"Authentication failed for {self.provider} ({self.model}). Please check your API key with 'scrapewizard auth <key>'.", level="error")
            elif "BadRequestError" in type(e).__name__ and json_mode:
                log(f"LLM Provider {self.provider} doesn't support JSON mode. Retrying as plain text...", level="warning")
                return self.call(system_prompt, user_prompt, json_mode=False)
            else:
                log(f"LLM Call failed ({self.model}): {type(e).__name__}: {e}", level="error")
            raise

    def parse_json(self, content: str) -> Dict[str, Any]:
        """Clean and parse JSON from LLM response with robustness."""
        try:
            # 1. Clean whitespace and non-printable chars
            cleaned = content.strip()
            
            # 2. Strip Markdown code blocks if present
            if cleaned.startswith("```"):
                # Use regex to extract content from the first code block
                import re
                match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
                if match:
                    cleaned = match.group(1).strip()
            
            # 3. Find first { and last } to isolate JSON object
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
                
            if not cleaned:
                return {}
                
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            import traceback
            log(f"Failed to parse LLM JSON: {e}", level="error")
            log(f"Raw Content: {content[:200]}...", level="debug")
            log(f"Cleaned Content: {cleaned[:200]}...", level="debug")
            log(f"Parse Traceback: {traceback.format_exc()}", level="debug")
            return {}
        except Exception as e:
            log(f"Unexpected error parsing LLM JSON: {e}", level="error")
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
