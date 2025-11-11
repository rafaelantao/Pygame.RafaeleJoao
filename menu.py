from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame


BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "music_enabled": True,
    "sfx_enabled": True,
    "bow_type": "base",
}


@dataclass(frozen=True)
class BowProfile:
    key: str
    label: str
    description: str
    image_file: str
    damage: float
    fire_rate: float


BOW_PROFILES: Dict[str, BowProfile] = {
    "base": BowProfile(
        key="base",
        label="Base",
        description="Reliable starter bow with balanced stats.",
        image_file="Purple Bow and Arrow.png",
        damage=1.0,
        fire_rate=1.0,
    ),
    "intermediate": BowProfile(
        key="intermediate",
        label="Intermediate",
        description="Improved limbs for extra punch and speed.",
        image_file="Purple Bow and Arrow PNG.png",
        damage=1.3,
        fire_rate=1.15,
    ),
    "advanced": BowProfile(
        key="advanced",
        label="Advanced",
        description="Forged with fire rune cores. Fastest draw.",
        image_file="Red Fire Bow and Arrow.png",
        damage=1.6,
        fire_rate=1.3,
    ),
}

BOW_ORDER: List[str] = ["base", "intermediate", "advanced"]


def load_settings() -> Dict[str, bool | str]:
    settings: Dict[str, bool | str] = DEFAULT_SETTINGS.copy()
    if not SETTINGS_PATH.exists():
        return settings
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    for key in settings:
        if key in data:
            settings[key] = data[key]
    return settings


def save_settings(settings: Dict[str, bool | str]) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_bow_profile(key: str) -> BowProfile:
    return BOW_PROFILES.get(key, BOW_PROFILES["base"])


