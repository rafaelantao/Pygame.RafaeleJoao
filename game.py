import math
import os
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


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise RuntimeError(f"Missing required .env key: {key}")
    return value


def _parse_color(value: str) -> Tuple[int, int, int]:
    return tuple(int(part.strip()) for part in value.split(","))  # type: ignore[return-value]


def _parse_color_list(value: str) -> List[Tuple[int, int, int]]:
    return [_parse_color(entry) for entry in value.split(";") if entry.strip()]


def load_config() -> Dict[str, object]:
    load_dotenv()
    get_f = lambda key: float(_require_env(key))
    get_i = lambda key: int(_require_env(key))
    difficulty = _require_env("DIFFICULTY").strip().upper()
    distance_map = {
        "EASY": float(_require_env("DIST_EASY_M")),
        "MEDIUM": float(_require_env("DIST_MEDIUM_M")),
        "HARD": float(_require_env("DIST_HARD_M")),
    }
    if difficulty not in distance_map:
        raise RuntimeError(f"Unsupported difficulty '{difficulty}'")
    return {
        "screen_width": get_i("SCREEN_WIDTH"),
        "screen_height": get_i("SCREEN_HEIGHT"),
        "fps": get_i("FPS"),
        "fov_deg": get_f("FOV_DEG"),
        "camera_z": get_f("CAMERA_Z"),
        "near_plane": get_f("NEAR_PLANE_M"),
        "far_plane": get_f("FAR_PLANE_M"),
        "gravity": get_f("GRAVITY"),
        "max_arrow_speed": get_f("MAX_ARROW_SPEED"),
        "max_draw_seconds": get_f("MAX_DRAW_SECONDS"),
        "power_exponent": get_f("POWER_EXPONENT"),
        "aim_yaw_speed": get_f("AIM_YAW_SPEED_DEG_S"),
        "aim_yaw_min": get_f("AIM_YAW_MIN_DEG"),
        "aim_yaw_max": get_f("AIM_YAW_MAX_DEG"),
        "aim_pitch_speed": get_f("AIM_PITCH_SPEED_DEG_S"),
        "aim_pitch_min": get_f("AIM_PITCH_MIN_DEG"),
        "aim_pitch_max": get_f("AIM_PITCH_MAX_DEG"),
        "aim_initial_yaw": get_f("AIM_INITIAL_YAW_DEG"),
        "aim_initial_pitch": get_f("AIM_INITIAL_PITCH_DEG"),
        "target_outer_radius": get_f("TARGET_OUTER_RADIUS_M"),
        "target_ring_count": get_i("TARGET_RING_COUNT"),
        "target_center_x": get_f("TARGET_CENTER_X"),
        "target_center_z": get_f("TARGET_CENTER_Z"),
        "difficulty": difficulty,
        "distance_map": distance_map,
        "bg_color": _parse_color(_require_env("BG_COLOR")),
        "target_colors": _parse_color_list(_require_env("TARGET_COLORS")),
        "arrow_color": _parse_color(_require_env("ARROW_COLOR")),
        "ui_color": _parse_color(_require_env("UI_COLOR")),
    }


