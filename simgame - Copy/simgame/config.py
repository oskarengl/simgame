from __future__ import annotations

import enum

WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
TARGET_FPS = 60


class EntityType(enum.IntEnum):
    TREE = 0
    HERBIVORE = 1
    TREE_EATER = 2
    CARNIVORE = 3
    DECOMPOSER = 4
    ALPHA_PREDATOR = 5


ENTITY_COLORS = {
    EntityType.TREE: (0.05, 0.5, 0.1),
    EntityType.HERBIVORE: (0.2, 0.8, 0.2),
    EntityType.TREE_EATER: (1.0, 0.55, 0.0),
    EntityType.CARNIVORE: (0.9, 0.1, 0.1),
    EntityType.DECOMPOSER: (0.6, 0.1, 0.7),
    EntityType.ALPHA_PREDATOR: (0.6, 0.0, 0.0),
}


MAX_ENTITIES = 20000
MAX_TREES = 5000


