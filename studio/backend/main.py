from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import sys
import os
import json
from typing import List, Optional

# Add root to sys.path to access scrapewizard core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scrapewizard.core.logging import log
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
    """Robust bi-directional CDP proxy for Studio Inspector."""
    await ws.accept()
    log("CDP WebSocket connection established", level="info")
    
    # Use the existing browser_manager to get a session
    # or follow the user's "launch as you go" plan for the proxy.
    # Given the isolation, we'll try to get the existing session first.
    try:
        if not browser_manager.page:
            # If no page is active, start a default one (or wait for session/start)
            await browser_manager.start("about:blank")
            
        cdp_session = await browser_manager.get_cdp_session()

        async def browser_to_client():
            """Forward messages from Browser (CDP) -> Studio Client (WS)."""
            try:
                while True:
                    # cdp_session.receive() is the Playwright internal for getting events/responses
                    # However, to avoid blocking, we use the .on() listeners for events
                    # and the session.send() for command results.
                    # As a generic proxy, we'll use a queue or similar if needed, 
                    # but Playwright's CDP session doesn't easily expose a "receive all" poll.
                    
                    # Instead, we'll rely on the specific command results and events 
                    # we've already set up, but let's try to make it more generic.
                    await asyncio.sleep(0.1) # Placeholder for the loop if needed
            except Exception as e:
                log(f"CDP Browser -> Client error: {e}", level="error")

        async def client_to_browser():
            """Forward messages from Studio Client (WS) -> Browser (CDP)."""
            try:
                while True:
                    msg = await ws.receive_json()
                    method = msg.get("method")
                    params = msg.get("params", {})
                    msg_id = msg.get("id")
                    
                    if method == "Input.dispatchMouseEvent":
                        # Params: type, x, y, button, etc.
                        # browser_manager expects: event_type='mouse', params={action, x, y, ...}
                        # We map CDP-like params to our simple manager
                        etype = params.get("type")
                        mapping = {
                            "mousePressed": "down",
                            "mouseReleased": "up",
                            "mouseMoved": "move",
                            "mouseWheel": "wheel"
                        }
                        if etype in mapping:
                            await browser_manager.handle_input_event("mouse", {
                                "action": mapping[etype],
                                "x": params.get("x"),
                                "y": params.get("y"),
                                "deltaX": params.get("deltaX", 0),
                                "deltaY": params.get("deltaY", 0),
                                "button": params.get("button", "left")
                            })
                    elif method == "Input.dispatchKeyEvent":
                        # TODO: Map keys if needed
                        pass
                    elif method:
                        result = await cdp_session.send(method, params)
                        if msg_id is not None:
                            await ws.send_json({"id": msg_id, "result": result})
            except Exception as e:
                log(f"CDP Client -> Browser error: {e}", level="error")

        # Hook into browser_manager's internal screencast logic
        async def handle_screencast_frame(data):
            # Forward the frame to the frontend
            try:
                await ws.send_json({"method": "Page.screencastFrame", "params": {"data": data}})
            except Exception:
                pass

        browser_manager.on_frame = handle_screencast_frame
        
        # Hook into browser_manager's inspector logic
        async def handle_selection(data_str: str):
            try:
                data = json.loads(data_str)
                if data['type'] == 'hover':
                    await ws.send_json({"method": "Inspector.highlight", "params": data})
                elif data['type'] == 'select':
                    await ws.send_json({"method": "Inspector.selected", "params": data})
            except Exception as e:
                log(f"Inspector error: {e}", level="error")

        browser_manager.on_selection = handle_selection

        # Subscribe to standard events from the *second* session for other things
        def forward_event(event, params):
            try:
                # We need to use the current event loop of the app
                asyncio.run_coroutine_threadsafe(ws.send_json({"method": event, "params": params}), asyncio.get_event_loop())
            except Exception as e:
                # Ignore failures if socket is closed
                pass

        # In Playwright, .on() can take a sync or async function.
        # We'll use a wrapper to ensure it forwards to the WS.
        def create_forwarder(event_name):
            def handler(params):
                # Create a task to send the message
                asyncio.create_task(ws.send_json({"method": event_name, "params": params}))
            return handler

        # Standard events for Inspector
        cdp_session.on("Page.screencastFrame", create_forwarder("Page.screencastFrame"))
        cdp_session.on("Runtime.consoleAPICalled", create_forwarder("Runtime.consoleAPICalled"))
        cdp_session.on("Network.requestWillBeSent", create_forwarder("Network.requestWillBeSent"))
        cdp_session.on("DOM.documentUpdated", create_forwarder("DOM.documentUpdated"))
        cdp_session.on("Page.loadEventFired", create_forwarder("Page.loadEventFired"))

        # Run the command loop
        await client_to_browser()
        
    except WebSocketDisconnect:
        log("CDP WebSocket disconnected", level="info")
    except Exception as e:
        log(f"CDP Proxy failed: {e}", level="error")
    finally:
        try:
            await ws.close()
        except:
            pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
