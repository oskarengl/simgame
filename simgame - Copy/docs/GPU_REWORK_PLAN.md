# GPU Re-architecture Plan

## Goals

- Sustain 10,000+ autonomous entities at 60 FPS on an NVIDIA RTX 2070.
- Preserve all current ecological mechanics (trees, fruits, seeds, walls, rivers, predators, decomposers, UI stats) after the new core is solid.
- Keep the project hackable in pure Python while offloading both rendering and heavy simulation work to the GPU.

## High-level Strategy

1. **Separate Simulation From Rendering**
   - Introduce a `simgame/` package with `simulation`, `rendering`, and `ui` submodules.
   - Maintain a single source of truth (`SimulationState`) that stores SoA (structure-of-arrays) data buffers for positions, velocities, health, hunger, entity type, etc.
   - Rendering code consumes read-only views of those buffers; the simulation updates them.

2. **Data-oriented Entity Model**
   - Replace thousands of Python objects with contiguous GPU-friendly arrays (NumPy initially, CuPy/Taichi-backed later).
   - Each agent type becomes an integer enum; behaviour is expressed as vectorized kernels that operate on slices of the arrays.
   - Spatial indexing uses a GPU-friendly uniform grid (flat arrays of cell heads & linked lists) to keep neighbour queries O(k) rather than O(n²).

3. **GPU Simulation Kernels**
   - Author kernels in [Taichi](https://www.taichi-lang.org/) so the same Python code JITs to CUDA on Windows/NVIDIA.
   - Critical kernels:
     - Movement & steering (seek targets, flee predators, wander).
     - Resource scans (trees with fruit, bodies for decomposers) via spatial grid.
     - Interaction/resolution (eat, reproduce, drop seeds).
   - Keep a CPU/NumPy fallback for development environments without CUDA.

4. **Modern GPU Rendering**
   - Switch from Pygame to instanced rendering (via `arcade`’s sprite lists or `moderngl`).
   - Batch each entity class into a `SpriteList`/instance buffer so 10k quads render in a handful of draw calls.
   - Dynamically stream transformed positions/colors from the simulation buffers each frame using `GL_DYNAMIC_DRAW`.
   - UI overlays (graphs, stats) use lightweight batched draw calls separate from the heavy scene pass.

5. **Progressive Feature Reintroduction**
   - **Phase 1 (Core Loop)**: movement, hunger decay, basic eating (trees/fruits, predators vs prey), reproduction, deaths, stats capture.
   - **Phase 2 (Environment)**: rivers (vector fields), mud puddles (speed modifiers), caves/walls, decomposer stink radius.
   - **Phase 3 (Builder Tools)**: mouse-driven spawning/walls, dropdown UI, entity inspection panel.

## Files / Modules (planned)

```
simgame/
  __init__.py
  config.py          # shared constants/enums
  state.py           # SimulationState structure-of-arrays buffers
  simulation/
    __init__.py
    kernels.py       # Taichi kernels (GPU) & numpy fallbacks
    scheduler.py     # steps orchestrator & spawning logic
  rendering/
    __init__.py
    window.py        # Arcade/Moderngl window + input handling
    sprites.py       # sprite batch definitions per entity type
  ui/
    hud.py           # stats graphs, population history
main_gpu.py          # entry point for new pipeline
```

## Implementation Milestones

1. **Scaffolding (current task)**
   - Create `simgame/` package and `SimulationState` with SoA buffers.
   - Stand up an `arcade` window that renders GPU-backed instanced sprites fed from the buffers.
   - Port a minimal subset of behaviours (wander + basic hunger) to prove the loop works at 10k agents.

2. **GPU Kernels**
   - Introduce Taichi kernels for update steps, toggled via config flag.
   - Profile & tune occupancy (block sizes, shared memory usage) to keep 60 FPS at 10k entities on RTX 2070.

3. **Mechanics Port**
   - Rebuild each mechanic atop the new kernels, ensuring parity with the Pygame version.
   - Validate via automated scenarios (scripted seeds/animals counts) to avoid regressions.

4. **UI / Tooling**
   - Re-implement the dropdown, stats graphs, entity inspector using `arcade.gui`.
   - Provide runtime switches (speed multiplier, spawn tools) and profiling HUD (GPU/CPU usage).

## Dependencies to Add

- `arcade>=3.0.0` – GPU-accelerated rendering & window/input layer.
- `taichi>=1.6.0` – portable CUDA kernels for agent updates.
- `numba>=0.59.0` – CPU fallback JIT for machines without CUDA.
- `numpy>=2.0.0` – base array storage (already required indirectly).

## Next Steps

1. Update `requirements.txt` with the new stack.
2. Add the `simgame/` scaffolding (state, simulation skeleton, renderer shell).
3. Implement a proof-of-concept loop in `main_gpu.py` that spawns 10k dummy agents and idles at 60 FPS to validate the rendering pipeline before porting behaviours.

