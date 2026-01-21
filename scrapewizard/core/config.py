import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """Manages global configuration for ScrapeWizard."""
    
    APP_NAME = "scrapewizard"
    CONFIG_DIR = Path.home() / f".{APP_NAME}"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROXY_FILE = CONFIG_DIR / "proxy.json"

    DEFAULT_CONFIG = {
        "provider": "openai",
        "model": "gpt-4-turbo",
        "api_key": ""
    }

    @classmethod
    def ensure_config_dir(cls):
        """Ensure configuration directory exists."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Load global configuration."""
        if not cls.CONFIG_FILE.exists():
            return cls.DEFAULT_CONFIG.copy()
        
        try:
            with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def save_config(cls, config: Dict[str, Any]):
        """Save global configuration."""
        cls.ensure_config_dir()
        with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    @classmethod
    def load_proxy(cls) -> Dict[str, Any]:
        """Load global proxy settings."""
        if not cls.PROXY_FILE.exists():
            return {}
        try:
            with open(cls.PROXY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
            
    @classmethod
    def save_proxy(cls, proxy_config: Dict[str, Any]):
        """Save global proxy settings."""
        cls.ensure_config_dir()
        with open(cls.PROXY_FILE, "w", encoding="utf-8") as f:
            json.dump(proxy_config, f, indent=2)

    @classmethod
    def check_setup(cls) -> bool:
        """Check if essential configuration (API key) is set."""
        config = cls.load_config()
        return bool(config.get("api_key"))
