import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from scrapewizard.core.config import ConfigManager

def test_validate_url_valid():
    assert ConfigManager.validate_url("https://example.com") == "https://example.com"
    assert ConfigManager.validate_url("http://localhost:8080/test") == "http://localhost:8080/test"

def test_validate_url_invalid():
    with pytest.raises(ValueError):
        ConfigManager.validate_url("ftp://example.com")
    with pytest.raises(ValueError):
        ConfigManager.validate_url("example.com")
    with pytest.raises(ValueError):
        ConfigManager.validate_url("not-a-url")

@patch("keyring.set_password")
@patch("keyring.get_password")
def test_keyring_storage(mock_get, mock_set):
    mock_get.return_value = "secret-key"
    
    ConfigManager.save_api_key("openai", "secret-key")
    mock_set.assert_called_with(ConfigManager.SERVICE_NAME, "openai_api_key", "secret-key")
    
    assert ConfigManager.get_api_key("openai") == "secret-key"
    mock_get.assert_called_with(ConfigManager.SERVICE_NAME, "openai_api_key")

def test_migration_logic(tmp_path):
    # Setup temp config file
    config_dir = tmp_path / ".scrapewizard"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    
    old_data = {
        "provider": "anthropic",
        "api_key": "old-plain-key",
        "model": "claude-3"
    }
    config_file.write_text(json.dumps(old_data))
    
    # Mock ConfigManager paths
    with patch.object(ConfigManager, "CONFIG_FILE", config_file):
        with patch("keyring.set_password") as mock_set:
            ConfigManager.migrate_from_plaintext()
            
            # Verify keyring was set
            mock_set.assert_called_with(ConfigManager.SERVICE_NAME, "anthropic_api_key", "old-plain-key")
            
            # Verify file was cleaned
            new_data = json.loads(config_file.read_text())
            assert "api_key" not in new_data
            assert new_data["provider"] == "anthropic"
            assert new_data["model"] == "claude-3"
