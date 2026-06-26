import pytest
from unittest.mock import patch, MagicMock
import httpx
from scrapewizard.llm.local_runtime import LocalRuntime, DaemonStatus, ProbeResult

class TestLocalRuntime:
    @patch('os.sysconf')
    @patch('subprocess.run')
    def test_detect_hardware_balanced(self, mock_run, mock_sysconf):
        # Mock 12 GB RAM on Unix
        mock_sysconf.side_effect = lambda param: 4096 if "PAGE_SIZE" in param else 3145728 # 4096 * 3145728 = 12 GB
        
        # Mock GPU check
        mock_gpu = MagicMock()
        mock_gpu.stdout = "Apple M2"
        mock_run.return_value = mock_gpu

        runtime = LocalRuntime()
        with patch('platform.system', return_value="Darwin"):
            hw = runtime.detect_hardware()
            assert hw["tier"] == "balanced"
            assert hw["ram_gb"] == 12.0
            assert "M2" in hw["gpu_name"]

    @patch('httpx.get')
    def test_check_daemon_running(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "0.1.48"}
        mock_get.return_value = mock_resp

        runtime = LocalRuntime()
        status = runtime.check_daemon()
        assert status.running is True
        assert status.version == "0.1.48"

    @patch('httpx.get')
    def test_check_daemon_down(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        runtime = LocalRuntime()
        status = runtime.check_daemon()
        assert status.running is False

    @patch('httpx.get')
    def test_list_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5-coder:3b"},
                {"name": "llama3:latest"}
            ]
        }
        mock_get.return_value = mock_resp

        runtime = LocalRuntime()
        models = runtime.list_models()
        assert models == ["qwen2.5-coder:3b", "llama3:latest"]

    @patch('httpx.post')
    def test_probe_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        runtime = LocalRuntime()
        res = runtime.probe("qwen2.5-coder:3b")
        assert res.success is True
        assert res.latency >= 0.0

    @patch('httpx.post')
    def test_probe_failure(self, mock_post):
        mock_post.side_effect = httpx.TimeoutException("Read timed out")

        runtime = LocalRuntime()
        res = runtime.probe("qwen2.5-coder:3b")
        assert res.success is False
        assert "timed out" in res.error
