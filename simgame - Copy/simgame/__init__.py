"""GPU-ready ecological simulation package."""

from .config import EntityType, WINDOW_WIDTH, WINDOW_HEIGHT
from .state import SimulationState

__all__ = [
    "EntityType",
    "WINDOW_WIDTH",
    "WINDOW_HEIGHT",
    "SimulationState",
]

