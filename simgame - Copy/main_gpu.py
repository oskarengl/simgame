from __future__ import annotations

import sys

# Check Python version compatibility
if sys.version_info >= (3, 14):
    print("=" * 70)
    print("ERROR: Python 3.14+ is not yet supported by arcade/taichi")
    print("=" * 70)
    print("\nPlease install Python 3.11 or 3.12:")
    print("  1. Download from: https://www.python.org/downloads/")
    print("  2. During installation, check 'Add Python to PATH'")
    print("  3. Create a virtual environment:")
    print("     py -3.11 -m venv .venv")
    print("     .venv\\Scripts\\activate")
    print("     pip install -r requirements.txt")
    print("  4. Then run: python main_gpu.py")
    print("\nAlternatively, use the legacy Pygame version:")
    print("  python main.py")
    print("=" * 70)
    sys.exit(1)

try:
    import arcade
except ImportError as e:
    print("=" * 70)
    print("ERROR: Could not import 'arcade'")
    print("=" * 70)
    print(f"\nDetails: {e}")
    print("\nPlease install dependencies:")
    print("  pip install -r requirements.txt")
    print("\nIf you're using Python 3.14+, you need Python 3.11 or 3.12")
    print("See instructions above.")
    print("=" * 70)
    sys.exit(1)

from simgame import EntityType, SimulationState, WINDOW_HEIGHT, WINDOW_WIDTH
from simgame.rendering import SimulationWindow
from simgame.simulation import SimulationScheduler
from simgame.ui import StartupMenu
from simgame.world import create_river


def bootstrap_initial_state(state: SimulationState, config) -> None:
    """Spawn entities based on configuration."""
    state.spawn_trees(config.trees, fruit_capacity=6)
    state.spawn_random(
        config.herbivores,
        EntityType.HERBIVORE,
        speed=65.0,
        size=10.0,
        max_jitter=0.15,
    )
    state.spawn_random(
        config.tree_eaters,
        EntityType.TREE_EATER,
        speed=60.0,
        size=12.0,
        max_jitter=0.2,
    )
    state.spawn_random(
        config.carnivores,
        EntityType.CARNIVORE,
        speed=90.0,
        size=12.0,
        max_jitter=0.25,
    )
    state.spawn_random(
        config.decomposers,
        EntityType.DECOMPOSER,
        speed=55.0,
        size=9.0,
        max_jitter=0.3,
    )
    state.spawn_random(
        config.alpha_predators,
        EntityType.ALPHA_PREDATOR,
        speed=110.0,
        size=14.0,
        max_jitter=0.15,
    )


def start_simulation(config) -> None:
    """Start the simulation with the given configuration."""
    state = SimulationState()
    bootstrap_initial_state(state, config)
    scheduler = SimulationScheduler(state, backend="auto")
    river_segments = create_river(WINDOW_WIDTH, WINDOW_HEIGHT)
    scheduler.set_river(river_segments)
    sim_view = SimulationWindow(state, scheduler, river_segments)
    # Switch to simulation view
    window = arcade.get_window()
    if window:
        window.show_view(sim_view)


def main() -> None:
    window = arcade.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "Ecological Simulation (GPU)")
    menu = StartupMenu(start_simulation)
    window.show_view(menu)
    arcade.run()


if __name__ == "__main__":
    main()