class BowGame:
    def __init__(self, config: Dict[str, object]) -> None:
        pygame.init()
        pygame.font.init()
        self.config = config
        self.screen = pygame.display.set_mode(
            (int(config["screen_width"]), int(config["screen_height"]))
        )
        pygame.display.set_caption("Semi-3D Bow & Arrow")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)

        self.cx = config["screen_width"] * 0.5  # type: ignore[operator]
        self.cy = config["screen_height"] * 0.5  # type: ignore[operator]
        fov_rad = math.radians(config["fov_deg"])  # type: ignore[arg-type]
        self.focal_length = 0.5 * config["screen_width"] / math.tan(fov_rad / 2.0)  # type: ignore[operator]

        self.state = GameState.AIMING
        self.yaw_deg = config["aim_initial_yaw"]  # type: ignore[assignment]
        self.pitch_deg = config["aim_initial_pitch"]  # type: ignore[assignment]
        self._clamp_angles()
        self.draw_time = 0.0
        self.arrow: Optional[Vector3] = None
        self.arrow_velocity: Optional[Vector3] = None
        self.arrow_origin: Optional[Vector3] = None
        self.arrow_time = 0.0
        self.last_message = ""
        self.resolve_timer = 0.0
        self.running = True

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(int(self.config["fps"])) / 1000.0
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
        max_draw = self.config["max_draw_seconds"]  # type: ignore[index]
        power_ratio = min(self.draw_time / max_draw, 1.0)
        if power_ratio <= 0.0:
            self.state = GameState.AIMING
            return

        shaped_power = power_ratio ** self.config["power_exponent"]  # type: ignore[index]
        launch_speed = self.config["max_arrow_speed"] * shaped_power  # type: ignore[index]
        yaw_rad = math.radians(self.yaw_deg)
        pitch_rad = math.radians(self.pitch_deg)
        cos_pitch = math.cos(pitch_rad)
        v_x = launch_speed * math.sin(yaw_rad) * cos_pitch
        v_y = launch_speed * math.cos(yaw_rad) * cos_pitch
        v_z = launch_speed * math.sin(pitch_rad)
        if v_y <= 0.0:
            self.state = GameState.AIMING
            self.last_message = "Can't shoot backward"
            return

        start_y = max(self.config["near_plane"], 1e-4)  # type: ignore[index]
        origin = Vector3(0.0, start_y, self.config["camera_z"])  # type: ignore[index]
        self.arrow = origin.copy()
        self.arrow_origin = origin.copy()
        self.arrow_velocity = Vector3(v_x, v_y, v_z)
        self.arrow_time = 0.0
        self.state = GameState.IN_FLIGHT
        self.last_message = ""

    def _update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        if self.state in (GameState.AIMING, GameState.CHARGING):
            self._update_aim(keys, dt)
        if self.state == GameState.CHARGING:
            self.draw_time = min(self.draw_time + dt, self.config["max_draw_seconds"])  # type: ignore[index]
        if self.state == GameState.IN_FLIGHT and self.arrow:
            self._update_arrow(dt)
        if self.state == GameState.RESOLVE:
            self.resolve_timer -= dt
            if self.resolve_timer <= 0.0:
                self.state = GameState.AIMING

    def _update_aim(self, keys, dt: float) -> None:
        yaw_speed = self.config["aim_yaw_speed"]  # type: ignore[index]
        pitch_speed = self.config["aim_pitch_speed"]  # type: ignore[index]
        if keys[pygame.K_a]:
            self.yaw_deg -= yaw_speed * dt
        if keys[pygame.K_d]:
            self.yaw_deg += yaw_speed * dt
        if keys[pygame.K_w]:
            self.pitch_deg += pitch_speed * dt
        if keys[pygame.K_s]:
            self.pitch_deg -= pitch_speed * dt
        self._clamp_angles()

    def _clamp_angles(self) -> None:
        self.yaw_deg = max(
            self.config["aim_yaw_min"], min(self.yaw_deg, self.config["aim_yaw_max"])
        )  # type: ignore[index]
        self.pitch_deg = max(
            self.config["aim_pitch_min"], min(self.pitch_deg, self.config["aim_pitch_max"])
        )  # type: ignore[index]

    def _update_arrow(self, dt: float) -> None:
        assert self.arrow and self.arrow_velocity and self.arrow_origin
        self.arrow_time += dt
        self.arrow_velocity.z -= self.config["gravity"] * dt  # type: ignore[index]
        self.arrow += self.arrow_velocity * dt
        distance = self.config["distance_map"][self.config["difficulty"]]  # type: ignore[index]
        if self.arrow.y >= distance:
            self._finalize_shot(hit=True)
        elif self.arrow.y >= self.config["far_plane"]:  # type: ignore[index]
            self._finalize_shot(hit=False)

    def _finalize_shot(self, hit: bool) -> None:
        self.state = GameState.RESOLVE
        self.resolve_timer = 1.0
        if not hit or not self.arrow_origin or not self.arrow_velocity:
            self.last_message = "Miss"
            self.arrow = None
            return
        origin = self.arrow_origin
        velocity = self.arrow_velocity
        distance = self.config["distance_map"][self.config["difficulty"]]  # type: ignore[index]
        t_hit = (distance - origin.y) / max(velocity.y, 1e-4)
        x_hit = origin.x + velocity.x * t_hit
        z_hit = origin.z + velocity.z * t_hit - 0.5 * self.config["gravity"] * (t_hit**2)  # type: ignore[index]
        dx = x_hit - self.config["target_center_x"]  # type: ignore[index]
        dz = z_hit - self.config["target_center_z"]  # type: ignore[index]
        radial = math.hypot(dx, dz)
        ring = self._ring_index(radial)
        if ring is None:
            self.last_message = "Miss"
        elif ring == 1:
            self.last_message = "Bullseye!"
        else:
            self.last_message = f"Ring {ring}"
        self.arrow = None

    def _ring_index(self, radial_distance: float) -> Optional[int]:
        step = self.config["target_outer_radius"] / self.config["target_ring_count"]  # type: ignore[index]
        for idx in range(1, int(self.config["target_ring_count"]) + 1):  # type: ignore[index]
            if radial_distance <= step * idx + 1e-6:
                return idx
        return None

    def _render(self) -> None:
        self.screen.fill(self.config["bg_color"])  # type: ignore[index]
        self._draw_target()
        if self.arrow:
            self._draw_arrow()
        self._draw_ui()
        pygame.display.flip()

    def _draw_target(self) -> None:
        distance = self.config["distance_map"][self.config["difficulty"]]  # type: ignore[index]
        center_world = Vector3(
            self.config["target_center_x"], distance, self.config["target_center_z"]
        )  # type: ignore[index]
        center_screen = self._project(center_world)
        if not center_screen:
            return
        colors = self.config["target_colors"]  # type: ignore[index]
        rings = int(self.config["target_ring_count"])  # type: ignore[index]
        for idx in reversed(range(rings)):
            radius_world = self.config["target_outer_radius"] * (idx + 1) / rings  # type: ignore[index]
            radius_pixels = self.focal_length * (radius_world / distance)
            color = colors[min(idx, len(colors) - 1)]
            pygame.draw.circle(self.screen, color, center_screen, max(1, int(radius_pixels)))
        pygame.draw.circle(self.screen, self.config["ui_color"], center_screen, 2)  # type: ignore[index]

    def _draw_arrow(self) -> None:
        projected = self._project(self.arrow)  # type: ignore[arg-type]
        if not projected:
            return
        depth_scale = max(2, int(12 / max(self.arrow.y, self.config["near_plane"])))  # type: ignore[index]
        pygame.draw.circle(self.screen, self.config["arrow_color"], projected, depth_scale)  # type: ignore[index]

    def _project(self, point: Vector3) -> Optional[Tuple[int, int]]:
        if point.y <= self.config["near_plane"] or point.y >= self.config["far_plane"]:  # type: ignore[index]
            return None
        sx = self.cx + self.focal_length * (point.x / point.y)
        sy = self.cy - self.focal_length * ((point.z - self.config["camera_z"]) / point.y)  # type: ignore[index]
        return int(sx), int(sy)

    def _draw_ui(self) -> None:
        lines = [
            f"Yaw: {self.yaw_deg:+.1f}",
            f"Pitch: {self.pitch_deg:+.1f}",
            f"State: {self.state.name}",
            f"Info: {self.last_message or '—'}",
        ]
        for i, text in enumerate(lines):
            surface = self.font.render(text, True, self.config["ui_color"])  # type: ignore[index]
            self.screen.blit(surface, (16, 16 + i * 22))


def main() -> None:
    config = load_config()
    game = BowGame(config)
    try:
        game.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
