from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings
from typing import Generator

# SQLite engine with check_same_thread=False for multi-threaded/async FastAPI endpoints
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session management."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables in SQLite database if they don't already exist and ensure columns."""
    from backend.app.models.dron import Drone
    from backend.app.models.telemetria import TelemetryRecord
    from backend.app.models.imagen import ImageRecord
    from backend.app.models.incidente import Incidente
    from sqlalchemy import text

    Base.metadata.create_all(bind=engine)

    # Safe idempotent column migration for existing SQLite databases (preserves all data)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(incidentes)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "coordenadas_tipo" not in columns:
                conn.execute(text("ALTER TABLE incidentes ADD COLUMN coordenadas_tipo VARCHAR(50) DEFAULT 'simulacion_webots'"))
                conn.commit()
    except Exception:
        # Ignore if table was just created or connection is in test transaction
        pass


