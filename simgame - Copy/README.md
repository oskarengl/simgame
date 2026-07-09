# Ecological Simulation Game

A 2D top-down ecological simulation where different types of animals interact with trees, each other, and the environment.

## Features

- **Trees**: Grow fruits that herbivores can eat
- **Herbivores** (Green): Eat fruits from trees
- **Tree Eaters** (Orange): Eat trees directly
- **Carnivores** (Red): Hunt and eat other animals
- **Decomposers** (Purple): Consume dead animal bodies
- **River System**: Flowing river that can carry animals downstream
- **Walls**: Build boundaries to control animal movement
- **Stats Display**: Real-time population and ecosystem statistics

## Installation

1. Install Python 3.7 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## How to Play

### Controls

- **1**: Select Tree tool
- **2**: Select Herbivore tool
- **3**: Select Tree Eater tool
- **4**: Select Carnivore tool
- **5**: Select Decomposer tool
- **6**: Select Wall tool
- **Left Click**: Place selected entity/tool
- **Right Click**: Cancel wall placement

### Gameplay

- Animals will automatically seek food based on their type
- Animals reproduce when well-fed and near a mate
- Animals die when they run out of hunger
- Dead animals become bodies that decomposers can consume
- The river flows and can carry animals downstream
- Use walls to create boundaries and control animal movement

## Ecological Mechanics

- **Food Chain**: Herbivores → Carnivores, Tree Eaters → Carnivores
- **Decomposition**: Dead animals are consumed by decomposers
- **Reproduction**: Animals reproduce when healthy and near mates
- **Natural Selection**: Only well-fed animals survive and reproduce

## GPU Prototype (Experimental)

The repo now ships with a GPU-focused prototype built on Arcade + instanced rendering.  
It is optimized for very large populations (10k+ entities) and can be run alongside the classic Pygame version.

1. Install the additional dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the prototype:
   ```bash
   python main_gpu.py
   ```

The prototype currently demonstrates the new architecture (SoA data, GPU sprite batching, vectorized behaviours).  
Existing mechanics (rivers, walls, UI tools, etc.) are being ported over in stages as the new pipeline stabilizes.

Current GPU features:
- GPU-integrated forest with fruit growth per tree (vectorized on CPU, stepped on GPU)
- Herbivores/tree-eaters/carnivores/decomposers/alpha predators with simplified hunting & scavenging loops
- HUD shows FPS, entity counts, and active simulation backend

### Taichi Simulation Backend

- By default the scheduler auto-detects Taichi; if CUDA/Vulkan is available it will run the simulation step on the GPU, otherwise it falls back to the vectorized NumPy backend.
- You can force a backend when constructing `SimulationScheduler` (`backend="taichi"` or `"numpy"`).
- The in-game HUD shows which backend is active so you can confirm the kernel is executing on the GPU.

