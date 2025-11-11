import math
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector3
from dotenv import load_dotenv


# Representa os estados principais do loop, fica mais fácil enxergar a progressão.
class GameState(Enum):
    AIMING = auto()
    CHARGING = auto()
    IN_FLIGHT = auto()
    RESOLVE = auto()


# Estrutura simples para acompanhar posição/velocidade da flecha.
@dataclass
class Arrow:
    position: Vector3
    velocity: Vector3
    origin: Vector3
    launch_velocity: Vector3
    flight_time: float = 0.0


# Guardamos informações de cada disparo para a UI e pontuação.
@dataclass
class ShotResult:
    hit: bool
    ring_index: Optional[int]
    radial_distance: float
    hit_point: Tuple[float, float]
    time_to_plane: float
    message: str
    reason: Optional[str] = None
    points: int = 0


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


# Centralizamos tudo que vem do .env para facilitar ajustes sem mexer no código.
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
    arrow_timeout_seconds: float
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
    resolve_seconds: float
    quiver_size: int
    aim_circle_radius_px: int
    aim_circle_color: Tuple[int, int, int]

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
            arrow_timeout_seconds=_parse_float("ARROW_TIMEOUT_SECONDS"),
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
            resolve_seconds=_parse_float("RESOLVE_SECONDS"),
            quiver_size=_parse_int("QUIVER_SIZE"),
            aim_circle_radius_px=_parse_int("AIM_CIRCLE_RADIUS_PX"),
            aim_circle_color=_parse_color(_require_env("AIM_CIRCLE_COLOR")),
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
        self.yaw_deg = max(config.aim_yaw_min_deg, min(self.yaw_deg, config.aim_yaw_max_deg))
        self.pitch_deg = max(
            config.aim_pitch_min_deg, min(self.pitch_deg, config.aim_pitch_max_deg)
        )
        self.draw_time = 0.0
        self.arrow: Optional[Arrow] = None
        self.last_result: Optional[ShotResult] = None
        self.resolve_timer = 0.0
        self.warning_text: Optional[str] = None
        self.warning_timer = 0.0
        self.running = True
        self.quiver_size = config.quiver_size
        self.arrows_remaining = self.quiver_size
        self.quiver_score = 0
        self.awaiting_reload = False
        self.hit_markers: List[Vector3] = []

    def run(self) -> None:
        # Loop principal tradicional do Pygame.
        while self.running:
            dt = self.clock.tick(self.config.fps) / 1000.0
            self._handle_events()
            self._update(dt)
            self._render()
        pygame.quit()

    def _handle_events(self) -> None:
        # Processamos apenas o essencial para manter a responsividade.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self._start_charging()
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self._handle_difficulty_key(event.key)
                elif event.key == pygame.K_r:
                    self._reload_quiver()
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                self._release_shot()

    def _handle_difficulty_key(self, key: int) -> None:
        if self.state == GameState.IN_FLIGHT:
            return
        mapping = {pygame.K_1: "EASY", pygame.K_2: "MEDIUM", pygame.K_3: "HARD"}
        chosen = mapping.get(key)
        if chosen and chosen != self.config.difficulty:
            self.config.difficulty = chosen
            self.last_result = None
            self.hit_markers.clear()

    def _start_charging(self) -> None:
        # Impedimos disparos extras quando o jogador precisa recarregar.
        if self.awaiting_reload:
            self._queue_warning("Press R to reload quiver.")
            return
        if self.arrows_remaining <= 0:
            self._queue_warning("Out of arrows. Press R to reload.")
            return
        if self.state in (GameState.AIMING, GameState.CHARGING) and not self.arrow:
            self.state = GameState.CHARGING
            self.draw_time = 0.0

    def _release_shot(self) -> None:
        # Converte o tempo de carregamento em força inicial.
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
            self._queue_warning("Cannot shoot backward (adjust yaw/pitch).")
            return

        start_y = max(self.config.near_plane, 1e-4)
        start_pos = Vector3(0.0, start_y, self.config.camera_z)
        launch_velocity = Vector3(v_x, v_y, v_z)
        self.arrow = Arrow(
            position=start_pos.copy(),
            velocity=launch_velocity.copy(),
            origin=start_pos.copy(),
            launch_velocity=launch_velocity.copy(),
        )
        self.state = GameState.IN_FLIGHT
        self.last_result = None

    def _queue_warning(self, text: str) -> None:
        # Avisos curtos ajudam o jogador sem abrir diálogos.
        self.warning_text = text
        self.warning_timer = 1.5

    def _update(self, dt: float) -> None:
        if not self.running:
            return

        keys = pygame.key.get_pressed()
        if self.state in (GameState.AIMING, GameState.CHARGING):
            self._update_aim(keys, dt)

        if self.state == GameState.CHARGING:
            self.draw_time = min(self.draw_time + dt, self.config.max_draw_seconds)

        if self.state == GameState.IN_FLIGHT and self.arrow:
            self._update_arrow(dt)

        if self.state == GameState.RESOLVE:
            self.resolve_timer -= dt
            if self.resolve_timer <= 0.0:
                self.state = GameState.AIMING

        if self.warning_text:
            self.warning_timer -= dt
            if self.warning_timer <= 0.0:
                self.warning_text = None

    def _update_aim(self, keys, dt: float) -> None:
        # Sensibilidade reduzida deixa a mira mais estável em gamepads e teclado.
        yaw_speed = self.config.aim_yaw_speed_deg_s
        pitch_speed = self.config.aim_pitch_speed_deg_s
        if keys[pygame.K_a]:
            self.yaw_deg -= yaw_speed * dt
        if keys[pygame.K_d]:
            self.yaw_deg += yaw_speed * dt
        if keys[pygame.K_w]:
            self.pitch_deg += pitch_speed * dt
        if keys[pygame.K_s]:
            self.pitch_deg -= pitch_speed * dt
        self.yaw_deg = max(
            self.config.aim_yaw_min_deg, min(self.yaw_deg, self.config.aim_yaw_max_deg)
        )
        self.pitch_deg = max(
            self.config.aim_pitch_min_deg, min(self.pitch_deg, self.config.aim_pitch_max_deg)
        )

    def _update_arrow(self, dt: float) -> None:
        # Integração explícita simples é suficiente para este minigame.
        assert self.arrow is not None
        arrow = self.arrow
        arrow.flight_time += dt
        arrow.velocity.z -= self.config.gravity * dt
        arrow.position += arrow.velocity * dt

        if arrow.flight_time >= self.config.arrow_timeout_seconds:
            self._finalize_shot(hit=False, reason="Timeout")
            return

        if arrow.position.y >= self.config.far_plane:
            self._finalize_shot(hit=False, reason="Exceeded far plane")
            return

        target_distance = self.config.target_distance()
        if arrow.position.y >= target_distance:
            self._finalize_shot(hit=True, reason=None)

    def _finalize_shot(self, hit: bool, reason: Optional[str]) -> None:
        # Ao terminar o voo, calculamos pontuação e animamos o estado de resolução.
        result = self._compute_shot_result(hit, reason)
        self.last_result = result
        self.state = GameState.RESOLVE
        self.resolve_timer = self.config.resolve_seconds
        self.arrow = None
        if result.hit:
            self.hit_markers.append(
                Vector3(
                    result.hit_point[0],
                    self.config.target_distance(),
                    result.hit_point[1],
                )
            )
        self._update_quiver_after_shot(result.points)

    def _compute_shot_result(self, hit: bool, reason: Optional[str]) -> ShotResult:
        # Reaproveitamos o lançamento inicial para resolver interseção com o plano do alvo.
        if not self.arrow:
            # Should not occur, but keep values sane.
            return ShotResult(False, None, 0.0, (0.0, 0.0), 0.0, "No arrow", reason)

        arrow = self.arrow
        distance = self.config.target_distance()
        origin = arrow.origin
        launch_v = arrow.launch_velocity
        if not hit or launch_v.y <= 0:
            return ShotResult(
                False,
                None,
                0.0,
                (0.0, 0.0),
                arrow.flight_time,
                reason or "Missed target plane",
                reason,
                0,
            )

        t_hit = (distance - origin.y) / launch_v.y
        x_hit = origin.x + launch_v.x * t_hit
        z_hit = origin.z + launch_v.z * t_hit - 0.5 * self.config.gravity * (t_hit**2)
        dx = x_hit - self.config.target_center_x
        dz = z_hit - self.config.target_center_z
        radial = math.hypot(dx, dz)
        ring_index = self._ring_index(radial)
        points = self._points_for_ring(ring_index) if ring_index is not None else 0
        message = (
            f"Ring {ring_index} hit!" if ring_index is not None else "Missed bullseye!"
        )
        return ShotResult(
            ring_index is not None,
            ring_index,
            radial,
            (x_hit, z_hit),
            t_hit,
            message,
            reason,
            points,
        )

    def _ring_index(self, radial_distance: float) -> Optional[int]:
        step = self.config.target_outer_radius / self.config.target_ring_count
        for idx in range(1, self.config.target_ring_count + 1):
            if radial_distance <= step * idx + 1e-6:
                return idx
        return None

    def _points_for_ring(self, ring_index: Optional[int]) -> int:
        # Distribuímos as pontuações de forma linear entre 10 e 100 pontos.
        if ring_index is None:
            return 0
        max_score = 100
        min_score = 10
        rings = max(2, self.config.target_ring_count)
        step = (max_score - min_score) / (rings - 1)
        score = max_score - (ring_index - 1) * step
        return int(round(max(min_score, score)))

    def _update_quiver_after_shot(self, points: int) -> None:
        # Gerenciamos flechas, somamos pontos e forçamos o reload quando necessário.
        if self.arrows_remaining > 0:
            self.arrows_remaining -= 1
        self.quiver_score += points
        if self.arrows_remaining <= 0:
            self.awaiting_reload = True
            self._queue_warning("Quiver empty. Press R to reload.")

    def _reload_quiver(self) -> None:
        # Reset da rodada: limpa marcadores, recarrega flechas e remove avisos.
        if not self.awaiting_reload and self.arrows_remaining == self.quiver_size:
            return
        if self.state == GameState.IN_FLIGHT:
            self._queue_warning("Wait for arrow to finish before reloading.")
            return
        self.arrows_remaining = self.quiver_size
        self.quiver_score = 0
        self.awaiting_reload = False
        self.warning_text = None
        self.hit_markers.clear()

    def _render(self) -> None:
        # Desenhamos o mundo numa ordem fixa para manter a sensação semi-3D.
        self.screen.fill(self.config.bg_color)
        self._draw_target()
        self._draw_aim_circle()
        if self.arrow:
            self._draw_arrow(self.arrow)
        self._draw_ui()
        pygame.display.flip()

    def _draw_target(self) -> None:
        # Desenhamos círculos com escala em perspectiva (1 / distância).
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
        for marker in self.hit_markers:
            marker_screen = self._project(marker)
            if marker_screen:
                self._draw_hit_marker(marker_screen)

    def _draw_aim_circle(self) -> None:
        # O círculo representa a linha reta entre a mira atual e o plano do alvo.
        world_point = self._aim_indicator_world_point()
        if not world_point:
            return
        projected = self._project(world_point)
        if not projected:
            return
        radius = max(2, self.config.aim_circle_radius_px)
        pygame.draw.circle(
            self.screen,
            self.config.aim_circle_color,
            projected,
            radius,
            2,
        )

    def _draw_arrow(self, arrow: Arrow) -> None:
        # A flecha é um pequeno círculo cujo tamanho diminui com a distância.
        projected = self._project(arrow.position)
        if not projected:
            return
        depth_scale = max(2, int(12 / max(arrow.position.y, self.config.near_plane)))
        pygame.draw.circle(self.screen, self.config.arrow_color, projected, depth_scale)

    def _aim_indicator_world_point(self) -> Optional[Vector3]:
        # Ignoramos gravidade aqui para dar uma dica “idealizada” ao jogador.
        direction = self._aim_direction_vector()
        if direction.y <= 1e-5:
            return None
        origin = Vector3(
            0.0,
            max(self.config.near_plane + 1e-3, 1e-3),
            self.config.camera_z,
        )
        t = (self.config.target_distance() - origin.y) / direction.y
        if t <= 0:
            return None
        return origin + direction * t

    def _aim_direction_vector(self) -> Vector3:
        # Converte ângulos em um vetor unitário no espaço 3D.
        yaw_rad = math.radians(self.yaw_deg)
        pitch_rad = math.radians(self.pitch_deg)
        cos_pitch = math.cos(pitch_rad)
        return Vector3(
            math.sin(yaw_rad) * cos_pitch,
            math.cos(yaw_rad) * cos_pitch,
            math.sin(pitch_rad),
        )

    def _project(self, point: Vector3) -> Optional[Tuple[int, int]]:
        # Projeção pinhole simples alinhada ao eixo Y.
        if point.y <= self.config.near_plane or point.y >= self.config.far_plane:
            return None
        sx = self.cx + self.focal_length * (point.x / point.y)
        sy = self.cy - self.focal_length * ((point.z - self.config.camera_z) / point.y)
        return int(sx), int(sy)

    def _draw_hit_marker(self, position: Tuple[int, int]) -> None:
        size = 8
        color = (220, 40, 40)
        x, y = position
        pygame.draw.line(self.screen, color, (x - size, y - size), (x + size, y + size), 2)
        pygame.draw.line(self.screen, color, (x - size, y + size), (x + size, y - size), 2)

    def _draw_ui(self) -> None:
        # HUD textual com foco em ângulos, potência e placar da aljava.
        ui_color = self.config.ui_color
        lines = [
            f"Yaw: {self.yaw_deg:+.1f} deg",
            f"Pitch: {self.pitch_deg:+.1f} deg",
            f"Difficulty: {self.config.difficulty} ({self.config.target_distance():.1f} m)",
            f"Quiver: {self.arrows_remaining}/{self.quiver_size}  Score: {self.quiver_score}",
        ]

        if self.state == GameState.CHARGING:
            power_ratio = min(self.draw_time / self.config.max_draw_seconds, 1.0)
            shaped = power_ratio ** self.config.power_exponent
            speed = shaped * self.config.max_arrow_speed
            lines.append(f"Power: {power_ratio*100:.0f}%  Speed: {speed:.1f} m/s")
        else:
            lines.append("Power: 0%  Speed: 0.0 m/s")

        if self.last_result:
            status = (
                f"Hit ring {self.last_result.ring_index}"
                if self.last_result.hit and self.last_result.ring_index is not None
                else f"Miss ({self.last_result.reason or 'No hit'})"
            )
            lines.append(
                f"Last shot: {status}  r={self.last_result.radial_distance:.2f} m  pts={self.last_result.points}"
            )
        else:
            lines.append("Last shot: —")

        for i, text in enumerate(lines):
            surface = self.font.render(text, True, ui_color)
            self.screen.blit(surface, (16, 16 + i * 24))

        self._draw_power_bar()
        self._draw_instructions()
        if self.warning_text:
            warning_surface = self.font.render(self.warning_text, True, (255, 150, 0))
            rect = warning_surface.get_rect(center=(self.config.screen_width // 2, 40))
            self.screen.blit(warning_surface, rect)

    def _draw_power_bar(self) -> None:
        bar_width = 300
        bar_height = 18
        x = 16
        y = self.config.screen_height - bar_height - 24
        pygame.draw.rect(self.screen, (80, 80, 80), (x, y, bar_width, bar_height), 2)
        if self.state == GameState.CHARGING:
            ratio = min(self.draw_time / self.config.max_draw_seconds, 1.0)
        else:
            ratio = 0.0
        inner_width = int((bar_width - 4) * ratio)
        if inner_width > 0:
            pygame.draw.rect(
                self.screen,
                self.config.arrow_color,
                (x + 2, y + 2, inner_width, bar_height - 4),
            )

    def _draw_instructions(self) -> None:
        # Mantemos o tutorial sempre visível para facilitar testes rápidos.
        extra = " | OUT OF ARROWS - PRESS R" if self.awaiting_reload else ""
        text = (
            "A/D yaw  W/S pitch  SPACE hold+release to fire  1-3 difficulty  R reload  ESC quit"
            + extra
        )
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
