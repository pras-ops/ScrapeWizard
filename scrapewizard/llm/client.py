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

    def _setup_client(self):
        if not self.api_key and self.provider != "local":
            log("API Key missing for LLM client.", level="warning")
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
            log("OpenAI package not installed. Please install it.", level="error")

    def call(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """
        Execute an LLM call.
        """
        if not self.client:
            raise RuntimeError("LLM Client not initialized.")

        # Security redaction
        clean_user = SecurityManager.redact_text(user_prompt)
        
        # Wizard mode: hidden

        
        # log(f"Calling LLM...")
        
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
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content
        except Exception as e:
            log(f"LLM Call failed: {e}", level="error")
            raise

    def parse_json(self, content: str) -> Dict:
        """Clean and parse JSON from LLM response."""
        try:
            # simple cleanup for Markdown fences
            cleaned = content.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            log(f"Failed to parse LLM JSON: {e}", level="error")
            raise
