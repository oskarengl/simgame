"""Startup menu with species count sliders."""

from __future__ import annotations

from dataclasses import dataclass

import arcade

from ..config import EntityType, WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass
class SpawnConfig:
    """Configuration for initial entity spawning."""

    trees: int = 80
    herbivores: int = 400
    tree_eaters: int = 5
    carnivores: int = 0
    decomposers: int = 100
    alpha_predators: int = 0


class StartupMenu(arcade.View):
    """Startup menu with sliders for species counts."""

    def __init__(self, on_start: callable) -> None:
        super().__init__()
        self.on_start = on_start
        self.config = SpawnConfig()
        self.sliders: dict[str, dict] = {}
        self._setup_sliders()
        self.dragging: str | None = None

    def _setup_sliders(self) -> None:
        """Initialize slider UI elements."""
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT - 200
        spacing = 60
        slider_width = 300
        slider_height = 20
        label_width = 150

        species_config = [
            ("trees", "Trees", self.config.trees, 0, 500, (0, 150, 0)),
            ("herbivores", "Herbivores", self.config.herbivores, 0, 2000, (120, 220, 120)),
            ("tree_eaters", "Tree Eaters", self.config.tree_eaters, 0, 1000, (255, 165, 0)),
            ("carnivores", "Carnivores", self.config.carnivores, 0, 500, (230, 60, 60)),
            ("decomposers", "Decomposers", self.config.decomposers, 0, 500, (190, 120, 255)),
            ("alpha_predators", "Alpha Predators", self.config.alpha_predators, 0, 200, (140, 30, 30)),
        ]

        for i, (key, label, value, min_val, max_val, color) in enumerate(species_config):
            y = start_y - i * spacing
            self.sliders[key] = {
                "label": label,
                "value": value,
                "min": min_val,
                "max": max_val,
                "x": center_x - slider_width // 2,
                "y": y,
                "width": slider_width,
                "height": slider_height,
                "label_width": label_width,
                "color": color,
            }

    def on_draw(self) -> None:
        self.clear()
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)

        # Title
        arcade.draw_text(
            "Ecological Simulation - Startup",
            WINDOW_WIDTH // 2,
            WINDOW_HEIGHT - 80,
            arcade.color.WHITE,
            32,
            anchor_x="center",
            anchor_y="center",
        )

        # Instructions
        arcade.draw_text(
            "Adjust species counts, then press SPACE or click START to begin",
            WINDOW_WIDTH // 2,
            WINDOW_HEIGHT - 120,
            arcade.color.LIGHT_GRAY,
            16,
            anchor_x="center",
            anchor_y="center",
        )

        # Draw sliders
        for key, slider in self.sliders.items():
            self._draw_slider(slider)

        # Start button
        button_x = WINDOW_WIDTH // 2
        button_y = 100
        button_width = 200
        button_height = 50
        arcade.draw_lbwh_rectangle_filled(
            button_x - button_width // 2,
            button_y - button_height // 2,
            button_width,
            button_height,
            arcade.color.GREEN,
        )
        arcade.draw_lbwh_rectangle_outline(
            button_x - button_width // 2,
            button_y - button_height // 2,
            button_width,
            button_height,
            arcade.color.WHITE,
            2,
        )
        arcade.draw_text(
            "START",
            button_x,
            button_y,
            arcade.color.WHITE,
            24,
            anchor_x="center",
            anchor_y="center",
        )

    def _draw_slider(self, slider: dict) -> None:
        """Draw a single slider."""
        x = slider["x"]
        y = slider["y"]
        width = slider["width"]
        height = slider["height"]
        label_width = slider["label_width"]
        min_val = slider["min"]
        max_val = slider["max"]
        value = slider["value"]
        color = slider["color"]

        # Label
        arcade.draw_text(
            slider["label"],
            x - label_width - 10,
            y,
            arcade.color.WHITE,
            16,
            anchor_y="center",
        )

        # Slider track background
        arcade.draw_lbwh_rectangle_filled(x, y - height // 2, width, height, (60, 60, 60))
        arcade.draw_lbwh_rectangle_outline(x, y - height // 2, width, height, arcade.color.WHITE, 1)

        # Slider fill
        ratio = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.0
        fill_width = width * ratio
        arcade.draw_lbwh_rectangle_filled(x, y - height // 2, fill_width, height, color)

        # Slider handle
        handle_x = x + width * ratio
        handle_size = 12
        arcade.draw_circle_filled(handle_x, y, handle_size, arcade.color.WHITE)
        arcade.draw_circle_outline(handle_x, y, handle_size, arcade.color.BLACK, 2)

        # Value text
        arcade.draw_text(
            str(int(value)),
            x + width + 20,
            y,
            arcade.color.WHITE,
            16,
            anchor_y="center",
        )

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        # Check start button
        button_x = WINDOW_WIDTH // 2
        button_y = 100
        button_width = 200
        button_height = 50
        if (
            button_x - button_width // 2 <= x <= button_x + button_width // 2
            and button_y - button_height // 2 <= y <= button_y + button_height // 2
        ):
            self._start_simulation()
            return

        # Check sliders
        for key, slider in self.sliders.items():
            sx = slider["x"]
            sy = slider["y"]
            swidth = slider["width"]
            sheight = slider["height"]
            handle_size = 12

            if (
                sx - handle_size <= x <= sx + swidth + handle_size
                and sy - handle_size <= y <= sy + handle_size
            ):
                self.dragging = key
                self._update_slider_value(key, x)
                break

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int) -> None:
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.dragging = None

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int) -> None:
        if buttons & arcade.MOUSE_BUTTON_LEFT and self.dragging:
            self._update_slider_value(self.dragging, x)

    def _update_slider_value(self, key: str, mouse_x: float) -> None:
        """Update slider value based on mouse X position."""
        slider = self.sliders[key]
        sx = slider["x"]
        swidth = slider["width"]
        min_val = slider["min"]
        max_val = slider["max"]

        ratio = max(0.0, min(1.0, (mouse_x - sx) / swidth))
        value = min_val + ratio * (max_val - min_val)
        slider["value"] = int(value)
        setattr(self.config, key, int(value))

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.SPACE:
            self._start_simulation()

    def _start_simulation(self) -> None:
        """Start the simulation with current config."""
        self.on_start(self.config)

