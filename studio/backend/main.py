from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import sys
import os
from typing import List, Optional

# Add root to sys.path to access scrapewizard core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from studio.backend.state import StudioState, StudioProject, FieldDefinition
from studio.backend.browser_manager import StudioBrowserManager

app = FastAPI(title="ScrapeWizard Studio Backend")
browser_manager = StudioBrowserManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions = {}

@app.get("/health")
async def health():
    """Health check endpoint for CLI and Electron."""
    return {"status": "ok", "version": "1.0.0", "engine": "ScrapeWizard-Studio"}

@app.get("/")
async def root():
    return {"status": "online", "message": "ScrapeWizard Studio Orchestrator Active"}

@app.post("/session/start")
async def start_session(url: str, background_tasks: BackgroundTasks):
    # Use simple validation for now, or import from shared.validators if needed
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    
    project_id = f"proj_{len(active_sessions) + 1}"
    project = StudioProject(project_id=project_id, url=url, state=StudioState.NAVIGATION)
    active_sessions[project_id] = project
    
    # Start browser in background
    await browser_manager.start(url)
    
    return {"status": "started", "project_id": project_id, "state": project.state}

@app.post("/session/compile")
async def compile_project(project_id: str):
    if project_id not in active_sessions:
        return {"error": "Project not found"}
    
    project = active_sessions[project_id]
    # TODO: Invoke CodeGenerator with AET
    return {"status": "compiled", "project_id": project_id}

@app.get("/session/dom")
async def get_dom_project(project_id: str):
    if project_id not in active_sessions:
        return {"error": "Project not found"}
    tree = await browser_manager.get_dom_tree()
    return {"project_id": project_id, "tree": tree}

@app.websocket("/cdp/ws")
async def cdp_proxy(ws: WebSocket):
    await ws.accept()
    try:
        session = await browser_manager.get_cdp_session()
        
        # Forward messages from browser to client
        # We need to wrap the listener in an async task
        async def forward_to_client(event_name, params):
            try:
                await ws.send_json({"method": event_name, "params": params})
            except:
                pass

        # Since we can't easily subscribe to ALL events in Playwright's CDP without listing them,
        # we'll focus on the ones needed for Studio/Inspector or use the session.send for commands.
        # However, for a generic proxy, we'd want more.
        
        # For now, let's implement the bi-directional command flow
        async def client_to_browser():
            try:
                while True:
                    msg = await ws.receive_json()
                    method = msg.get("method")
                    params = msg.get("params", {})
                    msg_id = msg.get("id")
                    
                    result = await session.send(method, params)
                    if msg_id is not None:
                        await ws.send_json({"id": msg_id, "result": result})
            except Exception as e:
                print(f"WS Client -> Browser Error: {e}")

        # Listen for some common events to forward (e.g., Screencast, Console, Network)
        session.on("Page.screencastFrame", lambda payload: asyncio.create_task(ws.send_json({"method": "Page.screencastFrame", "params": payload})))
        session.on("Runtime.consoleAPICalled", lambda payload: asyncio.create_task(ws.send_json({"method": "Runtime.consoleAPICalled", "params": payload})))

        await client_to_browser()
    except Exception as e:
        print(f"CDP Proxy Error: {e}")
    finally:
        await ws.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
