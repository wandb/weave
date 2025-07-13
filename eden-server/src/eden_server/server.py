"""Eden MCP Server implementation."""
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from pydantic import BaseModel

class ServerConfig(BaseModel):
    """Configuration for the Eden server."""
    config_path: Path
    dev_mode: bool = False
    dashboard_port: int = 3000

class EdenServer:
    """Main Eden server implementation."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the Eden server."""
        self.config = config
        self.app = FastAPI(title="Eden Server")
        self.mcp = FastMCP("Eden")
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # TODO: Make configurable
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files for dashboard in production
        if not config.dev_mode:
            dashboard_path = Path(__file__).parent.parent.parent / "eden-dash" / "dist"
            self.app.mount("/", StaticFiles(directory=str(dashboard_path), html=True))
        
        # WebSocket connections for real-time updates
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Handle WebSocket connections for real-time updates."""
            await websocket.accept()
            client_id = str(id(websocket))
            self.active_connections[client_id] = websocket
            try:
                while True:
                    data = await websocket.receive_text()
                    # Handle incoming messages
                    # TODO: Implement message handling
            except Exception:
                del self.active_connections[client_id]
        
        @self.app.get("/api/status")
        async def get_status():
            """Get server status."""
            return {
                "status": "running",
                "config_path": str(self.config.config_path),
                "dev_mode": self.config.dev_mode,
            }
    
    async def start(self):
        """Start the server."""
        import uvicorn
        
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def stop(self):
        """Stop the server."""
        # TODO: Implement graceful shutdown
        pass 