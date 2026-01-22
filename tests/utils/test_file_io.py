import pytest
import json
from pathlib import Path
from unittest.mock import patch
from scrapewizard.utils.file_io import safe_read_json, safe_write_json

def test_safe_read_json_success(tmp_path):
    f = tmp_path / "test.json"
    data = {"hello": "world"}
    f.write_text(json.dumps(data))
    assert safe_read_json(f) == data

def test_safe_read_json_missing(tmp_path):
    f = tmp_path / "missing.json"
    assert safe_read_json(f, default={"def": 1}) == {"def": 1}

def test_safe_read_json_corrupt(tmp_path):
    f = tmp_path / "corrupt.json"
    f.write_text("{invalid")
    assert safe_read_json(f, default={}) == {}

def test_safe_write_json_success(tmp_path):
    f = tmp_path / "subdir" / "output.json"
    data = {"key": "val"}
    assert safe_write_json(f, data) is True
    assert f.exists()
    assert json.loads(f.read_text()) == data

@patch("pathlib.Path.write_text")
def test_safe_write_json_permission_error(mock_write, tmp_path):
    mock_write.side_effect = PermissionError("Denied")
    f = tmp_path / "locked.json"
    # Should log error and return False or raise if re-raised
    # According to our implementation, it logs and returns False or raises depending on the catch
    # Let's check the implementation: safe_write_json raises on Exception but catches PermissionError and logs.
    # Wait, in the implementation I wrote it catches PermissionError and returns False.
    assert safe_write_json(f, {"test": 1}) is False
