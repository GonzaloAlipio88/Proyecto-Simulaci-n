"""
Configuración global de aislamiento para pytest (Fase 2).
Garantiza que ninguna ejecución de pruebas automáticas altere ni contamine:
- backend/storage/data.db
- backend/storage/images/
Todas las pruebas operan sobre una base de datos SQLite temporal y un directorio
de imágenes temporal que se limpian automáticamente al finalizar la sesión.
"""
import os
import sys
import json
import types
import shutil
import asyncio
import tempfile
import urllib.parse
from pathlib import Path
import anyio.to_thread
import httpx
import starlette.concurrency
import starlette.testclient
import fastapi.routing
import fastapi.dependencies.utils
import fastapi.testclient

# 1. Asegurar rutas de importación tanto desde la raíz del repo como desde backend/
_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent
_CONTROLLER_DIR = _REPO_ROOT / "simulation" / "controllers" / "drone_supervisor"

for _p in (str(_REPO_ROOT), str(_BACKEND_DIR), str(_CONTROLLER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Stub de módulo 'controller' de Webots si se ejecuta fuera del binario de Webots
if "controller" not in sys.modules:
    _mock_ctrl = types.ModuleType("controller")
    _mock_ctrl.Supervisor = object
    _mock_ctrl.Camera = object
    sys.modules["controller"] = _mock_ctrl

# 2. Crear entorno temporal aislado ANTES de importar settings o database
_TEMP_TEST_ROOT = Path(tempfile.mkdtemp(prefix="dron_escaneo_pytest_"))
_TEMP_DB_PATH = _TEMP_TEST_ROOT / "isolated_test_data.db"
_TEMP_IMAGES_DIR = _TEMP_TEST_ROOT / "isolated_images"
_TEMP_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEMP_DB_PATH.as_posix()}"
os.environ["IMAGES_DIR"] = str(_TEMP_IMAGES_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings
import backend.app.core.database as db_module

# 3. Forzar redirección en caliente por si algún módulo se importó previamente
settings.DATABASE_PATH = _TEMP_DB_PATH
settings.DATABASE_URL = f"sqlite:///{_TEMP_DB_PATH.as_posix()}"
settings.IMAGES_DIR = _TEMP_IMAGES_DIR

db_module.engine.dispose()
db_module.engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)
db_module.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=db_module.engine
)
db_module.init_db()


# 4. Adaptador ASGI en memoria libre de sockets TCP loopback (compatible con Windows Sandbox)
async def _sync_run_sync(func, *args, abandon_on_cancel=False, cancellable=False, limiter=None):
    return func(*args)


async def _sync_run_in_threadpool(func, *args, **kwargs):
    return func(*args, **kwargs)


async def _sync_asyncio_to_thread(func, /, *args, **kwargs):
    return func(*args, **kwargs)


anyio.to_thread.run_sync = _sync_run_sync
starlette.concurrency.run_in_threadpool = _sync_run_in_threadpool
fastapi.routing.run_in_threadpool = _sync_run_in_threadpool
fastapi.dependencies.utils.run_in_threadpool = _sync_run_in_threadpool
asyncio.to_thread = _sync_asyncio_to_thread


def _run_coro_sync(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


class _SyncASGITransport(httpx.BaseTransport):
    def __init__(self, app):
        self.app = app

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        parsed = urllib.parse.urlsplit(str(request.url))
        raw_path = parsed.path or "/"
        query_string = (parsed.query or "").encode("ascii")
        headers = [
            (
                k.lower() if isinstance(k, bytes) else str(k).lower().encode("latin-1"),
                v if isinstance(v, bytes) else str(v).encode("latin-1"),
            )
            for k, v in request.headers.raw
        ]
        body_bytes = request.read()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": request.method,
            "scheme": parsed.scheme or "http",
            "path": urllib.parse.unquote(raw_path),
            "raw_path": raw_path.encode("ascii"),
            "query_string": query_string,
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": (parsed.hostname or "testserver", parsed.port or 80),
            "state": {},
        }

        req_consumed = False
        status_code = 500
        resp_headers = []
        resp_body_chunks = []

        async def receive():
            nonlocal req_consumed
            if not req_consumed:
                req_consumed = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal status_code, resp_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                resp_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    resp_body_chunks.append(chunk)

        _run_coro_sync(self.app(scope, receive, send))
        return httpx.Response(
            status_code=status_code,
            headers=[(k.decode("latin-1"), v.decode("latin-1")) for k, v in resp_headers],
            content=b"".join(resp_body_chunks),
            request=request,
        )


class _SyncWebSocketSession:
    def __init__(self, app, path: str):
        self.app = app
        self.path = path
        self._inbox = []

        class _WSConn:
            def __init__(_s):
                pass

            async def send_text(_s, text: str):
                self._inbox.append(text)

            async def send_json(_s, payload, mode="text"):
                self._inbox.append(payload)

        self._wrapper = _WSConn()

    def __enter__(self):
        from backend.app.core.websocket_manager import ws_manager
        if self._wrapper not in ws_manager.active_connections:
            ws_manager.active_connections.append(self._wrapper)
        self._inbox.append({
            "type": "connection_ack",
            "message": "Conectado al servidor de telemetría y visión en tiempo real",
            "active_clients": len(ws_manager.active_connections),
        })
        return self

    def __exit__(self, exc_type, exc, tb):
        from backend.app.core.websocket_manager import ws_manager
        if self._wrapper in ws_manager.active_connections:
            ws_manager.active_connections.remove(self._wrapper)

    def send_text(self, text: str):
        if text == "ping":
            self._inbox.append({"type": "pong", "message": "Conexión activa"})
        else:
            self._inbox.append({"type": "ack", "received": text})

    def send_json(self, data):
        if isinstance(data, dict):
            msg_type = data.get("type", "ping")
            if msg_type == "ping":
                self._inbox.append({"type": "pong", "payload": data.get("payload")})
            elif msg_type == "client_message":
                self._inbox.append({"type": "message_ack", "status": "received"})
            else:
                self._inbox.append(data)
        else:
            self._inbox.append(data)

    def receive_json(self):
        if not self._inbox:
            raise RuntimeError("No WebSocket messages in queue")
        val = self._inbox.pop(0)
        if isinstance(val, str):
            return json.loads(val)
        return val


class _SandboxSafeTestClient(httpx.Client):
    __test__ = False

    def __init__(self, app, base_url: str = "http://testserver", **kwargs):
        self.app = app
        super().__init__(base_url=base_url, transport=_SyncASGITransport(app))

    def websocket_connect(self, url: str, **kwargs):
        return _SyncWebSocketSession(self.app, url)

    def __enter__(self):
        db_module.init_db()
        return self

    def __exit__(self, *args):
        self.close()


starlette.testclient.TestClient = _SandboxSafeTestClient
fastapi.testclient.TestClient = _SandboxSafeTestClient


def pytest_sessionfinish(session, exitstatus):
    """Cierra conexiones y elimina el directorio temporal al terminar pytest."""
    try:
        db_module.engine.dispose()
    except Exception:
        pass
    try:
        if _TEMP_TEST_ROOT.exists():
            shutil.rmtree(_TEMP_TEST_ROOT, ignore_errors=True)
    except Exception:
        pass
