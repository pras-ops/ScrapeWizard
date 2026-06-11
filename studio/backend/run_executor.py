import datetime
import asyncio
from pathlib import Path
from typing import Dict, List
from fastapi import WebSocket
from sqlmodel import Session, select

from studio.backend.db import engine
from studio.backend.models import Run, Step, StepResult
from studio.backend.deps import STUDIO_ARTIFACTS_DIR, STUDIO_BASELINES_DIR
from scrapewizard.engine.sandbox import SandboxRunner
from scrapewizard.core.logging import log

class WSConnectionHub:
    """Manages active WebSocket connections for live run execution progress updates."""
    def __init__(self):
        self.connections: Dict[int, List[WebSocket]] = {}
        
    async def connect(self, run_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(run_id, []).append(websocket)
        
    def disconnect(self, run_id: int, websocket: WebSocket):
        if run_id in self.connections:
            if websocket in self.connections[run_id]:
                self.connections[run_id].remove(websocket)
            if not self.connections[run_id]:
                del self.connections[run_id]
                
    async def broadcast(self, run_id: int, message: dict):
        if run_id in self.connections:
            for connection in list(self.connections[run_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    # Connection closed or failed
                    pass

ws_hub = WSConnectionHub()

async def execute_run_task(run_id: int, test_id: int):
    """Run worker executing Playwright SandboxRunner and updating SQLModel entities."""
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = "running"
        session.add(run)
        session.commit()
        
    await ws_hub.broadcast(run_id, {"type": "run_status", "status": "running"})
    
    try:
        with Session(engine) as session:
            test_steps = session.exec(
                select(Step).where(Step.test_id == test_id).order_by(Step.order)
            ).all()
            
            from studio.backend.models import Test
            test = session.get(Test, test_id)
            url = test.url if test else ""
            
        test_def = {
            "url": url,
            "steps": []
        }
        for s in test_steps:
            # Generate deterministic name for execution reporting
            step_name = s.action if s.action == "navigate" else f"{s.action}_{s.order}"
            test_def["steps"].append({
                "name": step_name,
                "action": s.action,
                "value": s.value,
                "selectors": s.selectors,
                "assertions": s.assertions
            })
            
        run_artifacts_dir = STUDIO_ARTIFACTS_DIR / f"run_{run_id}"
        run_artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Execute sandbox environment run
        runner = SandboxRunner(
            artifacts_dir=str(run_artifacts_dir),
            baselines_dir=str(STUDIO_BASELINES_DIR),
            flow_name=f"test_{test_id}",
            headless=True
        )
        
        run_result = await runner.run(test_def)
        
        with Session(engine) as session:
            db_run = session.get(Run, run_id)
            db_run.status = run_result.status
            db_run.finished_at = datetime.datetime.now(datetime.timezone.utc)
            db_run.duration_ms = run_result.duration_ms
            db_run.ai_calls = run_result.ai_calls
            db_run.ai_cost_usd = run_result.ai_cost_usd
            session.add(db_run)
            
            for idx, r in enumerate(run_result.step_results):
                # Map standard local screenshot path to relative static URL mount
                scr_url = None
                if r.screenshot_path:
                    scr_url = f"/artifacts/run_{run_id}/screenshots/{Path(r.screenshot_path).name}"
                
                db_result = StepResult(
                    run_id=run_id,
                    step_name=r.step_name,
                    status=r.status,
                    duration_ms=r.duration_ms,
                    screenshot_path=scr_url,
                    visual_diff_score=r.visual_diff_score,
                    console_errors=r.console_errors,
                    network_errors=r.network_errors,
                    a11y_violations=r.a11y_violations,
                    healed=r.healed,
                    error_message=r.error_message
                )
                session.add(db_result)
                
                # Broadcast live step update
                await ws_hub.broadcast(run_id, {
                    "type": "step_result",
                    "step_index": idx,
                    "result": {
                        "step_name": r.step_name,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "screenshot_path": scr_url,
                        "visual_diff_score": r.visual_diff_score,
                        "console_errors": r.console_errors,
                        "network_errors": r.network_errors,
                        "a11y_violations": r.a11y_violations,
                        "healed": r.healed,
                        "error_message": r.error_message
                    }
                })
            session.commit()
            
        await ws_hub.broadcast(run_id, {"type": "run_status", "status": run_result.status})
        
    except Exception as e:
        log(f"Sandbox executor failed for run {run_id}: {e}", level="error")
        with Session(engine) as session:
            db_run = session.get(Run, run_id)
            if db_run:
                db_run.status = "error"
                db_run.finished_at = datetime.datetime.now(datetime.timezone.utc)
                session.add(db_run)
                session.commit()
        await ws_hub.broadcast(run_id, {"type": "run_status", "status": "error", "error_message": str(e)})
