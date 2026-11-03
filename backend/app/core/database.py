import sys
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Ensure repository root is on sys.path even when executed from inside 'backend/'
_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Unify 'app.core.database' and 'backend.app.core.database' in sys.modules BEFORE defining Base
# so importing via either path always returns the single canonical module and declarative_base().
_CANONICAL_MOD = sys.modules.get("backend.app.core.database") or sys.modules.get("app.core.database") or sys.modules[__name__]
sys.modules["backend.app.core.database"] = _CANONICAL_MOD
sys.modules["app.core.database"] = _CANONICAL_MOD

from backend.app.core.config import settings

# SQLite engine with check_same_thread=False for multi-threaded/async FastAPI endpoints
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = getattr(_CANONICAL_MOD, "Base", None) or declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None):
    """Create all tables in SQLite database if they don't already exist and ensure columns."""
    from backend.app.models.dron import Drone  # noqa: F401
    from backend.app.models.telemetria import TelemetryRecord  # noqa: F401
    from backend.app.models.imagen import ImageRecord  # noqa: F401
    from backend.app.models.incidente import Incidente  # noqa: F401

    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)

    # Safe idempotent column migration for existing SQLite databases (preserves all data)
    try:
        with active_engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(incidentes)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "coordenadas_tipo" not in columns:
                conn.execute(text("ALTER TABLE incidentes ADD COLUMN coordenadas_tipo VARCHAR(50) DEFAULT 'simulacion_webots'"))
                conn.commit()
    except Exception:
        # Ignore if table was just created or connection is in test transaction
        pass
