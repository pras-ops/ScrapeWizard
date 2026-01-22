import pytest
import json
from scrapewizard.llm.client import LLMClient

def test_parse_json_basic():
    client = LLMClient()
    raw = '{"fields": ["title", "price"]}'
    assert client.parse_json(raw) == {"fields": ["title", "price"]}

def test_parse_json_markdown():
    client = LLMClient()
    raw = "```json\n{'fields': ['title']}\n```"
    # Note: LLM usually provides double quotes, but let's test the stripping
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
