import sys
from unittest.mock import MagicMock, patch
# Mock anthropic module to avoid import issues
sys.modules['anthropic'] = MagicMock()

import pytest
import json
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.routing import LLMTask

def test_parse_json_basic():
    client = LLMClient()
    raw = '{"fields": ["title", "price"]}'
    assert client.parse_json(raw) == {"fields": ["title", "price"]}

def test_parse_json_markdown():
    client = LLMClient()
    raw = "```json\n{'fields': ['title']}\n```"
    raw_valid = "```json\n{\"fields\": [\"title\"]}\n```"
    assert client.parse_json(raw_valid) == {"fields": ["title"]}

def test_parse_json_with_preamble():
    client = LLMClient()
    raw = "Here is the data: {\"id\": 123} Hope this helps!"
    assert client.parse_json(raw) == {"id": 123}

def test_parse_json_corrupt():
    client = LLMClient()
    raw = "{\"id\": 123" # Missing closing brace
    assert client.parse_json(raw) == {}

def test_parse_json_empty():
    client = LLMClient()
    assert client.parse_json("") == {}
    assert client.parse_json("   ") == {}

@patch('scrapewizard.llm.routing.RoutingPolicy.route')
@patch('scrapewizard.llm.providers.OllamaProvider.call')
def test_call_with_task_routes_correctly(mock_ollama_call, mock_route):
    from scrapewizard.llm.providers import ProviderResponse
    mock_route.return_value = ("local", "qwen2.5-coder:3b")
    mock_ollama_call.return_value = ProviderResponse(content="routed-content", input_tokens=10, output_tokens=15)

    client = LLMClient()
    # Reset usage stats
    LLMClient._usage_stats = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    
    res = client.call("sys", "user", json_mode=False, task=LLMTask.UNDERSTAND)
    
    assert res == "routed-content"
    assert LLMClient.get_usage_stats()["calls"] == 1
    assert LLMClient.get_usage_stats()["input_tokens"] == 10
    mock_route.assert_called_once()
    mock_ollama_call.assert_called_once()

def test_local_provider_cost_is_zero():
    client = LLMClient(provider="local")
    LLMClient._usage_stats = {"input_tokens": 10000, "output_tokens": 20000, "calls": 10}
    assert client.get_estimated_cost() == "$0 — runs locally"

@patch('anthropic.Anthropic')
def test_anthropic_provider_no_crash(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="anthropic-response")]
    mock_response.usage = MagicMock(input_tokens=12, output_tokens=18)
    mock_client.messages.create.return_value = mock_response

    client = LLMClient(provider="anthropic", api_key="anthropic-test-key", model="claude-3-5-sonnet")
    res = client.call("sys", "user", json_mode=False)
    
    assert res == "anthropic-response"
