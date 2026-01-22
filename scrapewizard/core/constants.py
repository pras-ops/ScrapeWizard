from typing import Dict

# Timeouts (in seconds)
DEFAULT_BROWSER_TIMEOUT = 60
DEFAULT_SCRIPT_TIMEOUT = 120
PROBE_NAVIGATION_TIMEOUT = 30
SCAN_NAVIGATION_TIMEOUT = 45

# LLM Thresholds
LLM_CONFIDENCE_THRESHOLD = 0.5
SCRAPING_POSSIBLE_MIN_CONFIDENCE = 0.4

# Browser Settings
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
HOSTILE_SITE_HOSTILITY_THRESHOLD = 40

# Resource Limits
MAX_INFINITE_SCROLL_INTERACTIONS = 50
MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# State Mapping
STATE_EMOJIS = {
    "INIT": "🔍",
    "RECON": "🧠",
    "LLM_ANALYSIS": "⚙️",
    "USER_CONFIG": "📋",
    "CODEGEN": "🛠️",
    "TEST": "🧪",
    "REPAIR": "🩺",
    "APPROVED": "🚀",
    "FINAL_RUN": "📈",
    "DONE": "✅",
    "FAILED": "❌"
}
