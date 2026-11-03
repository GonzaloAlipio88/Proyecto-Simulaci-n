import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

_CANONICAL_CFG = sys.modules.get("backend.app.core.config") or sys.modules.get("app.core.config") or sys.modules[__name__]
sys.modules["backend.app.core.config"] = _CANONICAL_CFG
sys.modules["app.core.config"] = _CANONICAL_CFG

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
    
    # Computer Vision / YOLO settings
    DETECTION_MODEL_TYPE: str = "yolo" # "yolo", "hybrid", "heuristic", or "diagnostic"
    YOLO_WEIGHTS_PATH: str = str(
        (BASE_DIR / "storage" / "weights" / "best.pt")
        if (BASE_DIR / "storage" / "weights" / "best.pt").exists()
        else (BASE_DIR / "storage" / "weights" / "yolov8n.pt")
    )
    YOLO_WEIGHTS_DIR: Path = BASE_DIR / "storage" / "weights"
    YOLO_DEVICE: str = "cpu" # "cpu", "cuda", or "auto"
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.50
    DETECTION_FALLBACK_TO_HEURISTIC: bool = True # If YOLO weights/lib missing, fallback to OpenCV heuristic
    HYBRID_COMPLEMENT_FOR_WEBOTS: bool = True # Complement generic COCO YOLO with OpenCV heuristic on Webots 3D frames
    VISION_SKIP_FRAMES_ON_BUSY: bool = True # Drop frame if vision engine is currently busy
    VISION_ANALYSIS_INTERVAL_FRAMES: int = 1 # Analyze every N frames (1 = all frames)


    # Classes target
    TARGET_CLASSES: List[str] = [
        "poste_luz",
        "vegetacion_invasiva",
        "obstruccion_via"
    ]

    # External Image Upload settings (Semana 7)
    MAX_IMAGE_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    ALLOWED_IMAGE_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png"]
    ALLOWED_IMAGE_MIMES: List[str] = ["image/jpeg", "image/png", "image/jpg"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()

# Ensure directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
settings.YOLO_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
