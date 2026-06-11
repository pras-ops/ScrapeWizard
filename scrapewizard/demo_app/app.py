import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

app = FastAPI(title="ScrapeWizard Demo Portal")

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serve the single-page demo portal HTML."""
    if not TEMPLATE_PATH.exists():
        return HTMLResponse(
            content="<h1>Demo portal HTML file is missing.</h1>", 
            status_code=404
        )
    return HTMLResponse(content=TEMPLATE_PATH.read_text(encoding="utf-8"))

@app.post("/api/login")
async def api_login(request: Request):
    """Mock API login endpoint."""
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")
    
    if not username or not password:
        return JSONResponse(
            content={"error": "Username and password are required"},
            status_code=400
        )
    
    return {"status": "ok", "token": "mock-jwt-token-12345"}

@app.post("/api/checkout")
async def api_checkout():
    """Mock API checkout endpoint."""
    return {"status": "success", "message": "Checkout complete! Order #9872"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
