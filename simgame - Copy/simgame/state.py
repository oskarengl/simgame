from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import EntityType, MAX_ENTITIES, WINDOW_WIDTH, WINDOW_HEIGHT


@dataclass
class SimulationState:
    """Structure-of-arrays storage for fast vectorized simulation."""

    capacity: int = MAX_ENTITIES
    positions: np.ndarray = field(init=False)
    velocities: np.ndarray = field(init=False)
    energy: np.ndarray = field(init=False)
    entity_type: np.ndarray = field(init=False)
    size: np.ndarray = field(init=False)
    alive_mask: np.ndarray = field(init=False)
    tree_fruit: np.ndarray = field(init=False)
    tree_fruit_capacity: np.ndarray = field(init=False)
    seed_positions: np.ndarray = field(init=False)
    seed_alive: np.ndarray = field(init=False)
    seed_from_fruit: np.ndarray = field(init=False)
    seed_timer: np.ndarray = field(init=False)
    corpse_positions: np.ndarray = field(init=False)
    corpse_alive: np.ndarray = field(init=False)
    corpse_decay: np.ndarray = field(init=False)
    corpse_size: np.ndarray = field(init=False)
    _seed_next_slot: int = field(init=False, default=0)
    _corpse_next_slot: int = field(init=False, default=0)
    seed_capacity: int = 6000
    corpse_capacity: int = 2000
    count: int = 0

    def __post_init__(self) -> None:
        self.positions = np.zeros((self.capacity, 2), dtype=np.float32)
        self.velocities = np.zeros((self.capacity, 2), dtype=np.float32)
        self.energy = np.ones(self.capacity, dtype=np.float32)
        self.entity_type = np.zeros(self.capacity, dtype=np.int32)
        self.size = np.full(self.capacity, 6.0, dtype=np.float32)
        self.alive_mask = np.zeros(self.capacity, dtype=bool)
        self.tree_fruit = np.zeros(self.capacity, dtype=np.float32)
        self.tree_fruit_capacity = np.zeros(self.capacity, dtype=np.float32)
        self.seed_positions = np.zeros((self.seed_capacity, 2), dtype=np.float32)
        self.seed_alive = np.zeros(self.seed_capacity, dtype=bool)
        self.seed_from_fruit = np.zeros(self.seed_capacity, dtype=bool)
        self.seed_timer = np.zeros(self.seed_capacity, dtype=np.float32)
        self.corpse_positions = np.zeros((self.corpse_capacity, 2), dtype=np.float32)
        self.corpse_alive = np.zeros(self.corpse_capacity, dtype=bool)
        self.corpse_decay = np.zeros(self.corpse_capacity, dtype=np.float32)
        self.corpse_size = np.full(self.corpse_capacity, 10.0, dtype=np.float32)

    @property
    def alive_count(self) -> int:
        return int(np.count_nonzero(self.alive_mask[: self.count]))

    def spawn_random(
        self,
        amount: int,
        entity_type: EntityType,
        *,
        position_bounds: tuple[float, float, float, float] | None = None,
        speed: float = 50.0,
        size: float | None = None,
        max_jitter: float = 1.0,
    ) -> None:
        """Spawn entities uniformly in the playfield."""
        if amount <= 0:
            return
        if self.count + amount > self.capacity:
            amount = self.capacity - self.count
        if amount <= 0:
            return

        x_min, y_min, x_max, y_max = position_bounds or (
            0.0,
            0.0,
            float(WINDOW_WIDTH),
            float(WINDOW_HEIGHT),
        )

        idx_start = self.count
        idx_end = idx_start + amount
        rng = np.random.default_rng()

        self.positions[idx_start:idx_end, 0] = rng.uniform(x_min, x_max, amount)
        self.positions[idx_start:idx_end, 1] = rng.uniform(y_min, y_max, amount)
        self.velocities[idx_start:idx_end] = rng.normal(scale=max_jitter, size=(amount, 2)).astype(
            np.float32
        )
        speeds = np.linalg.norm(self.velocities[idx_start:idx_end], axis=1, keepdims=True) + 1e-5
        self.velocities[idx_start:idx_end] = (
            self.velocities[idx_start:idx_end] / speeds * speed
        ).astype(np.float32)
        self.energy[idx_start:idx_end] = 1.0
        self.entity_type[idx_start:idx_end] = int(entity_type)
        if size is not None:
            self.size[idx_start:idx_end] = size
        else:
            self.size[idx_start:idx_end] = np.random.uniform(4.0, 10.0, amount)
        self.alive_mask[idx_start:idx_end] = True
        self.count += amount

    def spawn_trees(
        self,
        amount: int,
        *,
        position_bounds: tuple[float, float, float, float] | None = None,
        fruit_capacity: float = 5.0,
        initial_fruit: tuple[int, int] = (0, 2),
    ) -> None:
        """Spawn static trees with fruit tracking."""
        if amount <= 0:
            return
        if self.count + amount > self.capacity:
            amount = self.capacity - self.count
        if amount <= 0:
            return

        x_min, y_min, x_max, y_max = position_bounds or (
            40.0,
            40.0,
            float(WINDOW_WIDTH - 40),
            float(WINDOW_HEIGHT - 40),
        )

        idx_start = self.count
        idx_end = idx_start + amount
        rng = np.random.default_rng()

        self.positions[idx_start:idx_end, 0] = rng.uniform(x_min, x_max, amount)
        self.positions[idx_start:idx_end, 1] = rng.uniform(y_min, y_max, amount)
        self.velocities[idx_start:idx_end] = 0.0
        self.energy[idx_start:idx_end] = 1.0
        self.entity_type[idx_start:idx_end] = int(EntityType.TREE)
        self.size[idx_start:idx_end] = rng.uniform(18.0, 28.0, amount).astype(np.float32)
        self.tree_fruit_capacity[idx_start:idx_end] = fruit_capacity
        self.tree_fruit[idx_start:idx_end] = rng.integers(
            initial_fruit[0], initial_fruit[1] + 1, amount
        )
        self.alive_mask[idx_start:idx_end] = True
        self.count += amount

    def add_seed(self, x: float, y: float, from_fruit: bool = True) -> None:
        idx = self._alloc_seed_slot()
        if idx is None:
            return
        self.seed_positions[idx] = (x, y)
        self.seed_alive[idx] = True
        self.seed_from_fruit[idx] = from_fruit
        self.seed_timer[idx] = 0.0

    def add_corpse(self, x: float, y: float, size: float, decay: float = 600.0) -> None:
        idx = self._alloc_corpse_slot()
        if idx is None:
            return
        self.corpse_positions[idx] = (x, y)
        self.corpse_alive[idx] = True
        self.corpse_decay[idx] = decay
        self.corpse_size[idx] = size

    def _alloc_seed_slot(self) -> int | None:
        for _ in range(self.seed_capacity):
            candidate = self._seed_next_slot
            self._seed_next_slot = (self._seed_next_slot + 1) % self.seed_capacity
            if not self.seed_alive[candidate]:
                return candidate
        return None

    def _alloc_corpse_slot(self) -> int | None:
        for _ in range(self.corpse_capacity):
            candidate = self._corpse_next_slot
            self._corpse_next_slot = (self._corpse_next_slot + 1) % self.corpse_capacity
            if not self.corpse_alive[candidate]:
                return candidate
        return None


