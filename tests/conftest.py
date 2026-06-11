import socket
import threading
import time
import pytest
import uvicorn
from scrapewizard.demo_app.app import app

def get_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def demo_server():
    """Starts the FastAPI demo app in a background thread."""
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    
    # Wait for server to boot
    time.sleep(1.0)
    
    yield f"http://127.0.0.1:{port}"
    
    server.should_exit = True
    thread.join(timeout=2.0)
