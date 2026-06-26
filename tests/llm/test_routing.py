import pytest
from unittest.mock import patch
from scrapewizard.llm.routing import RoutingPolicy, LLMTask

class TestRoutingPolicy:
    def test_explicit_cloud_provider(self):
        policy = RoutingPolicy()
        config = {
            "provider": "openai",
            "model": "gpt-4-turbo"
        }
        provider, model = policy.route(LLMTask.UNDERSTAND, config)
        assert provider == "openai"
        assert model == "gpt-4-turbo"

    @patch('scrapewizard.core.config.ConfigManager.get_api_key')
    def test_understand_routes_to_local(self, mock_get_key):
        mock_get_key.return_value = "fake-openai-key"
        policy = RoutingPolicy()
        config = {
            "provider": "local",
            "local_model": "qwen2.5-coder:3b",
            "offline_only": False
        }
        provider, model = policy.route(LLMTask.UNDERSTAND, config)
        assert provider == "local"
        assert model == "qwen2.5-coder:3b"

    @patch('scrapewizard.core.config.ConfigManager.get_api_key')
    def test_codegen_routes_to_local_when_no_cloud_key(self, mock_get_key):
        # No keys available
        mock_get_key.return_value = None
        policy = RoutingPolicy()
        config = {
            "provider": "local",
            "local_model": "qwen2.5-coder:3b",
            "offline_only": False
        }
        provider, model = policy.route(LLMTask.CODEGEN, config)
        assert provider == "local"
        assert model == "qwen2.5-coder:3b"

    @patch('scrapewizard.core.config.ConfigManager.get_api_key')
    def test_codegen_falls_back_to_cloud_when_key_exists(self, mock_get_key):
        # Mock OpenAI API key exists
        def get_api_key_side_effect(provider_id):
            if provider_id == "openai":
                return "fake-openai-key"
            return None
        mock_get_key.side_effect = get_api_key_side_effect
        
        policy = RoutingPolicy()
        config = {
            "provider": "local",
            "local_model": "qwen2.5-coder:3b",
            "offline_only": False
        }
        provider, model = policy.route(LLMTask.CODEGEN, config)
        assert provider == "openai"
        assert model == "gpt-4-turbo"

    @patch('scrapewizard.core.config.ConfigManager.get_api_key')
    def test_offline_only_mode_never_routes_to_cloud(self, mock_get_key):
        mock_get_key.return_value = "fake-openai-key"
        policy = RoutingPolicy()
        config = {
            "provider": "local",
            "local_model": "qwen2.5-coder:3b",
            "offline_only": True
        }
        provider, model = policy.route(LLMTask.CODEGEN, config)
        assert provider == "local"
        assert model == "qwen2.5-coder:3b"

    @patch('scrapewizard.core.config.ConfigManager.get_api_key')
    def test_force_cloud_without_key_stays_local(self, mock_get_key):
        mock_get_key.return_value = None
        policy = RoutingPolicy()
        config = {
            "provider": "local",
            "local_model": "qwen2.5-coder:3b",
            "offline_only": False
        }
        provider, model = policy.route(LLMTask.UNDERSTAND, config, force_cloud=True)
        assert provider == "local"
        assert model == "qwen2.5-coder:3b"
