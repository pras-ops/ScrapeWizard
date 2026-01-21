import re
from typing import Dict, Any

class SecurityManager:
    """
    Handles redaction of sensitive data before sending to LLMs or logging.
    """
    
    PATTERNS = {
        "api_key": r"sk-[a-zA-Z0-9]{32,}",
        "password": r"password=[\w!@#$%^&*()]+",
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "auth_token": r"Bearer [a-zA-Z0-9\._-]+"
    }

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Redact known sensitive patterns from text."""
        if not text: return text
        
        redacted = text
        for name, pattern in cls.PATTERNS.items():
            redacted = re.sub(pattern, f"[REDACTED_{name.upper()}]", redacted)
        return redacted

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact dictionary values."""
        new_data = {}
        for k, v in data.items():
            if isinstance(v, str):
                if k.lower() in ['password', 'secret', 'token', 'key']:
                    new_data[k] = "[REDACTED]"
                else:
                    new_data[k] = cls.redact_text(v)
            elif isinstance(v, dict):
                new_data[k] = cls.redact_dict(v)
            elif isinstance(v, list):
                new_data[k] = [cls.redact_dict(i) if isinstance(i, dict) else i for i in v]
            else:
                new_data[k] = v
        return new_data
