from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from studio.backend.deps import get_session
from studio.backend.models import Setting
from scrapewizard.core.config import ConfigManager
from scrapewizard.llm.client import LLMClient

router = APIRouter(prefix="/settings", tags=["Settings"])

class SettingsUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    visual_threshold: Optional[float] = None
    retention: Optional[int] = None
    ai_mode: Optional[str] = None

@router.get("")
def get_settings(db: Session = Depends(get_session)):
    """Fetch global LLM configuration and visual runner thresholds."""
    config = ConfigManager.load_config()
    
    db_settings = {}
    for key in ["provider", "model", "visual_threshold", "retention", "ai_mode"]:
        setting = db.get(Setting, key)
        if setting:
            db_settings[key] = setting.value
            
    visual_threshold = float(db_settings.get("visual_threshold", 0.05))
    retention = int(db_settings.get("retention", 10))
    ai_mode = db_settings.get("ai_mode", "Creation")
    provider = db_settings.get("provider", config.get("provider", "openai"))
    model = db_settings.get("model", config.get("model", "gpt-4-turbo"))
    
    # Retrieve API key for key presence check only (never echo value to frontend)
    api_key = ConfigManager.get_api_key(provider) or ""
    has_key = bool(api_key)
    
    return {
        "provider": provider,
        "model": model,
        "ai_mode": ai_mode,
        "has_key": has_key,
        "visual_threshold": visual_threshold,
        "retention": retention
    }

@router.put("")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_session)):
    """Update configurations and store the API Key securely in system keyring."""
    fields_to_save = {
        "provider": payload.provider,
        "model": payload.model,
        "ai_mode": payload.ai_mode,
        "visual_threshold": str(payload.visual_threshold) if payload.visual_threshold is not None else None,
        "retention": str(payload.retention) if payload.retention is not None else None
    }
    
    for k, v in fields_to_save.items():
        if v is not None:
            setting = db.get(Setting, k)
            if setting:
                setting.value = v
            else:
                setting = Setting(key=k, value=v)
                db.add(setting)
    
    provider = payload.provider
    if not provider:
        prov_setting = db.get(Setting, "provider")
        provider = prov_setting.value if prov_setting else "openai"
        
    if payload.api_key is not None:
        ConfigManager.save_api_key(provider, payload.api_key)
        
    db.commit()
    return {"status": "success", "message": "Settings updated successfully"}

class TestConnectionRequest(BaseModel):
    provider: str
    model: str
    api_key: str

@router.post("/test-connection")
def test_connection(payload: TestConnectionRequest):
    """Securely check connectivity of the chosen LLM provider."""
    try:
        key = payload.api_key
        if payload.provider == "local" and not key:
            key = "ollama"
            
        client = LLMClient(provider=payload.provider, api_key=key, model=payload.model)
        
        # Run a tiny completion probe
        probe = client.call(
            system_prompt="You are a connection checking assistant.",
            user_prompt="Respond with a JSON object containing single key 'status' with value 'ok'",
            json_mode=True
        )
        
        parsed = client.parse_json(probe)
        if parsed.get("status") == "ok" or parsed:
            return {"ok": True, "message": "Connection test passed successfully."}
        else:
            return {"ok": False, "message": f"Connection test failed to parse response: {probe}"}
            
    except Exception as e:
        return {"ok": False, "message": f"LLM connection test failed: {e}"}
