from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import EntityType, TARGET_FPS, WINDOW_HEIGHT, WINDOW_WIDTH
from ..world import RiverSegment
from ..state import SimulationState
from .kernels import TI_AVAILABLE, TaichiKernelEngine


@dataclass
class BehaviourTuning:
    wander_strength: float = 12.0  # Increased for more individual variation
    max_speed: float = 60.0  # Reduced overall max speed
    herbivore_seek_speed: float = 45.0  # Much slower when seeking food
    herbivore_idle_speed: float = 25.0  # Slower idle speed
    herbivore_target_jitter: float = 0.8  # Much more jitter for individual variation
    herbivore_hungry_threshold: float = 0.85
    herbivore_eat_radius: float = 20.0
    herbivore_energy_gain: float = 0.2
    tree_growth_rate: float = 0.01  # probability per second to grow fruit
    river_force: float = 1.5
    tree_eater_speed: float = 55.0
    tree_eater_idle_speed: float = 20.0
    tree_eater_target_jitter: float = 0.12
    tree_eater_bite_radius: float = 18.0
    tree_eater_damage: float = 0.03
    tree_eater_seed_chance: float = 0.3
    carnivore_speed: float = 95.0
    carnivore_jitter: float = 0.25
    carnivore_bite_radius: float = 18.0
    carnivore_energy_gain: float = 0.25
    alpha_speed: float = 115.0
    alpha_jitter: float = 0.2
    alpha_bite_radius: float = 18.0
    alpha_energy_gain: float = 0.35
    decomposer_speed: float = 60.0
    decomposer_jitter: float = 0.18
    decomposer_consume_radius: float = 16.0
    decomposer_energy_gain: float = 0.2
    health_decay: dict[EntityType, float] | None = None

    def __post_init__(self) -> None:
        if self.health_decay is None:
            self.health_decay = {
                EntityType.HERBIVORE: 0.02,
                EntityType.TREE_EATER: 0.03,
                EntityType.CARNIVORE: 0.05,
                EntityType.DECOMPOSER: 0.04,
                EntityType.ALPHA_PREDATOR: 0.07,
                EntityType.TREE: 0.0,
            }


