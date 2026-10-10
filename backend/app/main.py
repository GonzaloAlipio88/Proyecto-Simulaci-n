import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.core.websocket_manager import ws_manager
from backend.app.api.v1.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables
    logger.info("Initializing SQLite database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    # Shutdown
    logger.info("Server shutting down cleanly.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API y WebSocket en tiempo real para sistema de vigilancia con dron Webots y visión artificial.",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Health Check Endpoint
@app.get("/health", tags=["Salud"])
def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected"
    }

# WebSocket for real-time telemetry, stream notifications and commands
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial welcome / handshake
        await ws_manager.send_personal_message({
            "type": "connection_ack",
            "message": "Conectado al servidor de telemetría y visión en tiempo real",
            "active_clients": len(ws_manager.active_connections)
        }, websocket)

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "ping")
            
            if msg_type == "ping":
                await ws_manager.send_personal_message({"type": "pong", "payload": data.get("payload")}, websocket)
            elif msg_type == "client_message":
                logger.info(f"WebSocket client message received: {data}")
                await ws_manager.send_personal_message({"type": "message_ack", "status": "received"}, websocket)
            else:
                # Forward or echo custom actions
                logger.info(f"Unknown websocket payload: {msg_type}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
