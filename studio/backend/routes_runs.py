import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from sqlmodel import Session, select, func
from typing import List, Optional, Dict, Any

from studio.backend.deps import get_session
from studio.backend.models import Run, StepResult, Test
from studio.backend.run_executor import execute_run_task, ws_hub

router = APIRouter(tags=["Runs"])

@router.post("/tests/{test_id}/run")
def trigger_run(test_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    """Enqueue and execute a new sandbox test run instance."""
    test = db.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
        
    run = Run(test_id=test_id, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    
    # Enqueue execution as background task
    background_tasks.add_task(execute_run_task, run.id, test_id)
    return {"run_id": run.id, "status": run.status}

@router.get("/runs")
def list_runs(test_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_session)):
    """List execution runs, filterable by status or test identifier."""
    query = select(Run).order_by(Run.started_at.desc())
    if test_id is not None:
        query = query.where(Run.test_id == test_id)
    if status is not None:
        query = query.where(Run.status == status)
        
    runs = db.exec(query).all()
    results = []
    
    for r in runs:
        test_name = "Unknown Test"
        test = db.get(Test, r.test_id)
        if test:
            test_name = test.name
            
        results.append({
            "id": r.id,
            "test_id": r.test_id,
            "test_name": test_name,
            "status": r.status,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_ms": r.duration_ms,
            "ai_calls": r.ai_calls,
            "ai_cost_usd": r.ai_cost_usd
        })
        
    return results

@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_session)):
    """Fetch details of a single run execution along with its step outcomes."""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    step_results = db.exec(
        select(StepResult)
        .where(StepResult.run_id == run_id)
        .order_by(StepResult.id)
    ).all()
    
    test = db.get(Test, run.test_id)
    test_name = test.name if test else "Unknown Test"
    
    return {
        "id": run.id,
        "test_id": run.test_id,
        "test_name": test_name,
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms,
        "ai_calls": run.ai_calls,
        "ai_cost_usd": run.ai_cost_usd,
        "step_results": step_results
    }

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_session)):
    """Compile aggregated health and execution metrics for the dashboard."""
    total_tests = db.exec(select(func.count(Test.id))).one()
    
    # Pass rate over last 7 days
    seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    recent_runs = db.exec(
        select(Run)
        .where(Run.started_at >= seven_days_ago)
        .where(Run.status != "queued")
        .where(Run.status != "running")
    ).all()
    
    passed_count = sum(1 for r in recent_runs if r.status == "passed")
    total_recent = len(recent_runs)
    pass_rate = (passed_count / total_recent) * 100 if total_recent > 0 else 0
    
    # Runs today
    today_start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = db.exec(select(func.count(Run.id)).where(Run.started_at >= today_start)).one()
    
    # AI Spend
    ai_spend = db.exec(select(func.sum(Run.ai_cost_usd))).one() or 0.0
    
    return {
        "tests": total_tests,
        "pass_rate_7d": round(pass_rate, 1),
        "runs_today": runs_today,
        "ai_spend": round(ai_spend, 4)
    }

@router.websocket("/runs/{run_id}/live")
async def run_live_websocket(websocket: WebSocket, run_id: int):
    """WebSocket endpoint to receive real-time updates as step results complete."""
    await ws_hub.connect(run_id, websocket)
    try:
        while True:
            # Keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect(run_id, websocket)
    except Exception:
        ws_hub.disconnect(run_id, websocket)
