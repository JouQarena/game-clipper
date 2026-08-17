"""
Configuration manager - Handles loading and saving settings.
"""

import json
import os
import shutil
import sys


class ConfigManager:
    """Manages application configuration from config.json."""

    DEFAULTS = {
        "buffer_duration_seconds": 30,
        "resolution": "720p",
        "fps": 30,
        "audio_source": "game_only",
        "hotkey": "F8",
        "save_location": os.path.expanduser("~/Videos/GameClipper"),
        "buffer_storage": "memory",
        "run_on_startup": False,
        "minimize_to_tray": True,
        "enable_overlay": True,
        "enable_game_detection": True,
        "video_quality": 23,
        "output_format": "mp4",
        "codec": "libx264",
    }

    RESOLUTION_MAP = {
        "360p": (640, 360),
        "480p": (854, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
    }

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = self._get_default_config_path()
        self.config_path = config_path
        self.data = dict(self.DEFAULTS)
        self.load()

    @staticmethod
    def _get_default_config_path():
        """Return the correct config path depending on environment.

        - Packaged exe (PyInstaller): %APPDATA%/GameClipper/config.json
        - Source run: project folder config.json
        """
        # Detect if running as a frozen (packaged) exe
        if getattr(sys, "frozen", False):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            folder = os.path.join(base, "GameClipper")
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, "config.json")
        # Running from source
        return os.path.join(os.path.dirname(__file__), "config.json")

    def load(self):
        """Load config from JSON file, falling back to defaults."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Config] Warning: Could not load config: {e}. Using defaults.")

    def save(self):
        """Save current configuration to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"[Config] Error saving config: {e}")
            return False

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    @property
    def resolution_width(self):
        res = self.get("resolution", "720p")
        return self.RESOLUTION_MAP.get(res, (1280, 720))[0]

    @property
    def resolution_height(self):
        res = self.get("resolution", "720p")
        return self.RESOLUTION_MAP.get(res, (1280, 720))[1]

    @property
    def resolution_string(self):
        return f"{self.resolution_width}x{self.resolution_height}"

    @property
    def resolution_tuple(self):
        return (self.resolution_width, self.resolution_height)