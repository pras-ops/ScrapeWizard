import os
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from scrapewizard.core.config import ConfigManager


class MemoryKeyring(KeyringBackend):
    """Stand-in for the OS keyring, which CI runners and containers don't have."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords = {}

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def delete_password(self, service, username):
        self.passwords.pop((service, username), None)


@pytest.fixture
def memory_keyring():
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    yield
    keyring.set_keyring(previous)

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

def test_save_config(memory_keyring):
    ConfigManager.CONFIG_FILE = Path("test_save_config.json")
    
    new_conf = {"provider": "local", "api_key": "xyz"}
    ConfigManager.save_config(new_conf)
    
    loaded = ConfigManager.load_config()
    assert loaded["provider"] == "local"
    assert loaded["api_key"] == "xyz"
    
    os.remove(ConfigManager.CONFIG_FILE)