class SimulationScheduler:
    """Lightweight orchestrator that advances the SoA state each frame."""

    def __init__(
        self,
        state: SimulationState,
        tuning: BehaviourTuning | None = None,
        backend: str = "auto",
    ) -> None:
        self.state = state
        self.tuning = tuning or BehaviourTuning()
        self.rng = np.random.default_rng()
        self._decay_lut = self._build_decay_lut()
        self.backend = self._resolve_backend(backend)
        self.kernel_engine: TaichiKernelEngine | None = None
        if self.backend == "taichi":
            try:
                self.kernel_engine = TaichiKernelEngine(self.state.capacity, self._decay_lut)
                print(f"[Simulation] Using Taichi backend (GPU acceleration enabled)")
            except Exception as e:
                print(f"[Simulation] Taichi initialization failed: {e}, falling back to NumPy")
                self.backend = "numpy"
                self.kernel_engine = None
        else:
            print(f"[Simulation] Using NumPy backend (CPU only)")
        self._tree_eater_targets: tuple[np.ndarray, np.ndarray] | None = None
        self._carnivore_targets: tuple[np.ndarray, np.ndarray] | None = None
        self._alpha_targets: tuple[np.ndarray, np.ndarray] | None = None
        self._decomposer_targets: tuple[np.ndarray, np.ndarray, str] | None = None
        self.river_segments: list[RiverSegment] = []
        # Steering update throttling for performance - very aggressive
        self._steer_frame_counter = 0
        self._steer_update_interval = 15  # Update steering every 15 frames
        self._collision_frame_counter = 0
        self._collision_update_interval = 20  # Update collision every 20 frames
        self._resolve_frame_counter = 0
        self._resolve_update_interval = 10  # Update eating/predation every 10 frames
        self._frame_counter = 0  # Track frames for caching

    def update(self, dt: float) -> None:
        if self.state.count == 0:
            return
        self._frame_counter += 1
        
        # CRITICAL: Invalidate alive indices cache every frame
        if hasattr(self, '_cached_alive_indices'):
            delattr(self, '_cached_alive_indices')
        
        # PERFORMANCE: Only work with alive entities to avoid processing dead ones
        # This is critical - count never decreases, so we must filter early
        # Use a reasonable slice size based on alive count
        max_check = min(self.state.alive_count + 200, self.state.count)
        idx = slice(0, max_check)
        prev_alive = self.state.alive_mask[idx].copy()
        
        # CRITICAL: Clean up accumulating seeds and corpses to prevent slowdown
        self._cleanup_seeds_and_corpses(dt)
        
        self._update_trees(dt)
        
        # Steering calculations (throttled for performance - expensive O(n²) operations)
        self._steer_frame_counter += 1
        if self._steer_frame_counter >= self._steer_update_interval:
            self._steer_herbivores()
            self._steer_tree_eaters()
            self._steer_carnivores()
            self._steer_alpha_predators()
            self._steer_decomposers()
            self._steer_frame_counter = 0
        
        # Simple collision avoidance (throttled to reduce CPU load)
        self._collision_frame_counter += 1
        if self._collision_frame_counter >= self._collision_update_interval:
            self._apply_collision_avoidance()
            self._collision_frame_counter = 0
        
        self._pin_static_entities()
        if self.kernel_engine is not None:
            self.kernel_engine.step(
                self.state,
                dt,
                self.tuning.wander_strength,
                self.tuning.max_speed,
                WINDOW_WIDTH,
                WINDOW_HEIGHT,
            )
        else:
            self._update_numpy(dt)
        self._apply_river_currents()
        
        # Resolve eating/predation (throttled - expensive O(n²) distance matrices)
        self._resolve_frame_counter += 1
        if self._resolve_frame_counter >= self._resolve_update_interval:
            self._resolve_tree_eating()
            self._resolve_tree_eater_damage()
            self._resolve_predation(
                EntityType.CARNIVORE,
                [EntityType.HERBIVORE, EntityType.TREE_EATER],
                self.tuning.carnivore_bite_radius,
                self.tuning.carnivore_energy_gain,
            )
            self._resolve_predation(
                EntityType.ALPHA_PREDATOR,
                [EntityType.HERBIVORE, EntityType.TREE_EATER, EntityType.CARNIVORE, EntityType.DECOMPOSER],
                self.tuning.alpha_bite_radius,
                self.tuning.alpha_energy_gain,
            )
            self._resolve_decomposition()
            self._resolve_frame_counter = 0
        
        self._handle_new_corpses(prev_alive)

    def _update_numpy(self, dt: float) -> None:
        # CRITICAL: Only process alive entities, not full count
        alive_idx = self._alive_indices()
        if alive_idx.size == 0:
            return

        positions = self.state.positions[alive_idx]
        velocities = self.state.velocities[alive_idx]
        energy = self.state.energy[alive_idx]
        entity_types = self.state.entity_type[alive_idx]

        self._apply_wander(velocities, dt)
        self._clamp_speed(velocities)
        positions += velocities * dt
        np.mod(positions[:, 0], WINDOW_WIDTH, out=positions[:, 0])
        np.mod(positions[:, 1], WINDOW_HEIGHT, out=positions[:, 1])

        self._apply_energy_decay(energy, entity_types, dt)
        died = energy <= 0.0
        self.state.alive_mask[alive_idx[died]] = False

    def _apply_wander(self, velocities: np.ndarray, dt: float) -> None:
        jitter = self.rng.normal(scale=1.0, size=velocities.shape).astype(np.float32)
        velocities += jitter * self.tuning.wander_strength * dt

    def _clamp_speed(self, velocities: np.ndarray) -> None:
        speeds = np.linalg.norm(velocities, axis=1, keepdims=True)
        max_speed = self.tuning.max_speed
        mask = speeds[:, 0] > max_speed
        if np.any(mask):
            velocities[mask] *= (max_speed / (speeds[mask] + 1e-5))

    def _apply_energy_decay(self, energy: np.ndarray, entity_types: np.ndarray, dt: float) -> None:
        decay = self._decay_lut[entity_types]
        energy -= decay * dt

    def _build_decay_lut(self) -> np.ndarray:
        max_type = max(e.value for e in EntityType) + 1
        lut = np.full(max_type, 0.02, dtype=np.float32)
        for entity_type, value in self.tuning.health_decay.items():
            lut[int(entity_type)] = np.float32(value)
        return lut

    def _resolve_backend(self, backend: str) -> str:
        backend = backend.lower()
        if backend == "auto":
            backend = "taichi" if TI_AVAILABLE else "numpy"
        if backend == "taichi" and not TI_AVAILABLE:
            backend = "numpy"
        if backend not in {"taichi", "numpy"}:
            raise ValueError(f"Unknown backend '{backend}'")
        return backend

    def set_river(self, segments: list[RiverSegment]) -> None:
        self.river_segments = segments

    def _type_mask(self, entity_type: EntityType) -> np.ndarray:
        # PERFORMANCE: Only check alive entities, return compact mask
        alive_idx = self._alive_indices()
        if alive_idx.size == 0:
            return np.array([], dtype=np.int32)
        type_match = self.state.entity_type[alive_idx] == int(entity_type)
        return alive_idx[type_match]  # Return indices directly, not full mask

    def _assign_random_motion(self, indices: np.ndarray, speed: float) -> None:
        if indices.size == 0:
            return
        idx = self._entity_slice()
        # Add individual variation - each entity gets slightly different direction
        jitter = self.rng.normal(size=(indices.size, 2)).astype(np.float32)
        jitter /= np.linalg.norm(jitter, axis=1, keepdims=True) + 1e-6
        # Blend with existing velocity for smoother transitions
        current_velocities = self.state.velocities[idx][indices]
        new_velocities = jitter * speed
        blended = new_velocities * 0.6 + current_velocities * 0.4
        self.state.velocities[idx][indices] = blended
    
    def _apply_collision_avoidance(self) -> None:
        """Simple collision avoidance - entities push away from nearby neighbors."""
        # PERFORMANCE: Only process alive entities
        alive_indices = self._alive_indices()
        if alive_indices.size == 0:
            return
        
        idx = self._entity_slice()
        # Only apply to non-tree entities
        non_tree_mask = (self.state.entity_type[idx][alive_indices] != int(EntityType.TREE))
        if not np.any(non_tree_mask):
            return
        
        entity_indices = alive_indices[non_tree_mask]
        if entity_indices.size < 2:
            return
        
        # Use direct indexing since entity_indices are already filtered
        positions = self.state.positions[entity_indices]
        velocities = self.state.velocities[entity_indices].copy()
        
        avoidance_radius = 25.0
        avoidance_radius_sq = avoidance_radius ** 2
        avoidance_strength = 12.0
        
        # PERFORMANCE: Only process a random subset of entities per frame (very reduced)
        max_entities_to_process = min(30, entity_indices.size)  # Very reduced
        if entity_indices.size > max_entities_to_process:
            process_indices = self.rng.choice(entity_indices.size, max_entities_to_process, replace=False)
        else:
            process_indices = np.arange(entity_indices.size)
        
        # For each entity, only check a small random sample of other entities
        max_neighbors_to_check = min(5, entity_indices.size - 1)  # Very reduced
        
        for i in process_indices:
            pos_i = positions[i]
            
            # Sample random neighbors to check
            other_indices = np.delete(np.arange(entity_indices.size), i)
            if len(other_indices) > max_neighbors_to_check:
                sample_idx = self.rng.choice(len(other_indices), max_neighbors_to_check, replace=False)
                check_indices = other_indices[sample_idx]
            else:
                check_indices = other_indices
            
            # Check distances to sampled neighbors
            diff = positions[check_indices] - pos_i
            dist_sq = np.sum(diff**2, axis=1)
            too_close = dist_sq < avoidance_radius_sq
            
            if not np.any(too_close):
                continue
            
            # Calculate repulsion
            nearby_diff = diff[too_close]
            nearby_dist_sq = dist_sq[too_close]
            nearby_dist = np.sqrt(nearby_dist_sq[:, None]) + 1e-5
            repulsion = -nearby_diff / nearby_dist
            weights = 1.0 / (nearby_dist_sq + 1e-5)
            total_repulsion = np.sum(repulsion * weights[:, None], axis=0)
            norm = np.linalg.norm(total_repulsion) + 1e-5
            total_repulsion /= norm
            
            velocities[i] += total_repulsion * avoidance_strength
        
        self.state.velocities[entity_indices] = velocities

    def _apply_river_currents(self) -> None:
        if not self.river_segments:
            return
        alive_idx = self._alive_indices()
        non_tree_mask = self.state.entity_type[alive_idx] != int(EntityType.TREE)
        if not np.any(non_tree_mask):
            return
        entity_indices = alive_idx[non_tree_mask]
        positions = self.state.positions[entity_indices]
        velocities = self.state.velocities[entity_indices]
        for segment in self.river_segments:
            inside = segment.contains_points(subset)
            if not np.any(inside):
                continue
            drift = np.array(
                [segment.flow_x, segment.flow_y], dtype=np.float32
            ) * self.tuning.river_force
            positions[inside] += drift
            velocities[inside] += drift * 0.3
        self.state.positions[entity_indices] = positions
        self.state.velocities[entity_indices] = velocities

    # --- Trees & herbivores -------------------------------------------------

    def _entity_slice(self) -> slice:
        # CRITICAL FIX: Only iterate over alive entities, not full count
        # This prevents linear slowdown as count grows
        alive_count = self.state.alive_count
        return slice(0, min(alive_count + 100, self.state.count))  # Small buffer for safety
    
    def _alive_indices(self) -> np.ndarray:
        """Get indices of all alive entities - use this for expensive operations."""
        # CRITICAL: Cache this to avoid recalculating every frame
        if not hasattr(self, '_cached_alive_indices') or self._alive_indices_frame != getattr(self, '_frame_counter', 0):
            idx = slice(0, self.state.count)
            self._cached_alive_indices = np.nonzero(self.state.alive_mask[idx])[0]
            self._alive_indices_frame = getattr(self, '_frame_counter', 0)
        return self._cached_alive_indices

    def _tree_mask(self) -> np.ndarray:
        # PERFORMANCE: Return indices directly
        alive_idx = self._alive_indices()
        if alive_idx.size == 0:
            return np.array([], dtype=np.int32)
        type_match = self.state.entity_type[alive_idx] == int(EntityType.TREE)
        return alive_idx[type_match]

    def _herbivore_mask(self) -> np.ndarray:
        # PERFORMANCE: Return indices directly
        alive_idx = self._alive_indices()
        if alive_idx.size == 0:
            return np.array([], dtype=np.int32)
        type_match = self.state.entity_type[alive_idx] == int(EntityType.HERBIVORE)
        return alive_idx[type_match]

    def _update_trees(self, dt: float) -> None:
        tree_indices = self._tree_mask()
        if tree_indices.size == 0:
            return
        fruit = self.state.tree_fruit[tree_indices]
        capacity = self.state.tree_fruit_capacity[tree_indices]
        growable_mask = fruit < capacity - 0.1
        growable = tree_indices[growable_mask]
        if growable.size == 0:
            return
        growth_prob = self.tuning.tree_growth_rate * dt * TARGET_FPS
        rand = self.rng.random(growable.size)
        grow_indices = growable[rand < growth_prob]
        if grow_indices.size:
            self.state.tree_fruit[grow_indices] += 1.0

    def _pin_static_entities(self) -> None:
        tree_indices = self._tree_mask()
        if tree_indices.size > 0:
            self.state.velocities[tree_indices] = 0.0

    def _steer_herbivores(self) -> None:
        herb_indices = self._herbivore_mask()
        if herb_indices.size == 0:
            return
        herb_energy = self.state.energy[herb_indices]

        hungry_mask = herb_energy < self.tuning.herbivore_hungry_threshold
        hungry_indices = herb_indices[hungry_mask]
        satiated_indices = herb_indices[~hungry_mask]

        # Set random wander for satiated herbivores (with strong individual variation)
        if satiated_indices.size:
            # Each entity gets a unique random direction
            rand = self.rng.normal(size=(satiated_indices.size, 2)).astype(np.float32)
            rand /= np.linalg.norm(rand, axis=1, keepdims=True) + 1e-6
            
            # Add per-entity speed variation (some move faster/slower)
            speed_multipliers = self.rng.uniform(0.7, 1.3, size=satiated_indices.size).astype(np.float32)
            speeds = self.tuning.herbivore_idle_speed * speed_multipliers[:, None]
            new_velocities = rand * speeds
            
            # Blend with existing velocity for smoother movement (more conservative blend)
            current_velocities = self.state.velocities[satiated_indices]
            blended = new_velocities * 0.4 + current_velocities * 0.6
            self.state.velocities[satiated_indices] = blended

        if not hungry_indices.size:
            return

        tree_mask = (
            (self.state.entity_type[idx] == int(EntityType.TREE))
            & self.state.alive_mask[idx]
            & (self.state.tree_fruit[idx] > 0.1)
        )
        if not np.any(tree_mask):
            # No fruiting trees; wander instead (with strong individual variation)
            rand = self.rng.normal(size=(hungry_indices.size, 2)).astype(np.float32)
            rand /= np.linalg.norm(rand, axis=1, keepdims=True) + 1e-6
            
            # Add per-entity speed variation
            speed_multipliers = self.rng.uniform(0.7, 1.3, size=hungry_indices.size).astype(np.float32)
            speeds = self.tuning.herbivore_idle_speed * speed_multipliers[:, None]
            new_velocities = rand * speeds
            
            # Blend with existing velocity (more conservative)
            current_velocities = self.state.velocities[hungry_indices]
            blended = new_velocities * 0.4 + current_velocities * 0.6
            self.state.velocities[hungry_indices] = blended
            return

        # Optimized: sample random trees instead of computing full distance matrix
        tree_indices_full = self._tree_mask()
        tree_mask_fruit = (self.state.tree_fruit[tree_indices_full] > 0.1)
        tree_indices = tree_indices_full[tree_mask_fruit]
        if tree_indices.size == 0:
            return
        
        tree_positions = self.state.positions[tree_indices]
        hungry_positions = self.state.positions[hungry_indices]
        current_velocities = self.state.velocities[hungry_indices]
        directions = np.zeros((hungry_indices.size, 2), dtype=np.float32)
        
        # PERFORMANCE: Sample only 3 random trees per herbivore for maximum speed
        max_trees_to_check = min(3, tree_indices.size)
        
        for i in range(hungry_indices.size):
            pos = hungry_positions[i]
            
            # Sample random subset of trees
            if tree_indices.size > max_trees_to_check:
                sample_idx = self.rng.choice(tree_indices.size, max_trees_to_check, replace=False)
                sample_positions = tree_positions[sample_idx]
            else:
                sample_positions = tree_positions
            
            # Find closest among samples
            diff = sample_positions - pos
            dist_sq = np.sum(diff**2, axis=1)
            closest_idx = np.argmin(dist_sq)
            direction = diff[closest_idx]
            
            # Normalize direction
            norm = np.linalg.norm(direction) + 1e-6
            direction = direction / norm
            
            # Add per-entity random angle offset for individual variation
            angle_offset = self.rng.uniform(-0.6, 0.6)
            cos_a = np.cos(angle_offset)
            sin_a = np.sin(angle_offset)
            rotated_x = direction[0] * cos_a - direction[1] * sin_a
            rotated_y = direction[0] * sin_a + direction[1] * cos_a
            direction = np.array([rotated_x, rotated_y], dtype=np.float32)
            
            # Add jitter
            jitter = self.rng.normal(scale=self.tuning.herbivore_target_jitter, size=2).astype(np.float32)
            direction += jitter
            norm = np.linalg.norm(direction) + 1e-6
            directions[i] = direction / norm
        
        # Apply seek velocity with heavy blending for smooth, individual movement
        seek_velocities = directions * self.tuning.herbivore_seek_speed
        wander_component = self.rng.normal(scale=8.0, size=(hungry_indices.size, 2)).astype(np.float32)
        
        # Blend: 35% new direction, 55% old velocity, 10% random wander
        blended = seek_velocities * 0.35 + current_velocities * 0.55 + wander_component * 0.1
        
        # Normalize to maintain speed
        speeds = np.linalg.norm(blended, axis=1, keepdims=True) + 1e-5
        target_speeds = np.full((hungry_indices.size, 1), self.tuning.herbivore_seek_speed, dtype=np.float32)
        blended = (blended / speeds) * target_speeds
        
        self.state.velocities[hungry_indices] = blended

    def _steer_tree_eaters(self) -> None:
        eater_idx = self._type_mask(EntityType.TREE_EATER)
        if eater_idx.size == 0:
            self._tree_eater_targets = None
            return
        tree_idx = self._tree_mask()
        if tree_idx.size == 0:
            self._assign_random_motion(eater_idx, self.tuning.tree_eater_idle_speed)
            self._tree_eater_targets = None
            return
        eater_positions = self.state.positions[eater_idx]
        tree_positions = self.state.positions[tree_idx]
        
        # PERFORMANCE: Sample trees instead of checking all (very reduced)
        max_trees_to_check = min(5, tree_idx.size)
        closest_tree_indices = np.zeros(eater_idx.size, dtype=np.int32)
        directions = np.zeros((eater_idx.size, 2), dtype=np.float32)
        
        for i, eater_pos in enumerate(eater_positions):
            if tree_idx.size > max_trees_to_check:
                sample_idx = self.rng.choice(tree_idx.size, max_trees_to_check, replace=False)
                check_positions = tree_positions[sample_idx]
                check_indices = tree_idx[sample_idx]
            else:
                check_positions = tree_positions
                check_indices = tree_idx
            
            diff = check_positions - eater_pos
            dist_sq = np.sum(diff**2, axis=1)
            closest_local = np.argmin(dist_sq)
            closest_tree_indices[i] = check_indices[closest_local]
            directions[i] = diff[closest_local]
        
        directions += self.rng.normal(
            scale=self.tuning.tree_eater_target_jitter, size=directions.shape
        ).astype(np.float32)
        norms = np.linalg.norm(directions, axis=1, keepdims=True) + 1e-6
        directions /= norms
        self.state.velocities[eater_idx] = directions * self.tuning.tree_eater_speed
        self._tree_eater_targets = (eater_idx, closest_tree_indices)

    def _steer_carnivores(self) -> None:
        self._carnivore_targets = self._steer_predator(
            EntityType.CARNIVORE,
            [EntityType.HERBIVORE, EntityType.TREE_EATER],
            self.tuning.carnivore_speed,
            self.tuning.carnivore_jitter,
        )

    def _steer_alpha_predators(self) -> None:
        self._alpha_targets = self._steer_predator(
            EntityType.ALPHA_PREDATOR,
            [
                EntityType.HERBIVORE,
                EntityType.TREE_EATER,
                EntityType.CARNIVORE,
                EntityType.DECOMPOSER,
            ],
            self.tuning.alpha_speed,
            self.tuning.alpha_jitter,
        )

    def _steer_decomposers(self) -> None:
        dec_indices = self._type_mask(EntityType.DECOMPOSER)
        if dec_indices.size == 0:
            self._decomposer_targets = None
            return
        dec_positions = self.state.positions[idx][dec_indices]

        target_kind = None
        target_positions = None
        target_indices = None

        corpse_alive = self.state.corpse_alive
        if np.any(corpse_alive):
            target_kind = "corpse"
            target_indices = np.nonzero(corpse_alive)[0]
            target_positions = self.state.corpse_positions[corpse_alive]
        elif np.any(self.state.seed_alive):
            target_kind = "seed"
            target_indices = np.nonzero(self.state.seed_alive)[0]
            target_positions = self.state.seed_positions[target_indices]

        if target_positions is None or target_positions.size == 0:
            self._assign_random_motion(dec_indices, self.tuning.decomposer_speed * 0.5)
            self._decomposer_targets = None
            return

        # PERFORMANCE: Sample targets instead of full matrix (very reduced)
        max_targets_to_check = min(5, target_indices.size)
        closest_targets = np.zeros(dec_indices.size, dtype=np.int32)
        directions = np.zeros((dec_indices.size, 2), dtype=np.float32)
        
        for i, dec_pos in enumerate(dec_positions):
            if target_indices.size > max_targets_to_check:
                sample_idx = self.rng.choice(target_indices.size, max_targets_to_check, replace=False)
                check_positions = target_positions[sample_idx]
                check_indices = target_indices[sample_idx]
            else:
                check_positions = target_positions
                check_indices = target_indices
            
            diff = check_positions - dec_pos
            dist_sq = np.sum(diff**2, axis=1)
            closest_local = np.argmin(dist_sq)
            closest_targets[i] = check_indices[closest_local]
            directions[i] = diff[closest_local]
        
        directions += self.rng.normal(
            scale=self.tuning.decomposer_jitter, size=directions.shape
        ).astype(np.float32)
        norms = np.linalg.norm(directions, axis=1, keepdims=True) + 1e-6
        directions /= norms
        self.state.velocities[dec_indices] = directions * self.tuning.decomposer_speed
        self._decomposer_targets = (
            dec_indices,
            closest_targets,
            target_kind,
        )

    def _steer_predator(
        self,
        predator_type: EntityType,
        prey_types: list[EntityType],
        speed: float,
        jitter: float,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        pred_indices = self._type_mask(predator_type)
        if pred_indices.size == 0:
            return None
        
        # Get alive prey indices
        alive_idx = self._alive_indices()
        prey_indices = np.array([], dtype=np.int32)
        for prey_type in prey_types:
            type_match = self.state.entity_type[alive_idx] == int(prey_type)
            prey_indices = np.concatenate([prey_indices, alive_idx[type_match]])
        
        if prey_indices.size == 0:
            self._assign_random_motion(pred_indices, speed * 0.5)
            return None
        
        pred_positions = self.state.positions[pred_indices]
        prey_positions = self.state.positions[prey_indices]
        
        # PERFORMANCE: Sample prey instead of checking all (very reduced)
        max_prey_to_check = min(5, prey_indices.size)
        closest_prey_indices = np.zeros(pred_indices.size, dtype=np.int32)
        directions = np.zeros((pred_indices.size, 2), dtype=np.float32)
        
        for i, pred_pos in enumerate(pred_positions):
            if prey_indices.size > max_prey_to_check:
                sample_idx = self.rng.choice(prey_indices.size, max_prey_to_check, replace=False)
                check_positions = prey_positions[sample_idx]
                check_indices = prey_indices[sample_idx]
            else:
                check_positions = prey_positions
                check_indices = prey_indices
            
            diff = check_positions - pred_pos
            dist_sq = np.sum(diff**2, axis=1)
            closest_local = np.argmin(dist_sq)
            closest_prey_indices[i] = check_indices[closest_local]
            directions[i] = diff[closest_local]
        
        directions += self.rng.normal(scale=jitter, size=directions.shape).astype(
            np.float32
        )
        norms = np.linalg.norm(directions, axis=1, keepdims=True) + 1e-6
        directions /= norms
        self.state.velocities[pred_indices] = directions * speed
        return pred_indices, closest_prey_indices

    def _resolve_tree_eating(self) -> None:
        herb_indices = self._herbivore_mask()
        if herb_indices.size == 0:
            return
        
        tree_indices_full = self._tree_mask()
        tree_mask_fruit = (self.state.tree_fruit[tree_indices_full] > 0.1)
        tree_indices = tree_indices_full[tree_mask_fruit]
        if tree_indices.size == 0:
            return

        herb_positions = self.state.positions[herb_indices]
        tree_positions = self.state.positions[tree_indices]
        
        # PERFORMANCE: Check each herbivore against sampled trees instead of full matrix
        eat_radius_sq = self.tuning.herbivore_eat_radius ** 2
        max_trees_to_check = min(5, tree_indices.size)  # Very reduced
        consumed_herbivores: set[int] = set()
        
        for i, h_idx in enumerate(herb_indices):
            if h_idx in consumed_herbivores:
                continue
            herb_pos = herb_positions[i]
            
            # Sample random subset of trees
            if tree_indices.size > max_trees_to_check:
                sample_idx = self.rng.choice(tree_indices.size, max_trees_to_check, replace=False)
                check_trees = tree_indices[sample_idx]
                check_positions = tree_positions[sample_idx]
            else:
                check_trees = tree_indices
                check_positions = tree_positions
            
            # Check distances
            diff = check_positions - herb_pos
            dist_sq = np.sum(diff**2, axis=1)
            in_range = dist_sq < eat_radius_sq
            
            if not np.any(in_range):
                continue
            
            # Find closest tree in range
            in_range_idx = np.nonzero(in_range)[0]
            closest_local = in_range_idx[np.argmin(dist_sq[in_range])]
            t_idx = int(check_trees[closest_local])
            
            if self.state.tree_fruit[t_idx] <= 0:
                continue
            
            consumed_herbivores.add(h_idx)
            self.state.tree_fruit[t_idx] = max(
                0.0, self.state.tree_fruit[t_idx] - 1.0
            )
            self.state.energy[h_idx] = min(
                1.0, self.state.energy[h_idx] + self.tuning.herbivore_energy_gain
            )
            if self.rng.random() < 0.35:
                pos = self.state.positions[h_idx]
                self.state.add_seed(
                    float(pos[0] + self.rng.normal(scale=3.0)),
                    float(pos[1] + self.rng.normal(scale=3.0)),
                )

    def _resolve_tree_eater_damage(self) -> None:
        data = self._tree_eater_targets
        if not data:
            return
        eater_indices, tree_indices = data
        if eater_indices.size == 0:
            return
        pair_mask = self.state.alive_mask[eater_indices] & self.state.alive_mask[tree_indices]
        if not np.any(pair_mask):
            return
        eaters = eater_indices[pair_mask]
        trees = tree_indices[pair_mask]
        eater_positions = self.state.positions[eaters]
        tree_positions = self.state.positions[trees]
        diff = eater_positions - tree_positions
        dist_sq = np.sum(diff**2, axis=1)
        hits = dist_sq < (self.tuning.tree_eater_bite_radius**2)
        if not np.any(hits):
            return
        hit_trees = trees[hits]
        self.state.tree_fruit[hit_trees] = np.maximum(
            0.0, self.state.tree_fruit[hit_trees] - 1.0
        )
        self.state.energy[hit_trees] -= self.tuning.tree_eater_damage
        dead_trees = hit_trees[self.state.energy[hit_trees] <= 0.0]
        if dead_trees.size:
            self.state.alive_mask[dead_trees] = False
        hit_eaters = eaters[hits]
        for eater_idx in hit_eaters:
            if self.rng.random() < self.tuning.tree_eater_seed_chance:
                pos = self.state.positions[eater_idx]
                self.state.add_seed(
                    float(pos[0] + self.rng.normal(scale=4.0)),
                    float(pos[1] + self.rng.normal(scale=4.0)),
                    from_fruit=False,
                )

    def _resolve_predation(
        self,
        predator_type: EntityType,
        prey_types: list[EntityType],
        bite_radius: float,
        energy_gain: float,
        alpha: bool = False,
    ) -> None:
        pred_indices = self._type_mask(predator_type)
        if pred_indices.size == 0:
            return
        
        # Get alive prey indices
        alive_idx = self._alive_indices()
        prey_indices = np.array([], dtype=np.int32)
        for prey in prey_types:
            type_match = self.state.entity_type[alive_idx] == int(prey)
            prey_indices = np.concatenate([prey_indices, alive_idx[type_match]])
        
        if prey_indices.size == 0:
            return
        
        pred_positions = self.state.positions[pred_indices]
        prey_positions = self.state.positions[prey_indices]
        
        # PERFORMANCE: Instead of full distance matrix, check each predator against sampled prey
        bite_radius_sq = bite_radius ** 2
        max_prey_to_check = min(8, prey_indices.size)  # Very reduced for performance
        
        for i, pred_idx in enumerate(pred_indices):
            pred_pos = pred_positions[i]
            
            # Sample random subset of prey
            if prey_indices.size > max_prey_to_check:
                sample_idx = self.rng.choice(prey_indices.size, max_prey_to_check, replace=False)
                check_prey = prey_indices[sample_idx]
                check_positions = prey_positions[sample_idx]
            else:
                check_prey = prey_indices
                check_positions = prey_positions
            
            # Find closest prey among samples
            diff = check_positions - pred_pos
            dist_sq = np.sum(diff**2, axis=1)
            closest_idx = np.argmin(dist_sq)
            
            if dist_sq[closest_idx] < bite_radius_sq:
                prey_idx = check_prey[closest_idx]
                if not self.state.alive_mask[prey_idx]:
                    continue
                self.state.alive_mask[prey_idx] = False
                self.state.energy[pred_idx] = np.clip(
                    self.state.energy[pred_idx] + energy_gain, 0.0, 1.5
                )
                pos = self.state.positions[prey_idx]
                size = float(self.state.size[prey_idx])
                self.state.add_corpse(float(pos[0]), float(pos[1]), size)
                if alpha and self.rng.random() < 0.5:
                    self.state.add_seed(
                        float(pos[0] + self.rng.normal(scale=5.0)),
                        float(pos[1] + self.rng.normal(scale=5.0)),
                        from_fruit=False,
                    )

    def _resolve_decomposition(self) -> None:
        data = self._decomposer_targets
        if not data:
            return
        dec_indices, target_indices, target_kind = data
        if dec_indices.size == 0:
            return
        dec_positions = self.state.positions[dec_indices]
        radius_sq = self.tuning.decomposer_consume_radius**2
        if target_kind == "corpse":
            alive_mask = self.state.corpse_alive[target_indices]
            if not np.any(alive_mask):
                return
            targets = target_indices[alive_mask]
            consumers = dec_indices[alive_mask]
            target_positions = self.state.corpse_positions[targets]
            diff = target_positions - dec_positions[alive_mask]
            dist_sq = np.sum(diff**2, axis=1)
            hits = dist_sq < radius_sq
            if not np.any(hits):
                return
            consume_targets = targets[hits]
            consumers = consumers[hits]
            self.state.corpse_decay[consume_targets] -= (
                self.tuning.decomposer_consume_radius * 4.0
            )
            depleted = consume_targets[self.state.corpse_decay[consume_targets] <= 0]
            if depleted.size:
                self.state.corpse_alive[depleted] = False
            self.state.energy[consumers] = np.clip(
                self.state.energy[consumers] + self.tuning.decomposer_energy_gain,
                0.0,
                1.2,
            )
        elif target_kind == "seed":
            alive_mask = self.state.seed_alive[target_indices]
            if not np.any(alive_mask):
                return
            targets = target_indices[alive_mask]
            consumers = dec_indices[alive_mask]
            target_positions = self.state.seed_positions[targets]
            diff = target_positions - dec_positions[alive_mask]
            dist_sq = np.sum(diff**2, axis=1)
            hits = dist_sq < radius_sq
            if not np.any(hits):
                return
            consume_targets = targets[hits]
            consumers = consumers[hits]
            self.state.seed_alive[consume_targets] = False
            self.state.energy[consumers] = np.clip(
                self.state.energy[consumers] + self.tuning.decomposer_energy_gain,
                0.0,
                1.2,
            )
        self._decomposer_targets = None

    def _cleanup_seeds_and_corpses(self, dt: float) -> None:
        """CRITICAL: Clean up accumulating seeds and corpses to prevent performance degradation."""
        # Clean up old seeds (auto-expire after 30 seconds)
        seed_timer_threshold = 30.0
        alive_seeds = self.state.seed_alive
        if np.any(alive_seeds):
            self.state.seed_timer[alive_seeds] += dt
            expired = alive_seeds & (self.state.seed_timer >= seed_timer_threshold)
            if np.any(expired):
                self.state.seed_alive[expired] = False
                self.state.seed_timer[expired] = 0.0
        
        # Clean up old corpses (auto-decay after 60 seconds if not consumed)
        corpse_decay_rate = 1.0  # Decay per second
        alive_corpses = self.state.corpse_alive
        if np.any(alive_corpses):
            self.state.corpse_decay[alive_corpses] -= corpse_decay_rate * dt
            depleted = alive_corpses & (self.state.corpse_decay <= 0.0)
            if np.any(depleted):
                self.state.corpse_alive[depleted] = False
                self.state.corpse_decay[depleted] = 0.0

    def _handle_new_corpses(self, prev_alive: np.ndarray) -> None:
        # Only check entities in the slice we're tracking
        idx = slice(0, min(len(prev_alive), self.state.count))
        alive_now = self.state.alive_mask[idx]
        died = prev_alive & ~alive_now
        if not np.any(died):
            return
        died_indices = np.nonzero(died)[0]
        types = self.state.entity_type[idx][died_indices]
        animal_types = [
            int(EntityType.HERBIVORE),
            int(EntityType.TREE_EATER),
            int(EntityType.CARNIVORE),
            int(EntityType.DECOMPOSER),
            int(EntityType.ALPHA_PREDATOR),
        ]
        animal_mask = np.isin(types, animal_types)
        if not np.any(animal_mask):
            return
        animal_died_indices = died_indices[animal_mask]
        positions = self.state.positions[idx][animal_died_indices]
        sizes = self.state.size[idx][animal_died_indices]
        for pos, size in zip(positions, sizes):
            self.state.add_corpse(float(pos[0]), float(pos[1]), float(size))


