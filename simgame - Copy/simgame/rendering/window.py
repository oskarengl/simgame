from __future__ import annotations

import math
import time
from dataclasses import dataclass

import arcade
import numpy as np

from ..config import EntityType, TARGET_FPS, WINDOW_HEIGHT, WINDOW_WIDTH
from ..world import RiverSegment
from ..simulation import SimulationScheduler
from ..state import SimulationState


INSTANCE_DTYPE = np.dtype(
    [
        ("in_pos", "f4", 2),
        ("in_size", "f4"),
        ("in_color", "f4", 4),
        ("in_kind", "i4"),
        ("in_extra", "f4", 2),
    ]
)

KIND_TREE = 0
KIND_CREATURE = 1


@dataclass
class Camera2D:
    world_width: float
    world_height: float
    window_width: float
    window_height: float
    center: np.ndarray | None = None
    zoom: float = 1.0
    min_zoom: float = 0.25
    max_zoom: float = 5.0

    def __post_init__(self) -> None:
        if self.center is None:
            self.center = np.array(
                [self.world_width / 2, self.world_height / 2], dtype=np.float32
            )

    def reset(self) -> None:
        self.center[:] = (self.world_width / 2, self.world_height / 2)
        self.zoom = 1.0

    def pan(self, dx: float, dy: float) -> None:
        self.center[0] = np.clip(self.center[0] - dx, 0.0, self.world_width)
        self.center[1] = np.clip(self.center[1] + dy, 0.0, self.world_height)

    def adjust_zoom(self, steps: float) -> None:
        if steps == 0:
            return
        factor = math.pow(1.15, steps)
        self.zoom = float(np.clip(self.zoom * factor, self.min_zoom, self.max_zoom))

    def set_window(self, width: float, height: float) -> None:
        self.window_width = width
        self.window_height = height

    def matrix(self) -> np.ndarray:
        view_width = self.window_width / self.zoom
        view_height = self.window_height / self.zoom
        left = self.center[0] - view_width / 2
        right = self.center[0] + view_width / 2
        bottom = self.center[1] - view_height / 2
        top = self.center[1] + view_height / 2

        scale_x = 2.0 / (right - left)
        scale_y = 2.0 / (top - bottom)
        tx = -(right + left) / (right - left)
        ty = -(top + bottom) / (top - bottom)

        return np.array(
            [
                [scale_x, 0.0, 0.0, tx],
                [0.0, scale_y, 0.0, ty],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        view_width = self.window_width / self.zoom
        view_height = self.window_height / self.zoom
        left = self.center[0] - view_width / 2
        bottom = self.center[1] - view_height / 2
        wx = left + (sx / self.window_width) * view_width
        wy = bottom + (sy / self.window_height) * view_height
        return (float(wx), float(wy))


class QuadRenderer:
    """Instanced quad renderer with simple procedural shading."""

    def __init__(self, window: arcade.Window, capacity: int) -> None:
        self.window = window
        self.ctx = window.ctx
        if hasattr(self.ctx, "BLEND"):
            self.ctx.enable(self.ctx.BLEND)

        quad = np.array(
            [
                (-0.5, -0.5),
                (0.5, -0.5),
                (0.5, 0.5),
                (-0.5, -0.5),
                (0.5, 0.5),
                (-0.5, 0.5),
            ],
            dtype="f4",
        )
        self._quad_buffer = self.ctx.buffer(data=quad.tobytes())
        buffer_bytes = INSTANCE_DTYPE.itemsize * capacity
        self._tree_buffer = self.ctx.buffer(reserve=buffer_bytes)
        self._creature_buffer = self.ctx.buffer(reserve=buffer_bytes)
        self._tree_cpu = np.zeros(capacity, dtype=INSTANCE_DTYPE)
        self._creature_cpu = np.zeros(capacity, dtype=INSTANCE_DTYPE)
        self._tree_count = 0
        self._creature_count = 0

        instance_format = "2f 1f 4f 1i 2f"
        quad_desc = arcade.gl.BufferDescription(self._quad_buffer, "2f", ["in_vert"])
        tree_desc = arcade.gl.BufferDescription(
            self._tree_buffer,
            instance_format,
            ["in_pos", "in_size", "in_color", "in_kind", "in_extra"],
            instanced=True,
        )
        herb_desc = arcade.gl.BufferDescription(
            self._creature_buffer,
            instance_format,
            ["in_pos", "in_size", "in_color", "in_kind", "in_extra"],
            instanced=True,
        )

        self._program = self.ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_vert;
                in vec2 in_pos;
                in float in_size;
                in vec4 in_color;
                in int in_kind;
                in vec2 in_extra;
                out vec2 v_local;
                out vec4 v_color;
                flat out int v_kind;
                out vec2 v_extra;
                uniform mat4 u_view_proj;
                void main() {
                    vec2 world = in_pos + in_vert * in_size;
                    gl_Position = u_view_proj * vec4(world, 0.0, 1.0);
                    v_local = in_vert * 2.0;
                    v_color = in_color;
                    v_kind = in_kind;
                    v_extra = in_extra;
                }
            """,
            fragment_shader="""
                #version 330
                in vec2 v_local;
                in vec4 v_color;
                flat in int v_kind;
                in vec2 v_extra;
                out vec4 fragColor;

                vec3 render_tree(vec2 uv, float fruit_ratio) {
                    vec3 canopy = mix(vec3(0.08, 0.4, 0.15),
                                      vec3(0.45, 0.85, 0.22),
                                      clamp(fruit_ratio, 0.0, 1.0));
                    vec3 trunk = vec3(0.35, 0.23, 0.13);
                    if (abs(uv.x) < 0.22 && uv.y < -0.9) {
                        return trunk;
                    }
                    if (abs(uv.x) < 0.3 && uv.y < -0.55) {
                        return mix(trunk, canopy, 0.2);
                    }
                    float dist = length(uv);
                    if (dist <= 1.0) {
                        float shade = 0.4 + 0.6 * (1.0 - dist);
                        return canopy * shade;
                    }
                    discard;
                }

                vec3 render_herbivore(vec2 uv, vec4 base_color, float energy_ratio) {
                    float body = length(uv);
                    if (body > 1.0) {
                        discard;
                    }
                    vec3 color = base_color.rgb * mix(0.6, 1.1, clamp(energy_ratio, 0.0, 1.0));
                    // Simple eyes: just two black dots
                    vec2 left_eye = uv - vec2(-0.3, 0.15);
                    vec2 right_eye = uv - vec2(0.3, 0.15);
                    float left_dist = length(left_eye);
                    float right_dist = length(right_eye);
                    if (left_dist < 0.1 || right_dist < 0.1) {
                        return vec3(0.0, 0.0, 0.0); // Black dots
                    }
                    return color;
                }

                vec3 render_tree_with_fruit(vec2 uv, float ratio, float fruit_count) {
                    vec3 base = render_tree(uv, ratio);
                    int fruit_int = clamp(int(fruit_count + 0.5), 0, 8);
                    if (fruit_int == 0) {
                        return base;
                    }
                    for (int i = 0; i < 8; ++i) {
                        if (i >= fruit_int) break;
                        float angle = 6.2831853 * (float(i) / float(max(fruit_int, 1)));
                        vec2 center = vec2(cos(angle), sin(angle));
                        center *= 0.65;
                        center.y += 0.25;
                        float d = length(uv - center);
                        if (d < 0.18) {
                            vec3 fruit_color = mix(vec3(0.98, 0.76, 0.2), vec3(1.0, 0.5, 0.05), ratio);
                            if (d < 0.08) {
                                fruit_color = vec3(1.0, 0.9, 0.4);
                            }
                            return fruit_color;
                        }
                    }
                    return base;
                }

                void main() {
                    if (v_kind == 0) {
                        vec3 color = render_tree_with_fruit(v_local, v_extra.x, v_extra.y);
                        fragColor = vec4(color, 1.0);
                    } else {
                        vec3 color = render_herbivore(v_local, v_color, v_extra.x);
                        fragColor = vec4(color, 1.0);
                    }
                }
            """,
        )

        self._tree_geometry = self.ctx.geometry(
            [quad_desc, tree_desc], mode=self.ctx.TRIANGLES
        )
        self._herb_geometry = self.ctx.geometry(
            [quad_desc, herb_desc], mode=self.ctx.TRIANGLES
        )

    def upload(self, state: SimulationState) -> None:
        count = state.count
        if count == 0:
            self._tree_count = 0
            self._herb_count = 0
            return

        idx = slice(0, count)
        alive = state.alive_mask[idx]
        if not np.any(alive):
            self._tree_count = 0
            self._herb_count = 0
            return

        types = state.entity_type[idx]
        positions = state.positions[idx]

        tree_mask = alive & (types == int(EntityType.TREE))
        creature_mask = alive & (types != int(EntityType.TREE))

        self._tree_count = int(np.count_nonzero(tree_mask))
        if self._tree_count:
            view = self._tree_cpu[: self._tree_count]
            view["in_pos"] = positions[tree_mask]
            sizes = np.maximum(16.0, state.size[idx][tree_mask] * 1.8)
            view["in_size"] = sizes.astype(np.float32)
            fruit = state.tree_fruit[idx][tree_mask]
            capacity = np.maximum(1.0, state.tree_fruit_capacity[idx][tree_mask])
            ratio = np.clip(fruit / capacity, 0.0, 1.0).astype(np.float32)
            colors = np.tile(np.array([[0.1, 0.55, 0.2, 1.0]], dtype=np.float32), (self._tree_count, 1))
            colors[:, :3] *= (0.75 + 0.35 * ratio[:, None])
            view["in_color"] = colors
            view["in_kind"] = KIND_TREE
            tree_fruits = np.clip(fruit, 0.0, 8.0).astype(np.float32)
            view_extra = view["in_extra"]
            view_extra[:, 0] = ratio
            view_extra[:, 1] = tree_fruits
            self._tree_buffer.write(view.tobytes())

        self._creature_count = int(np.count_nonzero(creature_mask))
        if self._creature_count:
            view = self._creature_cpu[: self._creature_count]
            view["in_pos"] = positions[creature_mask]
            base_sizes = np.full(self._creature_count, 18.0, dtype=np.float32)
            creature_types = types[creature_mask]
            for etype, scale in [
                (EntityType.TREE_EATER, 20.0),
                (EntityType.CARNIVORE, 20.0),
                (EntityType.DECOMPOSER, 16.0),
                (EntityType.ALPHA_PREDATOR, 22.0),
            ]:
                mask = creature_types == int(etype)
                if np.any(mask):
                    base_sizes[mask] = scale
            view["in_size"] = base_sizes

            colors = np.tile(
                np.array([[0.2, 0.8, 0.2, 1.0]], dtype=np.float32),
                (self._creature_count, 1),
            )
            color_map = {
                EntityType.HERBIVORE: (0.2, 0.8, 0.2, 1.0),
                EntityType.TREE_EATER: (1.0, 0.63, 0.1, 1.0),
                EntityType.CARNIVORE: (0.9, 0.25, 0.25, 1.0),
                EntityType.DECOMPOSER: (0.6, 0.25, 0.9, 1.0),
                EntityType.ALPHA_PREDATOR: (0.55, 0.1, 0.1, 1.0),
            }
            for etype, color in color_map.items():
                mask = creature_types == int(etype)
                if np.any(mask):
                    colors[mask] = color
            view["in_color"] = colors
            view["in_kind"] = KIND_CREATURE
            energy = np.clip(state.energy[idx][creature_mask], 0.0, 1.5).astype(
                np.float32
            )
            extras = view["in_extra"]
            extras[:, 0] = energy
            extras[:, 1] = creature_types.astype(np.float32)
            self._creature_buffer.write(view.tobytes())

    def draw(self, camera_matrix: np.ndarray) -> None:
        self._program["u_view_proj"] = (
            camera_matrix.astype("f4").T.flatten().tolist()
        )
        if self._tree_count:
            self._tree_geometry.render(self._program, instances=self._tree_count)
        if self._creature_count:
            self._herb_geometry.render(self._program, instances=self._creature_count)


class SimulationWindow(arcade.View):
    """Arcade view that wires the simulation schedule to the GPU renderer."""

    def __init__(
        self,
        state: SimulationState,
        scheduler: SimulationScheduler,
        river_segments: list[RiverSegment],
    ) -> None:
        super().__init__()
        self.state = state
        self.scheduler = scheduler
        self.backend = scheduler.backend
        self.river_segments = river_segments
        self.camera = Camera2D(
            world_width=WINDOW_WIDTH,
            world_height=WINDOW_HEIGHT,
            window_width=float(WINDOW_WIDTH),
            window_height=float(WINDOW_HEIGHT),
        )
        self.renderer: QuadRenderer | None = None
        self._time_accum = 0.0
        self._fps_count = 0
        self._display_fps = 0.0
        self._fps_start_time = time.perf_counter()
        self.tools = [
            ("Pointer", "pointer", None),
            ("Tree", "tree", EntityType.TREE),
            ("Herbivore", "herbivore", EntityType.HERBIVORE),
            ("Tree Eater", "tree_eater", EntityType.TREE_EATER),
            ("Carnivore", "carnivore", EntityType.CARNIVORE),
            ("Decomposer", "decomposer", EntityType.DECOMPOSER),
            ("Alpha", "alpha", EntityType.ALPHA_PREDATOR),
        ]
        self.selected_tool = "pointer"
        self.selected_entity: int | None = None
        self.population_history: list[dict[EntityType, int]] = []
        self.population_interval = 0.5
        self._pop_accum = 0.0
        self.speed_options = [1, 2, 4, 8]
        self.speed_index = 0

    def on_show_view(self) -> None:
        """Called when view is shown."""
        arcade.set_background_color(arcade.color.DARK_BLUE_GRAY)
        if self.renderer is None:
            self.renderer = QuadRenderer(self.window, self.state.capacity)
        self.camera.set_window(float(self.window.width), float(self.window.height))

    def on_draw(self) -> None:
        self.clear()
        if self.renderer is None:
            return
        self._draw_river()
        self.renderer.upload(self.state)
        self.renderer.draw(self.camera.matrix())
        self._draw_hud()

    def on_update(self, delta_time: float) -> None:
        steps = self.speed_options[self.speed_index]
        step_dt = delta_time / steps
        for _ in range(steps):
            self.scheduler.update(step_dt)
            self._pop_accum += step_dt
            if self._pop_accum >= self.population_interval:
                self._record_population_sample()
                self._pop_accum = 0.0
        self._time_accum += delta_time
        current_time = time.perf_counter()
        self._fps_count += 1
        
        # Calculate FPS using wall-clock time for accuracy
        elapsed = current_time - self._fps_start_time
        if elapsed >= 0.5 and self._fps_count > 0:
            self._display_fps = self._fps_count / elapsed
            self._fps_start_time = current_time
            self._fps_count = 0

    def _draw_hud(self) -> None:
        fps = self._display_fps
        alive = self.state.alive_count
        counts = {}
        if self.state.count:
            types = self.state.entity_type[: self.state.count]
            alive_mask = self.state.alive_mask[: self.state.count]
            for etype in [
                EntityType.TREE,
                EntityType.HERBIVORE,
                EntityType.TREE_EATER,
                EntityType.CARNIVORE,
                EntityType.DECOMPOSER,
                EntityType.ALPHA_PREDATOR,
            ]:
                counts[etype] = int(
                    np.count_nonzero(alive_mask & (types == int(etype)))
                )
        tree_count = counts.get(EntityType.TREE, 0)
        hud_lines = [
            f"Entities: {alive:,}",
            f"Trees: {tree_count:,}  Herb: {counts.get(EntityType.HERBIVORE,0):,}  "
            f"T-Eaters: {counts.get(EntityType.TREE_EATER,0):,}",
            f"Carn: {counts.get(EntityType.CARNIVORE,0):,}  "
            f"Dec: {counts.get(EntityType.DECOMPOSER,0):,}  "
            f"Alpha: {counts.get(EntityType.ALPHA_PREDATOR,0):,}",
            f"FPS: {fps:.1f}  Speed: {self.speed_options[self.speed_index]}x  Tool: {self.selected_tool.title()}",
            f"Sim Backend: {self.backend.upper()} ({'GPU' if self.backend == 'taichi' else 'CPU'})",
            "Scroll = Zoom, Right/Middle Drag = Pan, R = Reset, 1-7 = Tools",
        ]
        arcade.draw_text(
            "\n".join(hud_lines),
            10,
            self.window.height - 80,
            arcade.color.WHITE,
            14,
        )
        self._draw_population_graph()
        self._draw_inspector()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & (arcade.MOUSE_BUTTON_RIGHT | arcade.MOUSE_BUTTON_MIDDLE):
            self.camera.pan(dx / self.camera.zoom, dy / self.camera.zoom)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera.adjust_zoom(scroll_y * 0.5)

    def on_resize(self, width: int, height: int):
        self.camera.set_window(width, height)

    def on_resize(self, width: int, height: int):
        self.camera.set_window(width, height)

    def on_key_press(self, symbol: int, modifiers: int):
        if symbol == arcade.key.R:
            self.camera.reset()
        elif symbol in (arcade.key.EQUAL, arcade.key.PLUS):
            self.speed_index = min(self.speed_index + 1, len(self.speed_options) - 1)
        elif symbol == arcade.key.MINUS:
            self.speed_index = max(self.speed_index - 1, 0)
        elif arcade.key.KEY_1 <= symbol <= arcade.key.KEY_7:
            tool_idx = symbol - arcade.key.KEY_1
            if tool_idx < len(self.tools):
                self.selected_tool = self.tools[tool_idx][1]

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        wx, wy = self.camera.screen_to_world(x, y)
        if self.selected_tool == "pointer":
            self.selected_entity = self._pick_entity(wx, wy)
        else:
            self._spawn_tool_entity(wx, wy)

    def _draw_river(self) -> None:
        if not self.river_segments:
            return
        for segment in self.river_segments:
            arcade.draw_line(
                segment.x1,
                segment.y1,
                segment.x2,
                segment.y2,
                arcade.color.DODGER_BLUE,
                int(segment.width),
            )

    def _record_population_sample(self) -> None:
        idx = slice(0, self.state.count)
        alive = self.state.alive_mask[idx]
        if not np.any(alive):
            return
        sample: dict[EntityType, int] = {}
        for etype in [
            EntityType.TREE,
            EntityType.HERBIVORE,
            EntityType.TREE_EATER,
            EntityType.CARNIVORE,
            EntityType.DECOMPOSER,
            EntityType.ALPHA_PREDATOR,
        ]:
            sample[etype] = int(
                np.count_nonzero(alive & (self.state.entity_type[idx] == int(etype)))
            )
        self.population_history.append(sample)
        if len(self.population_history) > 240:
            self.population_history.pop(0)

    def _draw_population_graph(self) -> None:
        if len(self.population_history) < 2:
            return
        # PERFORMANCE: Throttle graph drawing - only update every 5 frames
        if not hasattr(self, '_graph_frame_counter'):
            self._graph_frame_counter = 0
        self._graph_frame_counter += 1
        if self._graph_frame_counter < 5:
            return
        self._graph_frame_counter = 0
        
        width = 260
        height = 90
        x0 = 10
        y0 = 100
        arcade.draw_lbwh_rectangle_filled(
            x0,
            y0,
            width,
            height,
            (20, 24, 33),
        )
        arcade.draw_lbwh_rectangle_outline(
            x0,
            y0,
            width,
            height,
            arcade.color.GRAY,
            1,
        )
        history = self.population_history
        max_pop = max(
            (sum(sample.values()) for sample in history if sample), default=1
        )
        max_pop = max(max_pop, 1)
        colors = {
            EntityType.HERBIVORE: (120, 220, 120),
            EntityType.TREE_EATER: (255, 165, 0),
            EntityType.CARNIVORE: (230, 60, 60),
            EntityType.DECOMPOSER: (190, 120, 255),
            EntityType.ALPHA_PREDATOR: (140, 30, 30),
        }
        # Draw stacked area chart (bottom to top)
        order = [
            EntityType.HERBIVORE,
            EntityType.TREE_EATER,
            EntityType.CARNIVORE,
            EntityType.DECOMPOSER,
            EntityType.ALPHA_PREDATOR,
        ]
        # Build cumulative values for stacking
        cumulative = np.zeros(len(history), dtype=np.float32)
        for etype in order:
            color = colors[etype]
            top_points = []
            bottom_points = []
            for i, sample in enumerate(history):
                value = sample.get(etype, 0)
                px = x0 + (i / max(1, len(history) - 1)) * width
                bottom_y = y0 + (cumulative[i] / max_pop) * height
                top_y = y0 + ((cumulative[i] + value) / max_pop) * height
                top_points.append((px, top_y))
                bottom_points.append((px, bottom_y))
                cumulative[i] += value
            # Draw filled polygon (area chart)
            if len(top_points) >= 2:
                # Build polygon: start at first bottom point, go along top, then back along bottom
                polygon_points = top_points + list(reversed(bottom_points))
                arcade.draw_polygon_filled(polygon_points, color)
                # Draw top outline
                arcade.draw_line_strip(top_points, tuple(min(255, c + 40) for c in color), 1)

    def _pick_entity(self, wx: float, wy: float) -> int | None:
        idx = slice(0, self.state.count)
        alive = self.state.alive_mask[idx]
        if not np.any(alive):
            return None
        positions = self.state.positions[idx]
        diff = positions - np.array([wx, wy], dtype=np.float32)
        dist_sq = np.sum(diff * diff, axis=1)
        candidate = int(np.argmin(dist_sq))
        if alive[candidate] and dist_sq[candidate] < 400.0:
            return candidate
        return None

    def _spawn_tool_entity(self, wx: float, wy: float) -> None:
        bounds = (wx, wx, wy, wy)
        tool = self.selected_tool
        if tool == "tree":
            self.state.spawn_trees(1, position_bounds=bounds)
        elif tool == "herbivore":
            self.state.spawn_random(
                1,
                EntityType.HERBIVORE,
                position_bounds=bounds,
                speed=65.0,
                size=10.0,
                max_jitter=0.2,
            )
        elif tool == "tree_eater":
            self.state.spawn_random(
                1,
                EntityType.TREE_EATER,
                position_bounds=bounds,
                speed=55.0,
                size=12.0,
                max_jitter=0.2,
            )
        elif tool == "carnivore":
            self.state.spawn_random(
                1,
                EntityType.CARNIVORE,
                position_bounds=bounds,
                speed=90.0,
                size=12.0,
                max_jitter=0.2,
            )
        elif tool == "decomposer":
            self.state.spawn_random(
                1,
                EntityType.DECOMPOSER,
                position_bounds=bounds,
                speed=55.0,
                size=9.0,
                max_jitter=0.3,
            )
        elif tool == "alpha":
            self.state.spawn_random(
                1,
                EntityType.ALPHA_PREDATOR,
                position_bounds=bounds,
                speed=110.0,
                size=14.0,
                max_jitter=0.15,
            )

    def _draw_inspector(self) -> None:
        if self.selected_entity is None:
            return
        idx = self.selected_entity
        if idx >= self.state.count or not self.state.alive_mask[idx]:
            self.selected_entity = None
            return
        
        entity_type = EntityType(self.state.entity_type[idx])
        energy = float(self.state.energy[idx])
        pos_x = float(self.state.positions[idx][0])
        pos_y = float(self.state.positions[idx][1])
        size = float(self.state.size[idx])
        
        # Panel dimensions
        panel_width = 250
        panel_height = 200
        left = self.window.width - panel_width - 20
        bottom = self.window.height - panel_height - 20
        
        # Background
        arcade.draw_lbwh_rectangle_filled(
            left,
            bottom,
            panel_width,
            panel_height,
            (30, 35, 45),
        )
        arcade.draw_lbwh_rectangle_outline(
            left,
            bottom,
            panel_width,
            panel_height,
            arcade.color.WHITE,
            2,
        )
        
        # Type name
        type_map = {
            EntityType.TREE: "Tree",
            EntityType.HERBIVORE: "Herbivore",
            EntityType.TREE_EATER: "Tree Eater",
            EntityType.CARNIVORE: "Carnivore",
            EntityType.DECOMPOSER: "Decomposer",
            EntityType.ALPHA_PREDATOR: "Alpha Predator",
        }
        type_name = type_map.get(entity_type, "Unknown")
        type_colors = {
            EntityType.TREE: arcade.color.GREEN,
            EntityType.HERBIVORE: (120, 220, 120),
            EntityType.TREE_EATER: (255, 165, 0),
            EntityType.CARNIVORE: (230, 60, 60),
            EntityType.DECOMPOSER: (190, 120, 255),
            EntityType.ALPHA_PREDATOR: (140, 30, 30),
        }
        type_color = type_colors.get(entity_type, arcade.color.WHITE)
        
        y_offset = bottom + panel_height - 25
        arcade.draw_text(
            type_name,
            left + 15,
            y_offset,
            type_color,
            18,
            bold=True,
        )
        y_offset -= 30
        
        # Health/Energy bar
        bar_width = panel_width - 30
        bar_height = 16
        bar_x = left + 15
        bar_y = y_offset
        
        # Background
        arcade.draw_lbwh_rectangle_filled(
            bar_x,
            bar_y,
            bar_width,
            bar_height,
            (60, 60, 60),
        )
        
        # Health fill (green to red gradient)
        health_ratio = max(0.0, min(1.0, energy))
        fill_width = bar_width * health_ratio
        health_color = (
            int(255 * (1 - health_ratio)),
            int(255 * health_ratio),
            0,
        )
        arcade.draw_lbwh_rectangle_filled(
            bar_x,
            bar_y,
            fill_width,
            bar_height,
            health_color,
        )
        
        # Border
        arcade.draw_lbwh_rectangle_outline(
            bar_x,
            bar_y,
            bar_width,
            bar_height,
            arcade.color.WHITE,
            1,
        )
        
        # Health text
        health_text = f"{int(health_ratio * 100)}%"
        arcade.draw_text(
            health_text,
            bar_x + bar_width + 5,
            bar_y - 2,
            arcade.color.WHITE,
            12,
        )
        y_offset -= 30
        
        # Energy value
        arcade.draw_text(
            f"Energy: {energy:.2f}",
            left + 15,
            y_offset,
            arcade.color.WHITE,
            14,
        )
        y_offset -= 25
        
        # Type-specific info
        if entity_type == EntityType.TREE:
            fruit_count = int(self.state.tree_fruit[idx])
            fruit_capacity = int(self.state.tree_fruit_capacity[idx])
            arcade.draw_text(
                f"Fruit: {fruit_count}/{fruit_capacity}",
                left + 15,
                y_offset,
                (255, 165, 0),
                14,
            )
            y_offset -= 25
        
        # Position and size
        arcade.draw_text(
            f"Position: ({pos_x:.1f}, {pos_y:.1f})",
            left + 15,
            y_offset,
            arcade.color.LIGHT_GRAY,
            12,
        )
        y_offset -= 20
        arcade.draw_text(
            f"Size: {size:.1f}",
            left + 15,
            y_offset,
            arcade.color.LIGHT_GRAY,
            12,
        )
        
        # Status indicator (based on energy)
        y_offset -= 25
        if energy < 0.3:
            status_text = "HUNGRY"
            status_color = arcade.color.RED
        elif energy < 0.7:
            status_text = "NEUTRAL"
            status_color = arcade.color.YELLOW
        else:
            status_text = "HEALTHY"
            status_color = arcade.color.GREEN
        
        arcade.draw_text(
            status_text,
            left + 15,
            y_offset,
            status_color,
            14,
            bold=True,
        )
