import os
import platform
import subprocess
import json
import time
import httpx
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
from scrapewizard.core.logging import log

@dataclass
class DaemonStatus:
    running: bool
    version: Optional[str] = None

@dataclass
class ProbeResult:
    success: bool
    latency: float = 0.0
    error: Optional[str] = None


class LocalRuntime:
    """Manages the local Ollama runtime lifecycle and model management."""

    def __init__(self, base_url: Optional[str] = None):
        # Read from config or default to localhost:11434
        from scrapewizard.core.config import ConfigManager
        config = ConfigManager.load_config()
        self.base_url = (base_url or config.get("local_base_url", "http://localhost:11434")).rstrip("/")

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect hardware capabilities and suggest a performance tier.
        
        Tiers:
        - Tiny: < 8 GB RAM
        - Balanced: 8 - 16 GB RAM
        - Power: > 16 GB RAM
        """
        ram_gb = 8.0
        try:
            # Unix-based RAM check
            ram_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
            ram_gb = ram_bytes / (1024 ** 3)
        except (AttributeError, ValueError, OSError):
            # Fallback to sysctl on Mac
            if platform.system() == "Darwin":
                try:
                    res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
                    ram_gb = int(res.stdout.strip()) / (1024 ** 3)
                except Exception:
                    pass
            # Fallback for Windows
            elif platform.system() == "Windows":
                try:
                    res = subprocess.run(["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"], capture_output=True, text=True)
                    lines = res.stdout.strip().split("\n")
                    if len(lines) > 1:
                        ram_gb = int(lines[1].strip()) / (1024 ** 3)
                except Exception:
                    pass

        # GPU detection
        gpu_name = "CPU Only"
        if platform.system() == "Darwin":
            try:
                res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
                gpu_name = f"{res.stdout.strip()}"
            except Exception:
                gpu_name = "Apple Silicon GPU"
        else:
            # Check for nvidia-smi
            import shutil
            if shutil.which("nvidia-smi"):
                try:
                    res = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
                    gpu_name = res.stdout.strip()
                except Exception:
                    gpu_name = "NVIDIA CUDA GPU"

        # Determine tier
        if ram_gb < 8.0:
            tier = "tiny"
        elif ram_gb < 16.0:
            tier = "balanced"
        else:
            tier = "power"

        return {
            "tier": tier,
            "ram_gb": round(ram_gb, 1),
            "gpu_name": gpu_name
        }

    def check_daemon(self) -> DaemonStatus:
        """Check if the Ollama daemon is running and return its version."""
        url = f"{self.base_url}/api/version"
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code == 200:
                ver = resp.json().get("version", "unknown")
                return DaemonStatus(running=True, version=ver)
            return DaemonStatus(running=True, version="unknown")
        except Exception:
            # Fallback check on tags endpoint
            try:
                resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
                if resp.status_code == 200:
                    return DaemonStatus(running=True, version="unknown")
            except Exception:
                pass
            return DaemonStatus(running=False)

    def list_models(self) -> List[str]:
        """List all downloaded/installed models in Ollama."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [m["name"] for m in models]
        except Exception as e:
            log(f"Failed to query Ollama models: {e}", level="warning")
        return []

    def pull_model(self, model: str, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
        """Pull a model from the Ollama library, yielding status updates."""
        url = f"{self.base_url}/api/pull"
        payload = {"name": model, "stream": True}
        try:
            with httpx.stream("POST", url, json=payload, timeout=None) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if progress_callback:
                            progress_callback(data)
                    except Exception:
                        pass
            return True
        except Exception as e:
            log(f"Failed to pull model '{model}': {e}", level="error")
            return False

    def probe(self, model: str, timeout: float = 15.0) -> ProbeResult:
        """Run a tiny completion to measure response latency and check model sanity."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "say ok"}],
            "stream": False
        }
        start_time = time.time()
        try:
            resp = httpx.post(url, json=payload, timeout=timeout)
            latency = time.time() - start_time
            if resp.status_code == 200:
                return ProbeResult(success=True, latency=round(latency, 2))
            return ProbeResult(success=False, error=f"Ollama returned status code {resp.status_code}")
        except Exception as e:
            return ProbeResult(success=False, error=str(e))

    def recommend_model(self, tier: str) -> str:
        """Recommend a model based on the hardware tier."""
        if tier == "tiny":
            return "qwen2.5:1.5b"
        elif tier == "balanced":
            return "qwen2.5-coder:3b"
        else:
            return "qwen2.5-coder:7b"
