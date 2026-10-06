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
    """Create all tables in SQLite database if they don't already exist."""
    # Import all models to ensure they are registered with Base metadata
    from backend.app.models.dron import Drone
    from backend.app.models.telemetria import TelemetryRecord
    from backend.app.models.imagen import ImageRecord
    from backend.app.models.incidente import Incidente
    Base.metadata.create_all(bind=engine)

