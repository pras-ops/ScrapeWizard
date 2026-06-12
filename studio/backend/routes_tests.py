import os
import json
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func

from studio.backend.deps import get_session, STUDIO_ARTIFACTS_DIR
from studio.backend.db import engine
from studio.backend.models import Test, Step, Run
from scrapewizard.core.config import ConfigManager
from scrapewizard.engine.recorder import InteractiveRecorder
from scrapewizard.engine.test_generator import TestGenerator
from scrapewizard.core.logging import log

router = APIRouter(prefix="/tests", tags=["Tests"])

# In-memory tracking for recording tasks
active_recordings: Dict[int, asyncio.Task] = {}
recording_states: Dict[int, Dict[str, Any]] = {}  # test_id -> {"recording": bool, "step_count": int}

async def run_recorder_flow(test_id: int, recorder: InteractiveRecorder, url: str, flow_path: Path):
    """Async background task running InteractiveRecorder and updating SQLite steps on completion."""
    try:
        recording_states[test_id] = {"recording": True, "step_count": 0}
        
        async def poll_steps():
            while recording_states.get(test_id, {}).get("recording"):
                recording_states[test_id]["step_count"] = len(recorder.steps)
                await asyncio.sleep(0.5)
                
        poll_task = asyncio.create_task(poll_steps())
        await recorder.start(url)
        poll_task.cancel()
    except Exception as e:
        log(f"Recording task failed for test {test_id}: {e}", level="error")
    finally:
        recording_states[test_id]["recording"] = False
        active_recordings.pop(test_id, None)
        
        # Parse output flow.json on browser close and update Step records in SQLite
        if flow_path.exists():
            try:
                with open(flow_path, "r", encoding="utf-8") as f:
                    flow_data = json.load(f)
                
                recording_states[test_id]["step_count"] = len(flow_data.get("steps", []))
                
                # Import generator to map to standard steps
                generator = TestGenerator(str(flow_path))
                test_def = generator.generate()
                
                # Update DB Steps
                with Session(engine) as db:
                    existing_steps = db.exec(select(Step).where(Step.test_id == test_id)).all()
                    for s in existing_steps:
                        db.delete(s)
                    
                    for idx, s in enumerate(test_def["steps"]):
                        fp = {}
                        if idx > 0 and (idx - 1) < len(recorder.steps):
                            fp = dict(recorder.steps[idx - 1].get("fingerprint", {}))
                            fp["screenshot_path"] = f"/projects/test_{test_id}/screenshots/crop_{idx - 1}.png"
                        
                        db_step = Step(
                            test_id=test_id,
                            order=idx,
                            action=s["action"],
                            value=s["value"],
                            selectors=s["selectors"],
                            assertions=s["assertions"],
                            fingerprint=fp
                        )
                        db.add(db_step)
                    db.commit()
                log(f"Steps updated in database successfully for test {test_id}.")
            except Exception as e:
                log(f"Failed to save recorded steps to SQLite: {e}", level="error")

