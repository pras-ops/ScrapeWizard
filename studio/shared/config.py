from pathlib import Path
from typing import Dict, Any
from scrapewizard.core.config import ConfigManager
from scrapewizard.utils.file_io import safe_read_json

class StudioConfig:
    """Extension of ScrapeWizard configuration for Studio-specific overrides."""
    
    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Load global config and apply .scrapewizardrc overrides for Studio."""
        # Get base config from core (Frozen)
        config = ConfigManager.load_config()
        
        # Apply local overrides (.scrapewizardrc or scrapewizard.json)
        # These are only loaded when running through the Studio bridge
        for local_file in [".scrapewizardrc", "scrapewizard.json"]:
            local_path = Path.cwd() / local_file
            if local_path.exists():
                local_config = safe_read_json(local_path, default={})
                config.update(local_config)
                # Ensure API key is refreshed if provider/key changed locally
                # Note: core ConfigManager.get_api_key uses keyring
                if "provider" in local_config:
                    provider = config.get("provider", "openai")
                    config["api_key"] = ConfigManager.get_api_key(provider) or ""
                break
        
        return config
