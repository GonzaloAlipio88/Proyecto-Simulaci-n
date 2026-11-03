import sys

_self = sys.modules[__name__]
sys.modules["backend.app.models"] = _self
sys.modules["app.models"] = _self

from backend.app.models.dron import Drone
from backend.app.models.telemetria import TelemetryRecord
from backend.app.models.imagen import ImageRecord
from backend.app.models.incidente import Incidente

__all__ = ["Drone", "TelemetryRecord", "ImageRecord", "Incidente"]
