import json
import re
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
import keyring
from keyring.errors import KeyringError
from urllib.parse import urlparse

from scrapewizard.core.logging import log
from scrapewizard.utils.file_io import safe_read_json, safe_write_json

class ConfigManager:
    """Manages global configuration for ScrapeWizard with secure key storage."""
    
    APP_NAME = "scrapewizard"
    CONFIG_DIR = Path.home() / f".{APP_NAME}"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROXY_FILE = CONFIG_DIR / "proxy.json"
    SERVICE_NAME = "scrapewizard"

    DEFAULT_CONFIG = {
        "provider": "openai",
        "model": "gpt-4-turbo"
    }

    @classmethod
    def _key_name(cls, provider: str) -> str:
        return f"{provider}_api_key"

    @classmethod
    def ensure_config_dir(cls):
        """Ensure configuration directory exists."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def migrate_from_plaintext(cls):
        """Migrate API keys from plain config.json to system keyring."""
        if not cls.CONFIG_FILE.exists():
            return
        
        try:
            data = safe_read_json(cls.CONFIG_FILE)
            migrated = False
            
            # Pattern 1: Generic 'api_key' field
            if "api_key" in data and data["api_key"]:
                provider = data.get("provider", "openai")
                cls.save_api_key(provider, data["api_key"])
                del data["api_key"]
                migrated = True
                
            # Pattern 2: Provider-specific keys
            for provider in ["openai", "anthropic", "openrouter", "local"]:
                if provider in data and isinstance(data[provider], dict) and "api_key" in data[provider]:
                    cls.save_api_key(provider, data[provider]["api_key"])
                    del data[provider]["api_key"]
                    migrated = True
            
            if migrated:
                safe_write_json(cls.CONFIG_FILE, data)
                log("API keys successfully migrated to system keyring.", level="info")
        except Exception as e:
            log(f"Migration from plaintext failed: {e}", level="warning")

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Load global configuration, fetching API key from keyring."""
        # Always attempt migration first
        cls.migrate_from_plaintext()
        
        config = cls.DEFAULT_CONFIG.copy()
        file_config = safe_read_json(cls.CONFIG_FILE, default=cls.DEFAULT_CONFIG)
        config.update(file_config)
        
        # Securely fetch API key for current provider
        provider = config.get("provider", "openai")
        config["api_key"] = cls.get_api_key(provider) or ""
        
        return config

    @classmethod
    def save_config(cls, config: Dict[str, Any]):
        """Save global configuration, storing API key securely in keyring."""
        cls.ensure_config_dir()
        
        # Extract and save API key to keyring
        if "api_key" in config:
            provider = config.get("provider", "openai")
            api_key = config.pop("api_key")
            if api_key:
                cls.save_api_key(provider, api_key)
        
        safe_write_json(cls.CONFIG_FILE, config)

    @classmethod
    def save_api_key(cls, provider: str, api_key: str):
        """Store an API key securely."""
        try:
            keyring.set_password(cls.SERVICE_NAME, cls._key_name(provider), api_key)
        except KeyringError as e:
            log(f"Keyring save failed for {provider}: {e}", level="error")

    @classmethod
    def get_api_key(cls, provider: str) -> Optional[str]:
        """Retrieve an API key securely."""
        try:
            return keyring.get_password(cls.SERVICE_NAME, cls._key_name(provider))
        except KeyringError as e:
            log(f"Keyring retrieval failed for {provider}: {e}", level="error")
            return None

    @staticmethod
    def validate_url(url: str) -> str:
        """Robust URL validation using urllib.parse."""
        try:
            parsed = urlparse(url)
            if not (parsed.scheme in ("http", "https") and parsed.netloc):
                raise ValueError(f"Invalid URL: '{url}' - Must be http/https with a valid domain.")
            return url
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"URL parsing failed: {e}")

    @classmethod
    def load_proxy(cls) -> Dict[str, Any]:
        """Load global proxy settings."""
        return safe_read_json(cls.PROXY_FILE)
            
    @classmethod
    def save_proxy(cls, proxy_config: Dict[str, Any]):
        """Save global proxy settings."""
        cls.ensure_config_dir()
        safe_write_json(cls.PROXY_FILE, proxy_config)

    @classmethod
    def check_setup(cls) -> bool:
        """Check if essential configuration (API key) is set."""
        config = cls.load_config()
        return bool(config.get("api_key"))