class StartMenu:
    def __init__(
        self,
        config,
        initial_settings: Optional[Dict[str, bool | str]] = None,
        surface: Optional[pygame.Surface] = None,
        start_label: str = "Start Game",
    ) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        self.config = config
        self.surface = surface or pygame.display.set_mode(
            (config.screen_width, config.screen_height)
        )
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("consolas", 48)
        self.option_font = pygame.font.SysFont("consolas", 28)
        self.small_font = pygame.font.SysFont("consolas", 20)

        self.settings: Dict[str, bool | str] = DEFAULT_SETTINGS.copy()
        if initial_settings:
            for key, value in initial_settings.items():
                if key in self.settings:
                    self.settings[key] = value

        self.menu_items = [
            {"key": "music", "label": "Music", "type": "toggle"},
            {"key": "sfx", "label": "Sound Effects", "type": "toggle"},
            {"key": "bow", "label": "Bow Type", "type": "choice"},
            {"key": "start", "label": start_label, "type": "action"},
        ]
        self.selected_index = 0
        self.option_rects: List[Tuple[int, pygame.Rect]] = []
        self.running = False
        self.confirmed = False
        self.hover_index: Optional[int] = None
        self.audio_available = self._ensure_mixer()
        self.quit_requested = False
        self.bow_images = self._load_bow_images()
        self._apply_audio_preview()

    def run(self) -> Optional[Dict[str, bool | str]]:
        pygame.mouse.set_visible(True)
        self.running = True
        self.confirmed = False
        self.quit_requested = False
        while self.running:
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.confirmed = False
                    self.quit_requested = True
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_mouse_click(event.pos)

            self._draw()
            pygame.display.flip()
        return self.settings.copy() if self.confirmed else None

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_UP, pygame.K_w):
            self._move_selection(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._move_selection(1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._activate_current(direction=1)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self._activate_current(direction=-1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_current()
        elif event.key == pygame.K_ESCAPE:
            self.running = False
            self.confirmed = False

    def _handle_mouse_motion(self, pos: Tuple[int, int]) -> None:
        for idx, rect in self.option_rects:
            if rect.collidepoint(pos):
                self.selected_index = idx
                self.hover_index = idx
                return
        self.hover_index = None

    def _handle_mouse_click(self, pos: Tuple[int, int]) -> None:
        for idx, rect in self.option_rects:
            if rect.collidepoint(pos):
                self.selected_index = idx
                self._activate_current()
                return

    def _move_selection(self, delta: int) -> None:
        self.selected_index = (self.selected_index + delta) % len(self.menu_items)

    def _activate_current(self, direction: int = 0) -> None:
        item = self.menu_items[self.selected_index]
        key = item["key"]
        if key == "music":
            self.settings["music_enabled"] = not bool(self.settings["music_enabled"])
            save_settings(self.settings)
            self._apply_audio_preview()
        elif key == "sfx":
            self.settings["sfx_enabled"] = not bool(self.settings["sfx_enabled"])
            save_settings(self.settings)
            self._apply_audio_preview()
        elif key == "bow":
            self._cycle_bow(direction if direction != 0 else 1)
        elif key == "start":
            self.confirmed = True
            save_settings(self.settings)
            self.running = False

    def _cycle_bow(self, direction: int) -> None:
        current = str(self.settings.get("bow_type", "base"))
        idx = BOW_ORDER.index(current) if current in BOW_ORDER else 0
        idx = (idx + direction) % len(BOW_ORDER)
        self.settings["bow_type"] = BOW_ORDER[idx]
        save_settings(self.settings)

    def _draw(self) -> None:
        self.surface.fill((12, 16, 28))
        title = self.title_font.render("Rafaele & Joao Archery", True, (230, 230, 240))
        title_rect = title.get_rect(center=(self.config.screen_width // 2, 80))
        self.surface.blit(title, title_rect)

        list_width = min(520, int(self.config.screen_width * 0.45))
        preview_width = min(380, int(self.config.screen_width * 0.35))
        spacing = 32
        total_width = list_width + preview_width + spacing
        start_x = max(40, (self.config.screen_width - total_width) // 2)
        list_x = start_x
        preview_x = start_x + list_width + spacing
        option_height = 70
        total_height = len(self.menu_items) * option_height + (len(self.menu_items) - 1) * 16
        start_y = max(140, (self.config.screen_height - total_height) // 2)

        self.option_rects = []
        for idx, item in enumerate(self.menu_items):
            rect = pygame.Rect(list_x, start_y + idx * (option_height + 16), list_width, option_height)
            is_selected = idx == self.selected_index
            base_color = (35, 44, 68)
            highlight_color = (70, 96, 150)
            color = highlight_color if is_selected else base_color
            pygame.draw.rect(self.surface, color, rect, border_radius=12)
            pygame.draw.rect(self.surface, (255, 255, 255), rect, 2, border_radius=12)

            label = item["label"]
            value_text = self._value_text(item["key"])
            label_surface = self.option_font.render(label, True, (250, 250, 255))
            value_surface = self.option_font.render(value_text, True, (190, 210, 255))

            label_rect = label_surface.get_rect(midleft=(rect.left + 18, rect.centery))
            value_rect = value_surface.get_rect(midright=(rect.right - 18, rect.centery))
            self.surface.blit(label_surface, label_rect)
            self.surface.blit(value_surface, value_rect)

            if is_selected:
                hint = "Use ← → to toggle" if item["key"] != "start" else "Press Enter to continue"
                hint_surface = self.small_font.render(hint, True, (200, 220, 255))
                hint_rect = hint_surface.get_rect(midleft=(rect.left + 24, rect.bottom - 14))
                self.surface.blit(hint_surface, hint_rect)

            self.option_rects.append((idx, rect))

        self._draw_bow_preview(preview_x, start_y, preview_width, total_height)
        self._draw_instructions()

    def _draw_bow_preview(
        self, x: int, y: int, width: int, height: int
    ) -> None:
        profile = get_bow_profile(str(self.settings.get("bow_type", "base")))
        pygame.draw.rect(
            self.surface,
            (35, 44, 68),
            (x, y, width, height),
            border_radius=16,
        )
        pygame.draw.rect(
            self.surface,
            (255, 255, 255),
            (x, y, width, height),
            2,
            border_radius=16,
        )

        title = self.option_font.render(f"{profile.label} Bow", True, (250, 250, 255))
        self.surface.blit(title, (x + 16, y + 16))

        stats_text = f"Damage x{profile.damage:.1f} | Fire Rate x{profile.fire_rate:.2f}"
        stats_surface = self.small_font.render(stats_text, True, (200, 210, 240))
        self.surface.blit(stats_surface, (x + 16, y + 60))

        image_area = pygame.Rect(x + 16, y + 100, width - 32, height - 180)
        image = self.bow_images.get(profile.key)
        if image:
            scaled = self._scale_surface(image, image_area.size)
            rect = scaled.get_rect(center=image_area.center)
            self.surface.blit(scaled, rect)
        else:
            placeholder_rect = pygame.Rect(0, 0, image_area.width, image_area.height)
            placeholder_rect.center = image_area.center
            pygame.draw.rect(self.surface, (80, 80, 120), placeholder_rect, border_radius=12)
            msg = self.small_font.render("Image missing", True, (240, 240, 255))
            msg_rect = msg.get_rect(center=placeholder_rect.center)
            self.surface.blit(msg, msg_rect)

        description_surface = self.small_font.render(profile.description, True, (220, 230, 250))
        desc_rect = description_surface.get_rect(midbottom=(x + width // 2, y + height - 20))
        self.surface.blit(description_surface, desc_rect)

    def _draw_instructions(self) -> None:
        text = "Arrows/WASD navigate • Enter/Space confirm • ESC back"
        surface = self.small_font.render(text, True, (200, 210, 230))
        rect = surface.get_rect(
            center=(self.config.screen_width // 2, self.config.screen_height - 40)
        )
        self.surface.blit(surface, rect)

    def _value_text(self, key: str) -> str:
        if key == "music":
            return "ON" if self.settings["music_enabled"] else "OFF"
        if key == "sfx":
            return "ON" if self.settings["sfx_enabled"] else "OFF"
        if key == "bow":
            profile = get_bow_profile(str(self.settings.get("bow_type", "base")))
            return profile.label.upper()
        if key == "start":
            return "ENTER"
        return ""

    def _scale_surface(self, surface: pygame.Surface, target_size: Tuple[int, int]) -> pygame.Surface:
        max_width, max_height = target_size
        width, height = surface.get_size()
        scale = min(max_width / max(1, width), max_height / max(1, height), 1.0)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        return pygame.transform.smoothscale(surface, new_size)

    def _ensure_mixer(self) -> bool:
        if pygame.mixer.get_init():
            return True
        try:
            pygame.mixer.init()
            return True
        except pygame.error:
            return False

    def _apply_audio_preview(self) -> None:
        if not self.audio_available or not pygame.mixer.get_init():
            return
        music_volume = 1.0 if self.settings["music_enabled"] else 0.0
        pygame.mixer.music.set_volume(music_volume)

    def _load_bow_images(self) -> Dict[str, Optional[pygame.Surface]]:
        images: Dict[str, Optional[pygame.Surface]] = {}
        for key, profile in BOW_PROFILES.items():
            path = BASE_DIR / profile.image_file
            if not path.exists():
                images[key] = None
                continue
            try:
                image = pygame.image.load(str(path)).convert_alpha()
            except pygame.error:
                image = None
            images[key] = image
        return images
