import math
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector3
from dotenv import load_dotenv


class GameState(Enum):
    AIMING = auto()
    CHARGING = auto()
    IN_FLIGHT = auto()
    RESOLVE = auto()


@dataclass
class Arrow:
    position: Vector3
    velocity: Vector3
    origin: Vector3
    flight_time: float = 0.0


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise RuntimeError(f"Missing required .env key: {key}")
    return value


def _parse_float(key: str) -> float:
    return float(_require_env(key))


def _parse_int(key: str) -> int:
    return int(_require_env(key))


def _parse_color(value: str) -> Tuple[int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Color must have 3 components, got '{value}'")
    return tuple(parts)  # type: ignore[return-value]


def _parse_color_list(value: str) -> List[Tuple[int, int, int]]:
    entries = [entry.strip() for entry in value.split(";") if entry.strip()]
    return [_parse_color(entry) for entry in entries]


@dataclass
class GameConfig:
    screen_width: int
    screen_height: int
    fps: int
    fov_deg: float
    camera_z: float
    near_plane: float
    far_plane: float
    gravity: float
    max_arrow_speed: float
    max_draw_seconds: float
    power_exponent: float
    aim_yaw_speed_deg_s: float
    aim_yaw_min_deg: float
    aim_yaw_max_deg: float
    aim_pitch_speed_deg_s: float
    aim_pitch_min_deg: float
    aim_pitch_max_deg: float
    aim_initial_yaw_deg: float
    aim_initial_pitch_deg: float
    target_outer_radius: float
    target_ring_count: int
    target_center_x: float
    target_center_z: float
    difficulty: str
    distance_map: Dict[str, float]
    bg_color: Tuple[int, int, int]
    target_colors: List[Tuple[int, int, int]]
    arrow_color: Tuple[int, int, int]
    ui_color: Tuple[int, int, int]

    @classmethod
    def load(cls) -> "GameConfig":
        load_dotenv()
        difficulty = _require_env("DIFFICULTY").strip().upper()
        distance_map = {
            "EASY": float(_require_env("DIST_EASY_M")),
            "MEDIUM": float(_require_env("DIST_MEDIUM_M")),
            "HARD": float(_require_env("DIST_HARD_M")),
        }
        if difficulty not in distance_map:
            raise RuntimeError(f"Unsupported difficulty '{difficulty}'")
        return cls(
            screen_width=_parse_int("SCREEN_WIDTH"),
            screen_height=_parse_int("SCREEN_HEIGHT"),
            fps=_parse_int("FPS"),
            fov_deg=_parse_float("FOV_DEG"),
            camera_z=_parse_float("CAMERA_Z"),
            near_plane=_parse_float("NEAR_PLANE_M"),
            far_plane=_parse_float("FAR_PLANE_M"),
            gravity=_parse_float("GRAVITY"),
            max_arrow_speed=_parse_float("MAX_ARROW_SPEED"),
            max_draw_seconds=_parse_float("MAX_DRAW_SECONDS"),
            power_exponent=_parse_float("POWER_EXPONENT"),
            aim_yaw_speed_deg_s=_parse_float("AIM_YAW_SPEED_DEG_S"),
            aim_yaw_min_deg=_parse_float("AIM_YAW_MIN_DEG"),
            aim_yaw_max_deg=_parse_float("AIM_YAW_MAX_DEG"),
            aim_pitch_speed_deg_s=_parse_float("AIM_PITCH_SPEED_DEG_S"),
            aim_pitch_min_deg=_parse_float("AIM_PITCH_MIN_DEG"),
            aim_pitch_max_deg=_parse_float("AIM_PITCH_MAX_DEG"),
            aim_initial_yaw_deg=_parse_float("AIM_INITIAL_YAW_DEG"),
            aim_initial_pitch_deg=_parse_float("AIM_INITIAL_PITCH_DEG"),
            target_outer_radius=_parse_float("TARGET_OUTER_RADIUS_M"),
            target_ring_count=_parse_int("TARGET_RING_COUNT"),
            target_center_x=_parse_float("TARGET_CENTER_X"),
            target_center_z=_parse_float("TARGET_CENTER_Z"),
            difficulty=difficulty,
            distance_map=distance_map,
            bg_color=_parse_color(_require_env("BG_COLOR")),
            target_colors=_parse_color_list(_require_env("TARGET_COLORS")),
            arrow_color=_parse_color(_require_env("ARROW_COLOR")),
            ui_color=_parse_color(_require_env("UI_COLOR")),
        )

    def target_distance(self) -> float:
        return self.distance_map[self.difficulty]


class BowGame:
    def __init__(self, config: GameConfig) -> None:
        pygame.init()
        pygame.font.init()
        self.config = config
        self.screen = pygame.display.set_mode(
            (config.screen_width, config.screen_height)
        )
        pygame.display.set_caption("Semi-3D Bow & Arrow")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.small_font = pygame.font.SysFont("consolas", 16)

        self.cx = config.screen_width * 0.5
        self.cy = config.screen_height * 0.5
        fov_rad = math.radians(config.fov_deg)
        self.focal_length = 0.5 * config.screen_width / math.tan(fov_rad / 2.0)

        self.state = GameState.AIMING
        self.yaw_deg = config.aim_initial_yaw_deg
        self.pitch_deg = config.aim_initial_pitch_deg
        self._clamp_angles()
        self.draw_time = 0.0
        self.arrow: Optional[Arrow] = None
        self.last_message = "Ready"
        self.resolve_timer = 0.0
        self.running = True

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.config.fps) / 1000.0
            self._handle_events()
            self._update(dt)
            self._render()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self._start_charging()
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                self._release_shot()

    def _start_charging(self) -> None:
        if self.state in (GameState.AIMING, GameState.CHARGING) and not self.arrow:
            self.state = GameState.CHARGING
            self.draw_time = 0.0

    def _release_shot(self) -> None:
        if self.state != GameState.CHARGING:
            return
        power_ratio = min(self.draw_time / self.config.max_draw_seconds, 1.0)
        if power_ratio <= 0.0:
            self.state = GameState.AIMING
            return

        shaped_power = power_ratio ** self.config.power_exponent
        launch_speed = self.config.max_arrow_speed * shaped_power
        yaw_rad = math.radians(self.yaw_deg)
        pitch_rad = math.radians(self.pitch_deg)
        cos_pitch = math.cos(pitch_rad)
        v_x = launch_speed * math.sin(yaw_rad) * cos_pitch
        v_y = launch_speed * math.cos(yaw_rad) * cos_pitch
        v_z = launch_speed * math.sin(pitch_rad)

        if v_y <= 0.0:
            self.state = GameState.AIMING
            self.last_message = "Cannot shoot backward"
            return

        start_y = max(self.config.near_plane, 1e-4)
        start_pos = Vector3(0.0, start_y, self.config.camera_z)
        self.arrow = Arrow(
            position=start_pos.copy(),
            velocity=Vector3(v_x, v_y, v_z),
            origin=start_pos.copy(),
        )
        self.state = GameState.IN_FLIGHT
        self.last_message = "Arrow in flight"

    def _update(self, dt: float) -> None:
        if self.state in (GameState.AIMING, GameState.CHARGING):
            self._update_aim(dt)

        if self.state == GameState.CHARGING:
            self.draw_time = min(self.draw_time + dt, self.config.max_draw_seconds)

        if self.state == GameState.IN_FLIGHT and self.arrow:
            self._update_arrow(dt)

        if self.state == GameState.RESOLVE:
            self.resolve_timer -= dt
            if self.resolve_timer <= 0.0:
                self.state = GameState.AIMING

    def _update_aim(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            self.yaw_deg -= self.config.aim_yaw_speed_deg_s * dt
        if keys[pygame.K_d]:
            self.yaw_deg += self.config.aim_yaw_speed_deg_s * dt
        if keys[pygame.K_w]:
            self.pitch_deg += self.config.aim_pitch_speed_deg_s * dt
        if keys[pygame.K_s]:
            self.pitch_deg -= self.config.aim_pitch_speed_deg_s * dt
        self._clamp_angles()

    def _clamp_angles(self) -> None:
        self.yaw_deg = max(
            self.config.aim_yaw_min_deg, min(self.yaw_deg, self.config.aim_yaw_max_deg)
        )
        self.pitch_deg = max(
            self.config.aim_pitch_min_deg, min(self.pitch_deg, self.config.aim_pitch_max_deg)
        )

    def _update_arrow(self, dt: float) -> None:
        assert self.arrow is not None
        arrow = self.arrow
        arrow.flight_time += dt
        arrow.velocity.z -= self.config.gravity * dt
        arrow.position += arrow.velocity * dt

        target_distance = self.config.target_distance()
        if arrow.position.y >= target_distance:
            self._finalize_shot(hit=True)
        elif arrow.position.y >= self.config.far_plane:
            self._finalize_shot(hit=False)

    def _finalize_shot(self, hit: bool) -> None:
        message = self._compute_shot_result(hit)
        self.last_message = message
        self.state = GameState.RESOLVE
        self.resolve_timer = 1.0
        self.arrow = None

    def _compute_shot_result(self, hit: bool) -> str:
        if not self.arrow:
            return "No arrow"

        arrow = self.arrow
        distance = self.config.target_distance()
        origin = arrow.origin
        velocity = arrow.velocity
        if not hit or velocity.y <= 0:
            return "Miss"

        t_hit = (distance - origin.y) / velocity.y
        x_hit = origin.x + velocity.x * t_hit
        z_hit = origin.z + velocity.z * t_hit - 0.5 * self.config.gravity * (t_hit**2)
        dx = x_hit - self.config.target_center_x
        dz = z_hit - self.config.target_center_z
        radial = math.hypot(dx, dz)
        ring_index = self._ring_index(radial)
        if ring_index is None:
            return "Miss"
        return "Bullseye!" if ring_index == 1 else f"Ring {ring_index}"

    def _ring_index(self, radial_distance: float) -> Optional[int]:
        step = self.config.target_outer_radius / self.config.target_ring_count
        for idx in range(1, self.config.target_ring_count + 1):
            if radial_distance <= step * idx + 1e-6:
                return idx
        return None

    def _render(self) -> None:
        self.screen.fill(self.config.bg_color)
        self._draw_target()
        if self.arrow:
            self._draw_arrow(self.arrow)
        self._draw_ui()
        pygame.display.flip()

    def _draw_target(self) -> None:
        target_y = self.config.target_distance()
        center_world = Vector3(
            self.config.target_center_x, target_y, self.config.target_center_z
        )
        center_screen = self._project(center_world)
        if not center_screen:
            return
        colors = self.config.target_colors
        ring_count = self.config.target_ring_count
        color_count = len(colors)
        for idx in reversed(range(ring_count)):
            radius_world = self.config.target_outer_radius * (idx + 1) / ring_count
            radius_pixels = self.focal_length * (radius_world / target_y)
            color = colors[min(idx, color_count - 1)]
            pygame.draw.circle(
                self.screen, color, center_screen, max(1, int(radius_pixels))
            )
        pygame.draw.circle(self.screen, self.config.ui_color, center_screen, 2)

    def _draw_arrow(self, arrow: Arrow) -> None:
        projected = self._project(arrow.position)
        if not projected:
            return
        depth_scale = max(2, int(12 / max(arrow.position.y, self.config.near_plane)))
        pygame.draw.circle(self.screen, self.config.arrow_color, projected, depth_scale)

    def _project(self, point: Vector3) -> Optional[Tuple[int, int]]:
        if point.y <= self.config.near_plane or point.y >= self.config.far_plane:
            return None
        sx = self.cx + self.focal_length * (point.x / point.y)
        sy = self.cy - self.focal_length * ((point.z - self.config.camera_z) / point.y)
        return int(sx), int(sy)

    def _draw_ui(self) -> None:
        ui_color = self.config.ui_color
        power_ratio = (
            min(self.draw_time / self.config.max_draw_seconds, 1.0)
            if self.state == GameState.CHARGING
            else 0.0
        )
        lines = [
            f"Yaw: {self.yaw_deg:+.1f} deg",
            f"Pitch: {self.pitch_deg:+.1f} deg",
            f"Power: {power_ratio*100:.0f}%",
            f"Info: {self.last_message}",
        ]
        for i, text in enumerate(lines):
            surface = self.font.render(text, True, ui_color)
            self.screen.blit(surface, (16, 16 + i * 24))

        self._draw_power_bar(power_ratio)
        self._draw_instructions()

    def _draw_power_bar(self, ratio: float) -> None:
        bar_width = 280
        bar_height = 16
        x = 16
        y = self.config.screen_height - bar_height - 32
        pygame.draw.rect(self.screen, (80, 80, 80), (x, y, bar_width, bar_height), 2)
        inner_width = int((bar_width - 4) * ratio)
        if inner_width > 0:
            pygame.draw.rect(
                self.screen,
                self.config.arrow_color,
                (x + 2, y + 2, inner_width, bar_height - 4),
            )

    def _draw_instructions(self) -> None:
        text = "A/D yaw  W/S pitch  SPACE hold+release  ESC quit"
        surface = self.small_font.render(text, True, self.config.ui_color)
        rect = surface.get_rect(
            center=(self.config.screen_width // 2, self.config.screen_height - 40)
        )
        self.screen.blit(surface, rect)


def main() -> None:
    config = GameConfig.load()
    game = BowGame(config)
    try:
        game.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
