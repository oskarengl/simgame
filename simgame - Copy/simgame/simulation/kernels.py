import numpy as np

from ..config import EntityType

TI_AVAILABLE = False
_TAICHI_INITIALIZED = False

try:
    import taichi as ti

    TI_AVAILABLE = True
except Exception:  # pragma: no cover - Taichi might not be installed on CI
    ti = None  # type: ignore[assignment]


def _init_taichi() -> None:
    if not TI_AVAILABLE:
        raise RuntimeError("Taichi is not installed")
    global _TAICHI_INITIALIZED
    if _TAICHI_INITIALIZED:
        return
    # Try GPU backends first (CUDA for NVIDIA, Vulkan for AMD/Intel)
    for arch in (ti.cuda, ti.vulkan, ti.metal):
        try:
            ti.init(arch=arch, device_memory_fraction=0.5)  # type: ignore[arg-type]
            print(f"[Taichi] Initialized on GPU backend: {arch}")
            _TAICHI_INITIALIZED = True
            return
        except Exception as e:
            continue
    # Fallback to CPU only if GPU fails
    print("[Taichi] Warning: GPU backends failed, falling back to CPU (this will be slow!)")
    ti.init(arch=ti.cpu)
    _TAICHI_INITIALIZED = True


if TI_AVAILABLE:

    @ti.data_oriented
    class TaichiKernelEngine:
        """Runs the core simulation kernels on the GPU via Taichi."""

        def __init__(self, capacity: int, decay_lut: np.ndarray) -> None:
            self.capacity = capacity
            self.decay_lut = decay_lut
            _init_taichi()
            # PERFORMANCE: Use full capacity but only transfer alive entities
            self.positions = ti.Vector.field(2, dtype=ti.f32, shape=self.capacity)
            self.velocities = ti.Vector.field(2, dtype=ti.f32, shape=self.capacity)
            self.energy = ti.field(dtype=ti.f32, shape=self.capacity)
            self.entity_type = ti.field(dtype=ti.i32, shape=self.capacity)
            self.alive = ti.field(dtype=ti.i32, shape=self.capacity)
            self._alive_indices = np.array([], dtype=np.int32)

            self.decay = ti.field(dtype=ti.f32, shape=self.decay_lut.shape[0])
            self.decay.from_numpy(self.decay_lut.astype(np.float32))

            self.type_tree = ti.field(dtype=ti.i32, shape=())
            self.type_tree[None] = int(EntityType.TREE)

            # Scratch scalars
            self._dt = ti.field(dtype=ti.f32, shape=())
            self._wander = ti.field(dtype=ti.f32, shape=())
            self._max_speed = ti.field(dtype=ti.f32, shape=())
            self._width = ti.field(dtype=ti.f32, shape=())
            self._height = ti.field(dtype=ti.f32, shape=())

        def load_from_state(self, state) -> None:
            # PERFORMANCE: Transfer full arrays (Taichi fields are fixed size)
            # Kernel will skip dead entities via alive[i] check
            self.positions.from_numpy(state.positions)
            self.velocities.from_numpy(state.velocities)
            self.energy.from_numpy(state.energy)
            self.entity_type.from_numpy(state.entity_type)
            self.alive.from_numpy(state.alive_mask.astype(np.int32))

        def store_into_state(self, state) -> None:
            # PERFORMANCE: Transfer back full arrays
            state.positions[:, :] = self.positions.to_numpy()
            state.velocities[:, :] = self.velocities.to_numpy()
            state.energy[:] = self.energy.to_numpy()
            state.entity_type[:] = self.entity_type.to_numpy()
            state.alive_mask[:] = self.alive.to_numpy().astype(bool)

        @ti.kernel
        def _step(self, count: ti.i32):
            dt = self._dt[None]
            wander_strength = self._wander[None]
            max_speed = self._max_speed[None]
            width = self._width[None]
            height = self._height[None]

            for i in range(count):
                if self.alive[i] == 1:
                    if self.entity_type[i] == self.type_tree[None]:
                        continue
                    jitter = ti.Vector([ti.randn(ti.f32), ti.randn(ti.f32)]) * wander_strength * dt
                    self.velocities[i] += jitter

                    speed = self.velocities[i].norm()
                    if speed > max_speed:
                        factor = max_speed / (speed + 1e-5)
                        self.velocities[i] *= factor

                    self.positions[i] += self.velocities[i] * dt
                    if self.positions[i].x < 0:
                        self.positions[i].x += width
                    if self.positions[i].x >= width:
                        self.positions[i].x -= width
                    if self.positions[i].y < 0:
                        self.positions[i].y += height
                    if self.positions[i].y >= height:
                        self.positions[i].y -= height

                    decay = self.decay[self.entity_type[i]]
                    energy = self.energy[i] - decay * dt
                    self.energy[i] = energy
                    if energy <= 0.0:
                        self.alive[i] = 0

        def step(
            self,
            state,
            dt: float,
            wander_strength: float,
            max_speed: float,
            width: float,
            height: float,
        ) -> None:
            if state.count == 0:
                return
            self.load_from_state(state)
            self._dt[None] = dt
            self._wander[None] = wander_strength
            self._max_speed[None] = max_speed
            self._width[None] = width
            self._height[None] = height
            # Process all entities - kernel checks alive[i] inside loop to skip dead ones
            # This is efficient because the check is cheap and GPU parallelizes well
            self._step(state.count)
            self.store_into_state(state)

else:

    class TaichiKernelEngine:  # type: ignore[override]
        def __init__(self, *_, **__):
            raise RuntimeError("Taichi is not installed")


