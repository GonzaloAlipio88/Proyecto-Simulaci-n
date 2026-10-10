from typing import List, Dict, Any
from fastapi import WebSocket
import json
import logging
import asyncio

logger = logging.getLogger("websocket_manager")

class ConnectionManager:
    """Manages active WebSocket connections and handles broadcasting real-time data."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending direct WebSocket message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, event_type: str, data: Any):
        """Broadcasts a typed payload to all connected clients."""
        payload = {
            "type": event_type,
            "data": data
        }
        raw_message = json.dumps(payload, default=str)
        
        to_remove = []
        for connection in self.active_connections:
            try:
                await connection.send_text(raw_message)
            except Exception as e:
                logger.warning(f"Error broadcasting to client: {e}. Marking for removal.")
                to_remove.append(connection)

        for stale in to_remove:
            self.disconnect(stale)

# Global singleton manager
ws_manager = ConnectionManager()
