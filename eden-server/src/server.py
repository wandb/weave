import json
import os
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Eden MCP Server")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from the React app
app.mount("/", StaticFiles(directory="../eden-dash/build", html=True), name="static")

class ServerConfig(BaseModel):
    name: str
    url: str
    enabled: bool = True

class ToolRequest(BaseModel):
    id: str
    tool: str
    arguments: Dict
    user: str
    timestamp: str

# In-memory storage for development
config: Dict = {
    "servers": [],
    "tools": [],
    "llm_vendors": [],
}

pending_requests: List[ToolRequest] = []

@app.get("/api/config")
async def get_config():
    return config

@app.post("/api/config")
async def update_config(new_config: Dict):
    global config
    config = new_config
    return {"status": "success"}

@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "uptime": "2 hours",  # TODO: Implement actual uptime tracking
        "connected_servers": len(config["servers"]),
        "pending_requests": len(pending_requests),
    }

@app.post("/api/requests")
async def create_request(request: ToolRequest):
    pending_requests.append(request)
    return {"status": "success", "id": request.id}

@app.get("/api/requests")
async def get_requests():
    return pending_requests

@app.post("/api/requests/{request_id}/approve")
async def approve_request(request_id: str):
    request = next((r for r in pending_requests if r.id == request_id), None)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # TODO: Implement actual tool execution
    pending_requests.remove(request)
    return {"status": "success"}

@app.post("/api/requests/{request_id}/deny")
async def deny_request(request_id: str):
    request = next((r for r in pending_requests if r.id == request_id), None)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    pending_requests.remove(request)
    return {"status": "success"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # TODO: Implement WebSocket communication for real-time updates
            await websocket.send_text(f"Message text was: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 