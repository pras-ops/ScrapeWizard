import os
from pathlib import Path
from scrapewizard.core.config import ConfigManager

def test_config_load_defaults():
    # Mock config file path to avoid reading real user config
    ConfigManager.CONFIG_FILE = Path("test_config.json")
    if ConfigManager.CONFIG_FILE.exists():
        os.remove(ConfigManager.CONFIG_FILE)
        
    config = ConfigManager.load_config()
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4-turbo"
    
    # Clean up
    if ConfigManager.CONFIG_FILE.exists():
        os.remove(ConfigManager.CONFIG_FILE)

def test_save_config():
    ConfigManager.CONFIG_FILE = Path("test_save_config.json")
    
    new_conf = {"provider": "local", "api_key": "xyz"}
    ConfigManager.save_config(new_conf)
    
    loaded = ConfigManager.load_config()
    assert loaded["provider"] == "local"
    assert loaded["api_key"] == "xyz"
    
    os.remove(ConfigManager.CONFIG_FILE)
