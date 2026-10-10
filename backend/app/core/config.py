import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dron De Escaneo y Vigilancia - Sistema de Misión"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Server configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Database
    DATABASE_PATH: Path = BASE_DIR / "storage" / "data.db"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'storage' / 'data.db'}"
    
    # Storage
    STORAGE_DIR: Path = BASE_DIR / "storage"
    IMAGES_DIR: Path = BASE_DIR / "storage" / "images"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*"
    ]
    
    # Computer Vision / YOLO placeholder settings
    DETECTION_MODEL_TYPE: str = "heuristic" # "heuristic" or "yolo"
    YOLO_WEIGHTS_PATH: str = str(BASE_DIR / "storage" / "weights" / "best.pt")
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.50
    
    # Classes target
    TARGET_CLASSES: List[str] = [
        "poste_luz",
        "vegetacion_invasiva",
        "obstruccion_via"
    ]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()

# Ensure directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
