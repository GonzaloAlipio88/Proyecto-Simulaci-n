import sys
import os
from pathlib import Path

# Add project root to sys.path so 'backend.app...' imports work correctly
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

import uvicorn
from backend.app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )
