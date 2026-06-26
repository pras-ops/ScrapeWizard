from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import asyncio
import json

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
    local_base_url: Optional[str] = None
    local_model: Optional[str] = None
    offline_only: Optional[bool] = None

@router.get("")
def get_settings(db: Session = Depends(get_session)):
    """Fetch global LLM configuration and visual runner thresholds."""
    config = ConfigManager.load_config()
    
    db_settings = {}
    for key in ["provider", "model", "visual_threshold", "retention", "ai_mode", "local_base_url", "local_model", "offline_only"]:
        setting = db.get(Setting, key)
        if setting:
            db_settings[key] = setting.value
            
    visual_threshold = float(db_settings.get("visual_threshold", 0.05))
    retention = int(db_settings.get("retention", 10))
    ai_mode = db_settings.get("ai_mode", "Creation")
    provider = db_settings.get("provider", config.get("provider", "openai"))
    model = db_settings.get("model", config.get("model", "gpt-4-turbo"))
    local_base_url = db_settings.get("local_base_url", config.get("local_base_url", "http://localhost:11434"))
    local_model = db_settings.get("local_model", config.get("local_model", "qwen2.5-coder:3b"))
    offline_only = db_settings.get("offline_only", str(config.get("offline_only", False))).lower() == "true"
    
    # Retrieve API key for key presence check only (never echo value to frontend)
    api_key = ConfigManager.get_api_key(provider) or ""
    has_key = bool(api_key)
    
    return {
        "provider": provider,
        "model": model,
        "ai_mode": ai_mode,
        "has_key": has_key,
        "visual_threshold": visual_threshold,
        "retention": retention,
        "local_base_url": local_base_url,
        "local_model": local_model,
        "offline_only": offline_only
    }

@router.put("")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_session)):
    """Update configurations and store the API Key securely in system keyring."""
    fields_to_save = {
        "provider": payload.provider,
        "model": payload.model,
        "ai_mode": payload.ai_mode,
        "visual_threshold": str(payload.visual_threshold) if payload.visual_threshold is not None else None,
        "retention": str(payload.retention) if payload.retention is not None else None,
        "local_base_url": payload.local_base_url,
        "local_model": payload.local_model,
        "offline_only": str(payload.offline_only) if payload.offline_only is not None else None
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
    
    # Also sync configuration into ConfigManager (config.json) so CLI commands stay in sync
    config = ConfigManager.load_config()
    if payload.provider:
        config["provider"] = payload.provider
    if payload.model:
        config["model"] = payload.model
    if payload.local_base_url:
        config["local_base_url"] = payload.local_base_url
    if payload.local_model:
        config["local_model"] = payload.local_model
    if payload.offline_only is not None:
        config["offline_only"] = payload.offline_only
    if payload.api_key:
        config["api_key"] = payload.api_key
        
    ConfigManager.save_config(config)
    
    return {"status": "success", "message": "Settings updated successfully"}

class TestConnectionRequest(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    local_base_url: Optional[str] = None

@router.post("/test-connection")
def test_connection(payload: TestConnectionRequest):
    """Securely check connectivity of the chosen LLM provider."""
    try:
        if payload.provider == "local":
            from scrapewizard.llm.local_runtime import LocalRuntime
            base_url = payload.local_base_url or "http://localhost:11434"
            runtime = LocalRuntime(base_url=base_url)
            daemon = runtime.check_daemon()
            if not daemon.running:
                return {"ok": False, "message": "Ollama daemon is not running. Please start Ollama and try again."}
                
            models = runtime.list_models()
            model_loaded = False
            for m in models:
                if m == payload.model or m.startswith(payload.model + ":") or payload.model.startswith(m + ":"):
                    model_loaded = True
                    break
                    
            if not model_loaded:
                return {"ok": False, "message": f"Model '{payload.model}' is not pulled/downloaded in Ollama."}
                
            probe_res = runtime.probe(payload.model)
            if probe_res.success:
                return {"ok": True, "message": f"Connection test passed! Latency: {probe_res.latency}s"}
            else:
                return {"ok": False, "message": f"Connection test failed to probe model: {probe_res.error}"}
        
        # Cloud providers
        key = payload.api_key
        if not key:
            # Try to fetch from keyring if not passed
            key = ConfigManager.get_api_key(payload.provider)
            
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

@router.get("/local-status")
def get_local_status():
    """Check local AI runtime status for the Settings page."""
    from scrapewizard.llm.local_runtime import LocalRuntime
    runtime = LocalRuntime()
    daemon = runtime.check_daemon()
    models = runtime.list_models() if daemon.running else []
    tier_info = runtime.detect_hardware()
    return {
        "daemon_running": daemon.running,
        "daemon_version": daemon.version,
        "installed_models": models,
        "hardware_tier": tier_info["tier"],
        "ram_gb": tier_info["ram_gb"],
        "gpu": tier_info["gpu_name"],
        "recommended_model": runtime.recommend_model(tier_info["tier"]),
    }

class PullModelRequest(BaseModel):
    model: str
    local_base_url: Optional[str] = None

@router.post("/pull-model")
async def pull_model(payload: PullModelRequest):
    """Pull/download a model via Ollama with SSE progress."""
    from scrapewizard.llm.local_runtime import LocalRuntime
    
    base_url = payload.local_base_url or "http://localhost:11434"
    runtime = LocalRuntime(base_url=base_url)
    
    async def event_generator():
        import queue
        import threading
        
        q = queue.Queue()
        
        def run_pull():
            def cb(data):
                q.put(data)
            success = runtime.pull_model(payload.model, cb)
            q.put({"done": True, "success": success})
            
        threading.Thread(target=run_pull, daemon=True).start()
        
        while True:
            try:
                data = q.get_nowait()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("done"):
                    break
            except queue.Empty:
                await asyncio.sleep(0.2)
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")