@router.post("")
def create_test(payload: Dict[str, Any], db: Session = Depends(get_session)):
    """Create a new Test record with a default name if omitted."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
        
    try:
        url = ConfigManager.validate_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    from urllib.parse import urlparse
    domain = urlparse(url).netloc or "site"
    name = payload.get("name") or f"Scrape flow for {domain}"
    
    test = Test(name=name, url=url)
    db.add(test)
    db.commit()
    db.refresh(test)
    return {"id": test.id, "name": test.name, "url": test.url}

@router.get("")
def list_tests(db: Session = Depends(get_session)):
    """List all tests along with step counts and last run health."""
    tests = db.exec(select(Test)).all()
    results = []
    
    for t in tests:
        # Count steps
        step_count = db.exec(select(func.count(Step.id)).where(Step.test_id == t.id)).one()
        
        # Last run
        last_run = db.exec(
            select(Run)
            .where(Run.test_id == t.id)
            .order_by(Run.started_at.desc())
            .limit(1)
        ).first()
        
        last_run_data = None
        if last_run:
            last_run_data = {
                "id": last_run.id,
                "status": last_run.status,
                "started_at": last_run.started_at.isoformat()
            }
            
        results.append({
            "id": t.id,
            "name": t.name,
            "url": t.url,
            "step_count": step_count,
            "last_run": last_run_data
        })
        
    return results

@router.get("/{id}")
def get_test(id: int, db: Session = Depends(get_session)):
    """Retrieve detailed test configuration including all recorded steps."""
    test = db.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    steps = db.exec(
        select(Step)
        .where(Step.test_id == id)
        .order_by(Step.order)
    ).all()
    
    return {
        "id": test.id,
        "name": test.name,
        "url": test.url,
        "steps": steps
    }

@router.put("/{id}")
def update_test(id: int, payload: Dict[str, Any], db: Session = Depends(get_session)):
    """Update test name and step ordering/configurations."""
    test = db.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    if "name" in payload:
        test.name = payload["name"]
        
    if "steps" in payload:
        # Re-save steps
        # Remove existing steps
        existing_steps = db.exec(select(Step).where(Step.test_id == id)).all()
        for s in existing_steps:
            db.delete(s)
            
        for idx, s in enumerate(payload["steps"]):
            db_step = Step(
                test_id=id,
                order=idx,
                action=s.get("action"),
                value=s.get("value"),
                selectors=s.get("selectors", []),
                assertions=s.get("assertions", []),
                fingerprint=s.get("fingerprint", {})
            )
            db.add(db_step)
            
    db.commit()
    return {"status": "success", "message": "Test updated successfully"}

@router.delete("/{id}")
def delete_test(id: int, db: Session = Depends(get_session)):
    """Delete a test and all its step / execution records."""
    test = db.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    db.delete(test)
    db.commit()
    return {"status": "success", "message": "Test deleted successfully"}

@router.post("/{id}/record")
async def record_test(id: int, db: Session = Depends(get_session)):
    """Launch the interactive browser recorder to record a flow."""
    test = db.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    if id in active_recordings:
        return {"status": "already_recording"}
        
    # Project directories live in ~/.scrapewizard/projects/test_{id}/
    test_dir = ConfigManager.CONFIG_DIR / "projects" / f"test_{id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    flow_path = test_dir / "flow.json"
    screenshots_dir = test_dir / "screenshots"
    
    if screenshots_dir.exists():
        shutil.rmtree(screenshots_dir)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    # Spawn headed browser in a background async task
    recorder = InteractiveRecorder(
        output_path=str(flow_path),
        screenshots_dir=str(screenshots_dir),
        headless=False
    )
    
    task = asyncio.create_task(run_recorder_flow(id, recorder, test.url, flow_path))
    active_recordings[id] = task
    
    return {"status": "started"}

@router.get("/{id}/record/status")
def record_status(id: int):
    """Retrieve details on whether a recording browser session is active."""
    state = recording_states.get(id, {"recording": False, "step_count": 0})
    return state

@router.get("/{id}/export")
@router.post("/{id}/export")
def export_pytest(id: int, db: Session = Depends(get_session)):
    """Build and download a runnable standalone Playwright/pytest test script."""
    test = db.get(Test, id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    steps = db.exec(select(Step).where(Step.test_id == id).order_by(Step.order)).all()
    
    test_dir = ConfigManager.CONFIG_DIR / "projects" / f"test_{id}"
    test_dir.mkdir(parents=True, exist_ok=True)
    flow_path = test_dir / "flow.json"
    
    # Format expected by TestGenerator
    recorded_steps = []
    for s in steps:
        if s.action == "navigate":
            continue
        recorded_steps.append({
            "action": s.action,
            "value": s.value,
            "fingerprint": s.fingerprint,
            "assertions": s.assertions
        })
        
    flow_data = {
        "url": test.url,
        "steps": recorded_steps
    }
    with open(flow_path, "w", encoding="utf-8") as f:
        json.dump(flow_data, f, indent=2)
        
    generator = TestGenerator(str(flow_path))
    export_path = test_dir / "test_flow.py"
    generator.export_pytest(str(export_path))
    
    return FileResponse(
        export_path,
        media_type="text/x-python",
        filename=f"test_{test.name.replace(' ', '_').lower()}.py"
    )

# The run trigger POST /{id}/run is handled in routes_runs.py
