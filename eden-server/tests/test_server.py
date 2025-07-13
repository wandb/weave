import pytest
from fastapi.testclient import TestClient
from eden.server import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Eden MCP Server is running"}

@pytest.mark.asyncio
async def test_websocket_endpoint():
    with client.websocket_connect("/ws") as websocket:
        data = "Hello, WebSocket!"
        websocket.send_text(data)
        response = websocket.receive_text()
        assert response == f"Message received: {data}" 