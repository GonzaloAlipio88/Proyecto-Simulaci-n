"""Backend App package — ensures unified module resolution for both 'app.*' and 'backend.app.*'."""
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent

for _p in (str(_REPO_ROOT), str(_BACKEND_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_self = sys.modules[__name__]
sys.modules.setdefault("app", _self)
sys.modules.setdefault("backend.app", _self)
